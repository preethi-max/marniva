import os
import sqlite3
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

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
    if "user" not in session:
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


def simple_dashboard_data():
    conn = get_db_connection()
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
    if not os.path.exists(DB_PATH):
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
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password),
        ).fetchone()
        conn.close()
        if user:
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


@app.route("/dashboard")
def dashboard():
    redirect_result = require_login()
    if redirect_result is not None:
        return redirect_result
    data = simple_dashboard_data()
    conn = get_db_connection()
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
    return jsonify(simple_dashboard_data())


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


@app.route("/api/training-submit", methods=["POST"])
def api_training_submit():
    payload = request.get_json(silent=True) or request.form
    crew_id = payload.get("crew_id")
    module_code = payload.get("module_code")
    answer = payload.get("answer")
    conn = get_db_connection()
    module = conn.execute(
        "SELECT * FROM training_modules WHERE code = ?",
        (module_code,),
    ).fetchone()
    if not module:
        conn.close()
        return jsonify({"error": "Module not found."}), 404

    result = evaluate_training_module(module, answer)
    recommendation = get_training_recommendation(module, result["score"])
    conn.execute(
        "INSERT INTO training_assessments (crew_id, module_code, score, passed, weak_area, recommendation) VALUES (?, ?, ?, ?, ?, ?)",
        (
            crew_id,
            module_code,
            result["score"],
            1 if result["passed"] else 0,
            result["weak_area"],
            recommendation,
        ),
    )
    conn.execute(
        "INSERT INTO training_progress (crew_id, module_code, status, score, completed_at, next_recommendation) VALUES (?, ?, ?, ?, ?, ?)",
        (
            crew_id,
            module_code,
            "Completed" if result["passed"] else "Needs review",
            result["score"],
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            recommendation,
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({
        "score": result["score"],
        "passed": result["passed"],
        "weak_area": result["weak_area"],
        "recommendation": recommendation,
        "certificate_eligible": result["score"] >= 80,
    })


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
