import io
import json
import os
import sqlite3
import uuid
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request, session, url_for, send_file
from werkzeug.security import check_password_hash, generate_password_hash

from database.init_db import init_db
from services.emergency_coordination import assess_emergency_scenario
from services.fleet_optimization import compare_route_alternatives
from services.fuel_prediction import build_prediction_model, evaluate_fuel_status, predict_fuel_consumption
from services.training_recommendation import evaluate_training_module, get_training_recommendation

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "database.db")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "marinva-secret-key"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def require_login():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return None


def fetch_ship(ship_id):
    conn = get_db_connection()
    ship = conn.execute("SELECT * FROM ships WHERE id = ?", (ship_id,)).fetchone()
    conn.close()
    return dict(ship) if ship else None


def fetch_all_ships():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM ships ORDER BY id").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def fetch_ports():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM port_information ORDER BY id").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def simple_dashboard_data(ship_ids=None):
    conn = get_db_connection()
    if ship_ids:
        placeholders = ",".join("?" for _ in ship_ids)
        ships = conn.execute(f"SELECT * FROM ships WHERE id IN ({placeholders}) ORDER BY id", ship_ids).fetchall()
    else:
        ships = conn.execute("SELECT * FROM ships ORDER BY id").fetchall()
    total_fuel = sum(float(ship["current_fuel_tons"]) for ship in ships)
    total_emissions = 0.0
    carbon_budget = 0.0
    for ship in ships:
        rec = conn.execute(
            "SELECT total_co2_tons, carbon_budget_pct FROM emission_records WHERE ship_id = ? ORDER BY recorded_at DESC LIMIT 1",
            (ship["id"],),
        ).fetchone()
        if rec:
            total_emissions += float(rec["total_co2_tons"])
            carbon_budget += float(rec["carbon_budget_pct"])
    emergency_alerts = conn.execute(
        "SELECT e.*, s.name AS ship_name FROM emergency_alerts e JOIN ships s ON s.id = e.ship_id ORDER BY e.triggered_at DESC LIMIT 5"
    ).fetchall()
    training = conn.execute(
        "SELECT crew_id, AVG(score) AS avg_score FROM training_assessments GROUP BY crew_id"
    ).fetchall()
    avg_training = round(sum(float(r["avg_score"]) for r in training) / len(training), 1) if training else 0
    conn.close()
    return {
        "total_ships": len(ships),
        "active_ships": sum(1 for ship in ships if ship["status"] != "Docked" and ship["status"] != "Port"),
        "fleet_fuel": round(total_fuel, 1),
        "estimated_emissions": round(total_emissions, 1),
        "carbon_budget": round(carbon_budget / len(ships), 1) if ships else 0,
        "fuel_alerts": sum(1 for ship in ships if float(ship["current_fuel_tons"]) / float(ship["fuel_capacity_tons"]) < 0.5),
        "emergency_alerts": len(emergency_alerts),
        "training_completion": round(avg_training, 1),
        "alerts": [dict(row) for row in emergency_alerts],
    }


@app.before_request
def initialize_if_needed():
    init_db()


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        valid_password = False
        if user:
            password_hash = user["password_hash"] if "password_hash" in user.keys() else None
            valid_password = check_password_hash(password_hash, password) if password_hash else user["password"] == password
            if password_hash is None:
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(password), user["id"]))
                conn.commit()
        conn.close()
        if user and valid_password:
            session["user_id"] = user["id"]
            session["user"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Invalid username or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        role = request.form.get("role", "crew").strip().lower()
        employee_id = request.form.get("employee_id", "").strip()
        responsibilities = request.form.get("responsibilities", "").strip()
        ship_id = request.form.get("ship_id", type=int)
        role_aliases = {
            "captain": "captain", "master": "captain", "vessel manager": "captain",
            "engineer": "engineer", "chief engineer": "engineer",
            "deck officer": "deck officer", "deck crew": "crew",
            "safety officer": "safety officer", "electrical engineer": "electrical engineer",
            "crew": "crew", "fleet administrator": "fleet administrator",
            "port authority": "fleet administrator", "admin": "admin", "operator": "admin"
        }
        role = role_aliases.get(role, role)

        if not username or not password or not full_name:
            return render_template(
                "register.html",
                error="All account fields are required."
            )

        conn = get_db_connection()

        try:
            existing_user = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,)
            ).fetchone()

            if existing_user:
                return render_template(
                    "register.html",
                    error="Username already exists."
                )

            if employee_id:
                existing_employee = conn.execute(
                    "SELECT id FROM users WHERE employee_id = ?",
                    (employee_id,)
                ).fetchone()

                if existing_employee:
                    return render_template(
                        "register.html",
                        error="Employee ID already exists."
                    )

            cursor = conn.execute(
                """
                INSERT INTO users
                (username, password, password_hash, full_name, role, employee_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    "legacy-migrated",
                    generate_password_hash(password),
                    full_name,
                    role,
                    employee_id
                )
            )

            user_id = cursor.lastrowid

            if role not in ("admin", "fleet administrator"):
                crew_id = f"CREW-{uuid.uuid4().hex[:10].upper()}"

                conn.execute(
                    """
                    INSERT INTO crew_profiles
                    (crew_id, full_name, language, ship_id, role, user_id, responsibilities)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        crew_id,
                        full_name,
                        "English",
                        ship_id,
                        role.title(),
                        user_id,
                        responsibilities
                    )
                )

                conn.execute(
                    "UPDATE users SET crew_id = ? WHERE id = ?",
                    (crew_id, user_id)
                )

            conn.commit()
            session.clear()
            session["user_id"] = user_id
            session["user"] = username
            session["full_name"] = full_name
            session["role"] = role
            if "crew_id" in locals() and crew_id:
                session["crew_id"] = crew_id
            return redirect(url_for("dashboard"))

        except sqlite3.IntegrityError:
            conn.rollback()
            return render_template(
                "register.html",
                error="Registration failed. Username or Employee ID may already exist."
            )

        except Exception:
            conn.rollback()
            return render_template(
                "register.html",
                error="Something went wrong during registration. Please try again."
            )

        finally:
            conn.close()

    conn = get_db_connection()
    ships = conn.execute("SELECT * FROM ships ORDER BY name")
    ship_rows = [dict(row) for row in ships]
    conn.close()

    return render_template("register.html", ships=ship_rows)


@app.route("/dashboard")
def dashboard():
    redirect_result = require_login()
    if redirect_result is not None:
        return redirect_result
    role = session.get("role", "").lower()
    ship_ids = None
    conn = get_db_connection()
    if role not in ("admin", "operator", "fleet administrator", "port authority"):
        crew = conn.execute("SELECT ship_id FROM crew_profiles WHERE user_id = ?", (session["user_id"],)).fetchone()
        ship_ids = [crew["ship_id"]] if crew and crew["ship_id"] else []
    data = simple_dashboard_data(ship_ids)
    if ship_ids:
        placeholders = ",".join("?" for _ in ship_ids)
        ships = conn.execute(f"SELECT * FROM ships WHERE id IN ({placeholders}) ORDER BY id", ship_ids).fetchall()
    else:
        ships = conn.execute("SELECT * FROM ships ORDER BY id").fetchall()
    fuel_history = conn.execute(
        "SELECT s.name, SUM(fr.fuel_consumed_tons) AS total_fuel, SUM(er.total_co2_tons) AS total_co2 FROM ships s LEFT JOIN fuel_records fr ON fr.ship_id = s.id LEFT JOIN emission_records er ON er.ship_id = s.id GROUP BY s.id ORDER BY s.id"
    ).fetchall()
    conn.close()
    return render_template("dashboard.html", dashboard=data, ships=ships, fuel_history=fuel_history)


@app.route("/fleet")
def fleet_page():
    redirect_result = require_login()
    if redirect_result is not None:
        return redirect_result
    conn = get_db_connection()
    ships = conn.execute("SELECT * FROM ships ORDER BY id").fetchall()
    ports = conn.execute("SELECT * FROM port_information ORDER BY id").fetchall()
    conn.close()
    return render_template("fleet.html", ships=ships, ports=ports)


@app.route("/fuel")
def fuel_page():
    redirect_result = require_login()
    if redirect_result is not None:
        return redirect_result
    conn = get_db_connection()
    ships = conn.execute("SELECT * FROM ships ORDER BY id").fetchall()
    ports = conn.execute("SELECT * FROM port_information ORDER BY id").fetchall()
    conn.close()
    return render_template("fuel.html", ships=ships, ports=ports)


@app.route("/emergency")
def emergency_page():
    redirect_result = require_login()
    if redirect_result is not None:
        return redirect_result
    conn = get_db_connection()
    ships = conn.execute("SELECT * FROM ships ORDER BY id").fetchall()
    ports = conn.execute("SELECT * FROM port_information ORDER BY id").fetchall()
    conn.close()
    return render_template("emergency.html", ships=ships, ports=ports)


@app.route("/training")
def training_page():
    redirect_result = require_login()
    if redirect_result is not None:
        return redirect_result
    conn = get_db_connection()
    crews = conn.execute("SELECT * FROM crew_profiles ORDER BY id").fetchall()
    modules = conn.execute("SELECT * FROM training_modules ORDER BY id").fetchall()
    conn.close()
    return render_template("training.html", crews=crews, modules=modules)


@app.route("/reports")
def reports_page():
    redirect_result = require_login()
    if redirect_result is not None:
        return redirect_result
    conn = get_db_connection()
    ship_rows = conn.execute("SELECT * FROM ships ORDER BY id").fetchall()
    voyage_rows = conn.execute("SELECT * FROM voyage_records ORDER BY id").fetchall()
    conn.close()
    return render_template("reports.html", ships=ship_rows, voyage_rows=voyage_rows)


@app.route("/profile")
def profile_page():
    redirect_result = require_login()
    if redirect_result is not None:
        return redirect_result
    return render_template("profile.html", user=session.get("full_name"), role=session.get("role"))


@app.route("/api/dashboard-data")
def api_dashboard_data():
    redirect_result = require_login()
    if redirect_result is not None:
        return jsonify({"error": "Authentication required"}), 401
    role = session.get("role", "").lower()
    ship_ids = None
    if role not in ("admin", "operator", "fleet administrator", "port authority"):
        conn = get_db_connection()
        crew = conn.execute("SELECT ship_id FROM crew_profiles WHERE user_id = ?", (session["user_id"],)).fetchone()
        conn.close()
        ship_ids = [crew["ship_id"]] if crew and crew["ship_id"] else []
    return jsonify(simple_dashboard_data(ship_ids))


@app.route("/api/fleet-sim", methods=["POST"])
def api_fleet_sim():
    payload = request.get_json(silent=True) or request.form
    ship_id = int(payload.get("ship_id", 1))
    ship = fetch_ship(ship_id)
    if not ship:
        return jsonify({"error": "Ship not found."}), 404
    alternatives = compare_route_alternatives(
        ship,
        weather=payload.get("weather", "Moderate"),
        distance=float(payload.get("distance", 5000)),
        speed=float(payload.get("speed", ship["speed_knots"])),
        fuel_type=payload.get("fuel_type", ship["fuel_type"]),
        start_port=payload.get("start_port", "Port Klang"),
        destination_port=payload.get("destination_port", ship["destination_port"]),
    )
    return jsonify({"alternatives": alternatives, "recommended": alternatives[0] if alternatives else {}})


@app.route("/api/fuel-analysis")
def api_fuel_analysis():
    ship_id = request.args.get("ship_id", 1, type=int)
    ship = fetch_ship(ship_id)
    if not ship:
        return jsonify({"error": "Ship not found."}), 404
    ports = fetch_ports()
    prediction = predict_fuel_consumption(
        ship,
        distance=float(request.args.get("distance", 5000)),
        speed=float(request.args.get("speed", ship["speed_knots"])),
        weather=request.args.get("weather", ship["weather_condition"]),
    )
    status = evaluate_fuel_status(ship, prediction["predicted_fuel_tons"], float(request.args.get("planned_distance", 3000)))
    compatibility = []
    for port in ports:
        available = port["available_fuels"].split(",")
        fuel_list = [item.strip() for item in available]
        compatible = ship["fuel_type"] in fuel_list or "LSFO" in fuel_list and ship["fuel_type"] == "VLSFO"
        compatibility.append({
            "port": port["name"],
            "fuel_type": port["available_fuels"],
            "compatible": compatible,
            "shore_power": bool(port["shore_power_available"]),
            "fuel_multiplier": port["fuel_cost_multiplier"],
            "availability": "Available" if compatible else "Incompatible",
        })
    return jsonify({
        "ship": ship,
        "prediction": prediction,
        "status": status,
        "port_options": compatibility,
        "model": build_prediction_model(),
    })


@app.route("/api/emergency-sim", methods=["POST"])
def api_emergency_sim():
    payload = request.get_json(silent=True) or request.form
    ship_id = int(payload.get("ship_id", 1))
    ship = fetch_ship(ship_id)
    if not ship:
        return jsonify({"error": "Ship not found."}), 404
    emergency_result = assess_emergency_scenario(
        ship,
        payload.get("emergency_type", "Engine failure"),
        payload.get("weather", ship["weather_condition"]),
        fetch_all_ships(),
        fetch_ports(),
    )
    return jsonify(emergency_result)


@app.route("/api/training-modules")
def api_training_modules():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM training_modules ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/api/training-dashboard")
def api_training_dashboard():
    redirect_result = require_login()
    if redirect_result is not None:
        return jsonify({"error": "Authentication required."}), 401
    conn = get_db_connection()
    role = session.get("role", "").lower()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    if role in ("crew", "engineer", "deck officer", "safety officer", "electrical engineer"):
        crew = conn.execute("SELECT * FROM crew_profiles WHERE user_id = ? OR crew_id = ?", (user["id"], user["crew_id"])).fetchone()
        crew_ids = [crew["crew_id"]] if crew else []
    elif role == "master" or role == "captain":
        crew = conn.execute("SELECT ship_id FROM crew_profiles WHERE user_id = ?", (user["id"],)).fetchone()
        ship_id = crew["ship_id"] if crew else None
        crew_ids = [r["crew_id"] for r in conn.execute("SELECT crew_id FROM crew_profiles WHERE ship_id = ?", (ship_id,)).fetchall()] if ship_id else []
    else:
        crew_ids = [r["crew_id"] for r in conn.execute("SELECT crew_id FROM crew_profiles")]

    placeholders = ",".join("?" for _ in crew_ids) if crew_ids else "NULL"
    params = crew_ids
    modules = [dict(r) for r in conn.execute("SELECT * FROM training_modules WHERE code NOT LIKE '%-hi' ORDER BY id")]
    assessments = [dict(r) for r in conn.execute(f"SELECT * FROM training_assessments WHERE crew_id IN ({placeholders}) ORDER BY submitted_at DESC", params)] if crew_ids else []
    certificates = [dict(r) for r in conn.execute(f"SELECT c.*, m.title FROM training_certificates c JOIN training_modules m ON m.code = c.module_code WHERE c.crew_id IN ({placeholders}) ORDER BY c.completion_date DESC", params)] if crew_ids else []
    completed_codes = {r["module_code"] for r in assessments if r["passed"]}
    progress = round(len(completed_codes) / len(modules) * 100, 1) if modules else 0
    weak_areas = [r["weak_area"] for r in assessments if r["weak_area"]]
    recommendations = list(dict.fromkeys(weak_areas))[:3]
    conn.close()
    return jsonify({"modules": modules, "assessments": assessments, "certificates": certificates, "progress": progress, "recommendations": recommendations})


ROLE_ASSESSMENT_ALIASES = {
    "master": "captain", "vessel manager": "captain", "chief engineer": "engineer",
    "deck crew": "crew", "deck officer": "deck officer", "safety officer": "safety officer",
    "electrical engineer": "electrical engineer", "crew": "crew", "engineer": "engineer",
}


@app.route("/api/personalized-assessment")
def api_personalized_assessment():
    redirect_result = require_login()
    if redirect_result is not None:
        return jsonify({"error": "Authentication required."}), 401
    conn = get_db_connection()
    crew = conn.execute("SELECT * FROM crew_profiles WHERE user_id = ?", (session["user_id"],)).fetchone()
    if not crew:
        conn.close()
        return jsonify({"error": "A crew profile is required."}), 403
    role_key = ROLE_ASSESSMENT_ALIASES.get((crew["role"] or "crew").lower(), (crew["role"] or "crew").lower())
    def load(category):
        role_filter = "common" if category == "common" else role_key
        rows = conn.execute("SELECT * FROM assessment_questions WHERE category = ? AND role_key = ? ORDER BY id", (category, role_filter)).fetchall()
        return [{"code": r["code"], "stage": r["stage"], "prompt": r["prompt"], "options": json.loads(r["options"]), "marks": r["marks"]} for r in rows]
    individual = load("individual")
    common = load("common")
    attempts = conn.execute("SELECT category, score, passed, submitted_at FROM assessment_attempts WHERE user_id = ? ORDER BY submitted_at DESC", (session["user_id"],)).fetchall()
    conn.close()
    return jsonify({"role": crew["role"], "role_key": role_key, "responsibilities": crew["responsibilities"] if "responsibilities" in crew.keys() else "", "individual": individual, "common": common, "attempts": [dict(r) for r in attempts]})


@app.route("/api/personalized-assessment/submit", methods=["POST"])
def api_personalized_assessment_submit():
    redirect_result = require_login()
    if redirect_result is not None:
        return jsonify({"error": "Authentication required."}), 401
    payload = request.get_json(silent=True) or {}
    category = payload.get("category")
    if category not in ("individual", "common"):
        return jsonify({"error": "Invalid assessment category."}), 400
    conn = get_db_connection()
    crew = conn.execute("SELECT * FROM crew_profiles WHERE user_id = ?", (session["user_id"],)).fetchone()
    if not crew:
        conn.close()
        return jsonify({"error": "Crew profile not found."}), 403
    role_key = ROLE_ASSESSMENT_ALIASES.get((crew["role"] or "crew").lower(), (crew["role"] or "crew").lower())
    expected_role = "common" if category == "common" else role_key
    questions = conn.execute("SELECT * FROM assessment_questions WHERE category = ? AND role_key = ? ORDER BY id", (category, expected_role)).fetchall()
    submitted = {str(a.get("code")): a.get("option") for a in payload.get("answers", []) if isinstance(a, dict)}
    if set(submitted) != {q["code"] for q in questions}:
        conn.close()
        return jsonify({"error": "Answer every question before submission."}), 400
    earned = 0
    mistakes = []
    for q in questions:
        correct = submitted[q["code"]] == q["correct_option"]
        if correct:
            earned += q["marks"]
        else:
            mistakes.append({"code": q["code"], "selected": submitted[q["code"]], "correct": q["correct_option"], "feedback": q["feedback"], "weak_area": q["weak_area"]})
    total = sum(q["marks"] for q in questions) or 1
    score = round(earned * 100 / total, 1)
    passed = score > 80
    cursor = conn.execute("INSERT INTO assessment_attempts (user_id, crew_id, category, role_key, score, passed, elapsed_seconds) VALUES (?, ?, ?, ?, ?, ?, ?)", (session["user_id"], crew["crew_id"], category, expected_role, score, int(passed), max(int(payload.get("elapsed_seconds", 0)), 0)))
    for q in questions:
        conn.execute("INSERT INTO assessment_attempt_answers (attempt_id, question_code, selected_option, correct_option, is_correct) VALUES (?, ?, ?, ?, ?)", (cursor.lastrowid, q["code"], submitted[q["code"]], q["correct_option"], int(submitted[q["code"]] == q["correct_option"])))
    conn.commit()
    recommendation = "Repeat the role-specific scenarios" if mistakes else "Progress to the next supervised drill"
    conn.close()
    return jsonify({"score": score, "passed": passed, "mistakes": mistakes, "recommendation": recommendation})


ASSESSMENT_SCENARIOS = {
    "engine-fire": [
        {"id":"fire_alarm","stage":"Hazard identification","prompt":"Smoke and high temperature alarms activate in the engine room. What is your first action?","options":[{"id":"raise_alarm","text":"Raise the alarm, stop fuel supply and isolate electrical power"},{"id":"open_vents","text":"Open ventilation and doors to clear smoke"},{"id":"restart","text":"Restart the machinery to verify the fault"},{"id":"water_panel","text":"Apply water to energized equipment"}],"correct":"raise_alarm","marks":25,"feedback":"Containment and personnel safety come before suppression. Raise the alarm and isolate fuel and electrical sources.","weak_area":"Fire initial response"},
        {"id":"fire_source","stage":"Equipment selection","prompt":"The fire is confirmed in lubricating-oil piping. Which extinguisher is appropriate?","options":[{"id":"co2","text":"Approved CO2 or fixed gas suppression system"},{"id":"water","text":"Pressurized water jet"},{"id":"foam_lpg","text":"Ordinary household foam"},{"id":"none","text":"Leave the equipment burning while investigating"}],"correct":"co2","marks":25,"feedback":"Use only the approved suppression method for energized machinery and fuel fires, following fixed-system procedures.","weak_area":"Fire equipment"},
        {"id":"fire_entry","stage":"Controlled response","prompt":"A watchkeeper asks to enter before smoke dispersal. What should the team do?","options":[{"id":"wait_scbA","text":"Wait for authorization and enter only with SCBA and a named team"},{"id":"enter","text":"Enter immediately without protective equipment"},{"id":"phone","text":"Send one person without radio communication"},{"id":"ventilate","text":"Ventilate before confirming isolation"}],"correct":"wait_scbA","marks":25,"feedback":"Maintain exclusion controls and use breathing apparatus, communications and controlled entry procedures.","weak_area":"Fire entry control"}
    ],
    "gas-toxic": [
        {"id":"gas_warning","stage":"Hazard identification","prompt":"A gas detector alarms near a fuel manifold. What should you do first?","options":[{"id":"upwind","text":"Move personnel upwind, raise the alarm and keep clear"},{"id":"investigate","text":"Inspect the pipe without protective equipment"},{"id":"fan","text":"Aim powered ventilation toward the crew"},{"id":"transfer","text":"Continue transfer and monitor the alarm"}],"correct":"upwind","marks":35,"feedback":"Move to a safe upwind position and raise the alarm before attempting detection or isolation." ,"weak_area":"Gas hazard recognition"},
        {"id":"gas_ppe","stage":"PPE selection","prompt":"An authorized leak-team response is required. Which PPE is appropriate?","options":[{"id":"scba","text":"SCBA, gas detector, protective suit and radio communications"},{"id":"helmet","text":"Hard hat and standard work gloves"},{"id":"dust","text":"Disposable dust mask"},{"id":"shorts","text":"Standard coveralls only"}],"correct":"scba","marks":35,"feedback":"A breathing apparatus, suitable detector and team communications are required for the known atmosphere." ,"weak_area":"Gas PPE"},
        {"id":"gas_isolate","stage":"Emergency response","prompt":"The gas source is confirmed in a closed cargo area. What procedure follows?","options":[{"id":"isolate","text":"Stop transfer, isolate the source and activate the approved emergency plan"},{"id":"seal","text":"Seal the area without accounting for personnel"},{"id":"ignite","text":"Use ignition sources to burn off the gas"},{"id":"pump","text":"Start ventilators while transfer continues"}],"correct":"isolate","marks":30,"feedback":"Stop transfer, isolate energy and sources, and follow the ship emergency plan with accountability." ,"weak_area":"Gas isolation"}
    ],
    "ship-flooding": [
        {"id":"flood_alarm","stage":"Hazard identification","prompt":"Water is rapidly rising around an access hatch. What is your first response?","options":[{"id":"alarm","text":"Raise the alarm, prevent access and report compartment location"},{"id":"cargo","text":"Continue cargo operations"},{"id":"open","text":"Open more hatches for inspection"},{"id":"speed","text":"Increase vessel speed"}],"correct":"alarm","marks":30,"feedback":"Raise the alarm immediately and provide a precise compartment and trend report." ,"weak_area":"Flooding recognition"},
        {"id":"flood_isolate","stage":"Damage control","prompt":"The leak is found behind a service pipe. What controlled action comes next?","options":[{"id":"source","text":"Isolate pipe systems and assess whether safe dewatering can begin"},{"id":"pump_fast","text":"Start maximum pumping without locating the source"},{"id":"door","text":"Open adjacent doors to equalize water"},{"id":"ignore","text":"Wait until the bilge alarm activates"}],"correct":"source","marks":35,"feedback":"Locate and isolate the water source, preserve stability, then coordinate safe dewatering." ,"weak_area":"Flooding damage control"},
        {"id":"flood_stability","stage":"Stability and accountability","prompt":"The vessel develops an increasing list. What is the safest command response?","options":[{"id":"control","text":"Stop unnecessary water movement, assess stability and report to the Master"},{"id":"drill","text":"Flood the opposite side deliberately"},{"id":"full","text":"Continue full speed to outrun the ingress"},{"id":"wait","text":"Delay because the bilge alarm may reset"}],"correct":"control","marks":35,"feedback":"Stability is a priority. Preserve watertight integrity and inform the Master without delay." ,"weak_area":"Flooding stability"}
    ],
    "emergency-muster": [
        {"id":"evacuate","stage":"Emergency response","prompt":"The general alarm sounds and smoke blocks the primary route. What do you do?","options":[{"id":"alternate","text":"Use the designated alternate route without entering smoke"},{"id":"primary","text":"Walk through smoke to reach the primary route"},{"id":"return","text":"Return to the cabin to collect belongings"},{"id":"wait","text":"Wait inside until a route is announced"}],"correct":"alternate","marks":35,"feedback":"Use a safe designated alternate route and keep low only when required by approved ship procedures." ,"weak_area":"Evacuation routing"},
        {"id":"muster","stage":"Muster procedure","prompt":"You reach the muster station. What is the immediate priority?","options":[{"id":"headcount","text":"Report presence and assist with the headcount"},{"id":"equipment","text":"Leave the station to collect tools"},{"id":"lifeboat","text":"Board the lifeboat without instruction"},{"id":"camera","text":"Film the emergency for later review"}],"correct":"headcount","marks":35,"feedback":"Accountability and command reporting are immediate muster priorities." ,"weak_area":"Muster accountability"},
        {"id":"missing","stage":"Team decision","prompt":"A crew member is reported missing. What should you do?","options":[{"id":"report","text":"Report the person to command and follow the search-control plan"},{"id":"search","text":"Enter the hazard area alone"},{"id":"assume","text":"Assume they reached another station"},{"id":"depart","text":"Wait aboard while the vessel departs"}],"correct":"report","marks":30,"feedback":"Do not conduct an uncontrolled rescue. Report the missing person and follow the approved search plan." ,"weak_area":"Emergency accountability"}
    ],
    "marine-ppe": [
        {"id":"ppe_hazard","stage":"Hazard assessment","prompt":"The task requires entry to an unknown atmosphere. What PPE decision is correct?","options":[{"id":"scba","text":"Use SCBA with an approved suit, detector and team backup"},{"id":"dust","text":"Use a dust mask because no visible cloud is present"},{"id":"helmet","text":"Wear only a helmet and gloves"},{"id":"none","text":"Enter without protection and ventilate afterward"}],"correct":"scba","marks":40,"feedback":"Unknown atmospheres require positive-pressure breathing protection under the vessel permit and team controls." ,"weak_area":"Atmospheric PPE"},
        {"id":"ppe_inspect","stage":"Inspection","prompt":"Before entering, what should the team do first?","options":[{"id":"inspect","text":"Inspect seals, alarms, cylinder pressure and communications"},{"id":"shortcut","text":"Skip inspection if the equipment is clean"},{"id":"swap","text":"Share breathing equipment between users"},{"id":"finish","text":"Check PPE only after entering"}],"correct":"inspect","marks":30,"feedback":"Equipment must be inspected and function-tested before it enters service." ,"weak_area":"PPE inspection"},
        {"id":"ppe_remove","stage":"Contamination control","prompt":"The work is complete. What comes next?","options":[{"id":"decon","text":"Move to a clean area and follow contamination and equipment procedures"},{"id":"quick","text":"Remove all equipment immediately inside the hazard zone"},{"id":"store","text":"Store used equipment without inspection"},{"id":"reuse","text":"Reuse SCBA parts without testing"}],"correct":"decon","marks":30,"feedback":"Use the approved exit, decontamination and equipment-return process." ,"weak_area":"PPE removal"}
    ],
    "alternative-fuels": [
        {"id":"fuel_transfer","stage":"Pre-transfer checks","prompt":"Before alternative-fuel transfer, what confirmation is required?","options":[{"id":"checks","text":"Compatibility, bonding, detection, emergency isolation and alarm readiness"},{"id":"open","text":"Open transfer valves and monitor later"},{"id":"bypass","text":"Bypass alarms to improve flow"},{"id":"accommodation","text":"Vent vapors toward accommodation spaces"}],"correct":"checks","marks":35,"feedback":"Complete compatibility, bonding, leak-detection, isolation and alarm checks before transfer." ,"weak_area":"Alternative fuel preparation"},
        {"id":"fuel_leak","stage":"Leak response","prompt":"A vapor cloud detector activates during bunkering. What is the safe response?","options":[{"id":"stop","text":"Stop transfer, isolate applicable valves and move personnel upwind"},{"id":"continue","text":"Continue transfer until the cloud is visible"},{"id":"water","text":"Use high-pressure water directly on the vapor source"},{"id":"hot","text":"Use ignition tools to locate the leak"}],"correct":"stop","marks":35,"feedback":"Stop transfer and isolate the source before controlled investigation by a qualified team." ,"weak_area":"Alternative fuel leak response"},
        {"id":"fuel_spill","stage":"Spill control","prompt":"A small spill is confirmed in a bunded area. What is required?","options":[{"id":"plan","text":"Keep ignition sources clear, notify command and use the approved spill plan"},{"id":"enter","text":"Enter without PPE"},{"id":"drain","text":"Drain it overboard"},{"id":"absorb","text":"Dispose of fuel without checking vessel procedures"}],"correct":"plan","marks":30,"feedback":"Use vessel-specific spill controls, protect personnel, and notify command promptly." ,"weak_area":"Fuel spill control"}
    ]
}


ROLE_TRAINING_CONTEXT = {
    "captain": "As the person in command, demonstrate leadership, communication and command priorities.",
    "engineer": "As engine-room technical staff, demonstrate machinery isolation, system knowledge and safe technical response.",
    "crew": "As a deck crew member, demonstrate practical hazard control, assigned duties and team reporting.",
    "deck officer": "As deck watchkeeping staff, demonstrate bridge-deck coordination, watch duties and controlled deck actions.",
    "electrical engineer": "As electrical technical staff, demonstrate isolation, electrical safety and protection of powered systems.",
    "safety officer": "As the safety officer, demonstrate risk assessment, PPE compliance, crew accountability and emergency coordination.",
}


def normalize_training_role(role):
    role_key = (role or "crew").strip().lower()
    return ROLE_ASSESSMENT_ALIASES.get(role_key, role_key)


def role_assessment_scenario(module_code, role):
    scenario = ASSESSMENT_SCENARIOS.get(module_code)
    if not scenario:
        return None
    role_key = normalize_training_role(role)
    context = ROLE_TRAINING_CONTEXT.get(role_key, ROLE_TRAINING_CONTEXT["crew"])
    role_label = role_key.replace("-", " ").title()
    personalized = []
    for question in scenario:
        item = dict(question)
        item["options"] = [dict(option) for option in question["options"]]
        item["stage"] = f"{role_label} · {question['stage']}"
        item["prompt"] = f"{context} {question['prompt']}"
        personalized.append(item)
    return personalized


@app.route("/api/training-assessment/<module_code>")
def api_training_assessment(module_code):
    redirect_result = require_login()
    if redirect_result is not None:
        return jsonify({"error": "Authentication required."}), 401
    conn = get_db_connection()
    crew = conn.execute("SELECT role FROM crew_profiles WHERE user_id = ?", (session["user_id"],)).fetchone()
    conn.close()
    role = crew["role"] if crew else session.get("role", "crew")
    scenario = role_assessment_scenario(module_code, role)
    if not scenario:
        return jsonify({"error": "Assessment module not found."}), 404
    public_scenario = [{"id": q["id"], "stage": q["stage"], "prompt": q["prompt"], "options": q["options"]} for q in scenario]
    return jsonify({"module_code": module_code, "role": role, "questions": public_scenario})


@app.route("/api/training-sessions", methods=["POST"])
def api_training_session():
    redirect_result = require_login()
    if redirect_result is not None:
        return jsonify({"error": "Authentication required."}), 401
    payload = request.get_json(silent=True) or {}
    module_code = payload.get("module_code")
    conn = get_db_connection()
    module = conn.execute("SELECT * FROM training_modules WHERE code = ?", (module_code,)).fetchone()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    crew = conn.execute("SELECT * FROM crew_profiles WHERE user_id = ? OR crew_id = ?", (user["id"], user["crew_id"])).fetchone()
    if not module or not crew:
        conn.close()
        return jsonify({"error": "A linked crew profile is required."}), 400
    cursor = conn.execute("INSERT INTO training_sessions (user_id, crew_id, module_code) VALUES (?, ?, ?)", (user["id"], crew["crew_id"], module_code))
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return jsonify({"session_id": session_id})


@app.route("/api/training-submit", methods=["POST"])
def api_training_submit():
    redirect_result = require_login()
    if redirect_result is not None:
        return jsonify({"error": "Authentication required."}), 401
    payload = request.get_json(silent=True) or {}
    conn = get_db_connection()
    training_session = conn.execute("SELECT * FROM training_sessions WHERE id = ? AND user_id = ?", (payload.get("session_id"), session["user_id"])).fetchone()
    if not training_session:
        conn.close()
        return jsonify({"error": "Training session not found."}), 404
    if training_session["submitted_at"]:
        conn.close()
        return jsonify({"error": "This assessment has already been submitted."}), 409
    crew_role = conn.execute("SELECT role FROM crew_profiles WHERE crew_id = ?", (training_session["crew_id"],)).fetchone()
    questions = role_assessment_scenario(training_session["module_code"], crew_role["role"] if crew_role else session.get("role", "crew"))
    if not questions:
        conn.close()
        return jsonify({"error": "Assessment not configured."}), 400
    module = conn.execute("SELECT * FROM training_modules WHERE code = ?", (training_session["module_code"],)).fetchone()
    submitted = {str(a.get("key")): a.get("answer") for a in payload.get("answers", []) if isinstance(a, dict)}
    if set(submitted) != {q["id"] for q in questions}:
        conn.close()
        return jsonify({"error": "Answer every scenario question before submission."}), 400
    earned = 0
    total_marks = sum(q["marks"] for q in questions)
    mistakes = []
    for q in questions:
        selected = submitted.get(q["id"])
        is_correct = selected == q["correct"]
        if is_correct:
            earned += q["marks"]
        else:
            option = next((o for o in q["options"] if o["id"] == selected), None)
            mistakes.append({"key": q["id"], "stage": q["stage"], "selected": option["text"] if option else "No answer", "correct": next(o["text"] for o in q["options"] if o["id"] == q["correct"]), "feedback": q["feedback"], "weak_area": q["weak_area"]})
        conn.execute("INSERT INTO assessment_answers (session_id, question_key, selected_answer, correct_answer, is_correct) VALUES (?, ?, ?, ?, ?)", (training_session["id"], q["id"], str(selected), q["correct"], int(is_correct)))
    score = round(earned * 100 / total_marks, 1)
    elapsed = max(int(payload.get("elapsed_seconds", 0)), 1)
    passed = score > 80
    weak_area = mistakes[0]["weak_area"] if mistakes else "General readiness"
    recommendation = get_training_recommendation(module, score)
    conn.execute("UPDATE training_sessions SET submitted_at = ?, elapsed_seconds = ?, status = ? WHERE id = ?", (datetime.utcnow().isoformat(), elapsed, "Completed" if passed else "Needs review", training_session["id"]))
    conn.execute("INSERT INTO assessment_scores (session_id, crew_id, module_code, score, procedure_score, speed_score, mistake_count, passed, weak_area) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (training_session["id"], training_session["crew_id"], module["code"], score, score, 100 if elapsed < 300 else 70, len(mistakes), int(passed), weak_area))
    conn.execute("INSERT INTO training_assessments (crew_id, module_code, score, passed, weak_area, recommendation) VALUES (?, ?, ?, ?, ?, ?)", (training_session["crew_id"], module["code"], score, int(passed), weak_area, recommendation))
    conn.execute("INSERT OR REPLACE INTO training_progress (crew_id, module_code, status, score, completed_at, next_recommendation) VALUES (?, ?, ?, ?, ?, ?)", (training_session["crew_id"], module["code"], "Completed" if passed else "Needs review", score, datetime.utcnow().isoformat(), recommendation))
    certificate = None
    if passed:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        verification_id = uuid.uuid4().hex.upper()
        conn.execute("INSERT INTO training_certificates (verification_id, user_id, crew_id, module_code, score, completion_date) VALUES (?, ?, ?, ?, ?, ?)", (verification_id, user["id"], training_session["crew_id"], module["code"], score, datetime.utcnow().date().isoformat()))
        certificate = {"verification_id": verification_id}
    conn.commit()
    conn.close()
    return jsonify({"score": score, "passed": passed, "mistakes": mistakes, "weak_area": weak_area, "recommendation": recommendation, "certificate": certificate})


@app.route("/certificate/<verification_id>.pdf")
def certificate_pdf(verification_id):
    redirect_result = require_login()
    if redirect_result is not None:
        return redirect_result
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.pdfgen import canvas
    import qrcode

    conn = get_db_connection()
    cert = conn.execute("SELECT c.*, u.full_name, u.employee_id, cp.ship_id, cp.full_name AS crew_name, s.name AS vessel_name, m.title FROM training_certificates c JOIN users u ON u.id = c.user_id JOIN crew_profiles cp ON cp.crew_id = c.crew_id LEFT JOIN ships s ON s.id = cp.ship_id JOIN training_modules m ON m.code = c.module_code WHERE c.verification_id = ?", (verification_id,)).fetchone()
    conn.close()
    if not cert:
        return "Certificate not found", 404
    verify_url = url_for("certificate_verify", verification_id=verification_id, _external=True)
    qr_buffer = io.BytesIO()
    qrcode.make(verify_url).save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    pdf_buffer = io.BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=landscape(A4))
    pdf.setTitle("Prototype Maritime Training Certificate")
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawCentredString(420, 520, "PROTOTYPE TRAINING CERTIFICATE")
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(420, 485, "Not a statutory maritime certification")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(420, 440, cert["full_name"])
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(420, 415, f"Employee ID: {cert['employee_id'] or 'Not assigned'}")
    pdf.drawCentredString(420, 390, f"Module: {cert['title']}")
    pdf.drawCentredString(420, 365, f"Vessel: {cert['vessel_name'] or 'Not assigned'}")
    pdf.drawCentredString(420, 340, f"Score: {cert['score']:.1f}%  |  Completed: {cert['completion_date']}")
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(420, 315, f"Certificate ID: {verification_id}")
    pdf.drawImage(reportlab_image(qr_buffer), 680, 70, width=90, height=90)
    pdf.save()
    pdf_buffer.seek(0)
    return send_file(pdf_buffer, mimetype="application/pdf", as_attachment=True, download_name=f"training-{verification_id}.pdf")


def reportlab_image(buffer):
    from reportlab.lib.utils import ImageReader
    return ImageReader(buffer)


@app.route("/certificate/verify/<verification_id>")
def certificate_verify(verification_id):
    conn = get_db_connection()
    cert = conn.execute("SELECT c.*, u.full_name, m.title FROM training_certificates c JOIN users u ON u.id = c.user_id JOIN training_modules m ON m.code = c.module_code WHERE c.verification_id = ?", (verification_id,)).fetchone()
    conn.close()
    return render_template("certificate_verify.html", cert=dict(cert) if cert else None, verification_id=verification_id)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
