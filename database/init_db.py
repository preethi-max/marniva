import sqlite3
import json
from pathlib import Path
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent / "database.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            vessel_id TEXT UNIQUE NOT NULL,
            vessel_type TEXT NOT NULL,
            status TEXT NOT NULL,
            fuel_type TEXT NOT NULL,
            fuel_capacity_tons REAL NOT NULL,
            current_fuel_tons REAL NOT NULL,
            speed_knots REAL NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            destination_port TEXT,
            weather_condition TEXT,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS fuel_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ship_id INTEGER NOT NULL,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            fuel_consumed_tons REAL NOT NULL,
            predicted_consumption_tons REAL NOT NULL,
            actual_consumption_tons REAL NOT NULL,
            cost_usd REAL NOT NULL,
            FOREIGN KEY (ship_id) REFERENCES ships(id)
        );

        CREATE TABLE IF NOT EXISTS voyage_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ship_id INTEGER NOT NULL,
            start_port TEXT NOT NULL,
            destination_port TEXT NOT NULL,
            distance_nm REAL NOT NULL,
            speed_knots REAL NOT NULL,
            fuel_type TEXT NOT NULL,
            weather_condition TEXT NOT NULL,
            predicted_fuel_tons REAL NOT NULL,
            actual_fuel_tons REAL NOT NULL,
            emissions_tco2 REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ship_id) REFERENCES ships(id)
        );

        CREATE TABLE IF NOT EXISTS port_information (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            available_fuels TEXT NOT NULL,
            shore_power_available INTEGER NOT NULL,
            emergency_services TEXT,
            accessibility TEXT,
            fuel_cost_multiplier REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS fuel_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            port_id INTEGER NOT NULL,
            fuel_type TEXT NOT NULL,
            quantity_tons REAL NOT NULL,
            compatible INTEGER NOT NULL,
            availability_status TEXT NOT NULL,
            FOREIGN KEY (port_id) REFERENCES port_information(id)
        );

        CREATE TABLE IF NOT EXISTS emission_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ship_id INTEGER NOT NULL,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            total_co2_tons REAL NOT NULL,
            carbon_budget_pct REAL NOT NULL,
            FOREIGN KEY (ship_id) REFERENCES ships(id)
        );

        CREATE TABLE IF NOT EXISTS emergency_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ship_id INTEGER NOT NULL,
            emergency_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            triggered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            weather_condition TEXT,
            remaining_fuel_tons REAL,
            FOREIGN KEY (ship_id) REFERENCES ships(id)
        );

        CREATE TABLE IF NOT EXISTS nearby_vessels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ship_id INTEGER NOT NULL,
            target_ship_id INTEGER NOT NULL,
            distance_nm REAL NOT NULL,
            capability TEXT NOT NULL,
            availability TEXT NOT NULL,
            suitability_score REAL NOT NULL,
            FOREIGN KEY (ship_id) REFERENCES ships(id),
            FOREIGN KEY (target_ship_id) REFERENCES ships(id)
        );

        CREATE TABLE IF NOT EXISTS training_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            scenario TEXT NOT NULL,
            description TEXT NOT NULL,
            language TEXT NOT NULL,
            question TEXT NOT NULL,
            options TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            recommended_equipment TEXT,
            risk_area TEXT,
            fuel_type TEXT
        );

        CREATE TABLE IF NOT EXISTS crew_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crew_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            language TEXT NOT NULL,
            ship_id INTEGER,
            role TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ship_id) REFERENCES ships(id)
        );

        CREATE TABLE IF NOT EXISTS training_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crew_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            score REAL NOT NULL,
            passed INTEGER NOT NULL,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            weak_area TEXT,
            recommendation TEXT,
            FOREIGN KEY (crew_id) REFERENCES crew_profiles(crew_id)
        );

        CREATE TABLE IF NOT EXISTS training_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crew_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            status TEXT NOT NULL,
            score REAL,
            completed_at TEXT,
            next_recommendation TEXT,
            FOREIGN KEY (crew_id) REFERENCES crew_profiles(crew_id)
        );
        """
    )

    seed_data(cursor)
    ensure_training_schema(conn)
    conn.commit()
    conn.close()


def ensure_training_schema(conn):
    cursor = conn.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS training_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            crew_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            submitted_at TEXT,
            elapsed_seconds INTEGER DEFAULT 0,
            status TEXT DEFAULT 'In progress'
        );
        CREATE TABLE IF NOT EXISTS training_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            action_key TEXT NOT NULL,
            selected_value TEXT,
            correct INTEGER NOT NULL DEFAULT 0,
            elapsed_seconds INTEGER DEFAULT 0,
            feedback TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS assessment_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            question_key TEXT NOT NULL,
            selected_answer TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            is_correct INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS assessment_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL UNIQUE,
            crew_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            score REAL NOT NULL,
            procedure_score REAL NOT NULL DEFAULT 0,
            speed_score REAL NOT NULL DEFAULT 0,
            mistake_count INTEGER NOT NULL DEFAULT 0,
            passed INTEGER NOT NULL DEFAULT 0,
            weak_area TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS training_certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            verification_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            crew_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            score REAL NOT NULL,
            completion_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS assessment_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            role_key TEXT NOT NULL DEFAULT 'common',
            stage TEXT NOT NULL,
            prompt TEXT NOT NULL,
            options TEXT NOT NULL,
            correct_option TEXT NOT NULL,
            marks INTEGER NOT NULL DEFAULT 20,
            feedback TEXT NOT NULL,
            weak_area TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS assessment_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            crew_id TEXT NOT NULL,
            category TEXT NOT NULL,
            role_key TEXT NOT NULL,
            score REAL NOT NULL,
            passed INTEGER NOT NULL DEFAULT 0,
            elapsed_seconds INTEGER NOT NULL DEFAULT 0,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS assessment_attempt_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL,
            question_code TEXT NOT NULL,
            selected_option TEXT NOT NULL,
            correct_option TEXT NOT NULL,
            is_correct INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (attempt_id) REFERENCES assessment_attempts(id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_employee_id ON users(employee_id) WHERE employee_id IS NOT NULL AND employee_id <> '';
        CREATE UNIQUE INDEX IF NOT EXISTS idx_crew_user ON crew_profiles(user_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_crew_profile_id ON crew_profiles(crew_id);
        """
    )

    for statement in (
        "ALTER TABLE users ADD COLUMN password_hash TEXT",
        "ALTER TABLE users ADD COLUMN crew_id TEXT",
        "ALTER TABLE users ADD COLUMN employee_id TEXT",
        "ALTER TABLE crew_profiles ADD COLUMN user_id INTEGER",
        "ALTER TABLE crew_profiles ADD COLUMN responsibilities TEXT NOT NULL DEFAULT ''",
    ):
        try:
            cursor.execute(statement)
        except sqlite3.OperationalError:
            pass

    role_questions = {
        "captain": [
            ("cap-flood", "Navigation flooding decision", ["Raise the alarm, secure watertight integrity and inform command" , "Increase speed and continue"], "Raise the alarm, secure watertight integrity and inform command", "Command flooding control"),
            ("cap-evac", "Crew evacuation coordination", ["Account crew, follow alternate routes and command muster control", "Board lifeboats without headcount"], "Account crew, follow alternate routes and command muster control", "Evacuation coordination")
        ],
        "engineer": [
            ("eng-fire", "Machinery fire isolation", ["Stop fuel and ventilation, raise alarm and use approved suppression", "Open doors to cool the machinery"], "Stop fuel and ventilation, raise alarm and use approved suppression", "Machinery fire isolation"),
            ("eng-fuel", "Fuel leakage containment", ["Stop transfer, isolate the source and maintain ignition control", "Continue operations and monitor"] , "Stop transfer, isolate the source and maintain ignition control", "Fuel leakage control")
        ],
        "crew": [
            ("crew-cargo", "Cargo handling hazard", ["Stop the operation and report the unstable load", "Continue if crane capacity has margin"], "Stop the operation and report the unstable load", "Cargo safety"),
            ("crew-mob", "Man-overboard action", ["Sound alarm, mark position and deploy approved assistance", "Search alone without informing bridge"], "Sound alarm, mark position and deploy approved assistance", "Man overboard response")
        ],
        "deck officer": [
            ("deck-watch", "Deck watch hazard", ["Secure the area and report the unsafe condition", "Allow work while monitoring visually"], "Secure the area and report the unsafe condition", "Deck hazard control"),
            ("deck-ppe", "Deck PPE selection", ["Use task-assessed helmet, gloves, footwear and lifejacket when required", "Use only sunglasses and gloves"], "Use task-assessed helmet, gloves, footwear and lifejacket when required", "Deck PPE")
        ],
        "electrical engineer": [
            ("elec-short", "Electrical short circuit", ["Isolate power and use approved electrical procedures", "Reset repeatedly until the breaker holds"], "Isolate power and use approved electrical procedures", "Electrical isolation"),
            ("elec-fire", "Electrical fire response", ["Disconnect power and use approved clean-agent or CO2 suppression", "Apply water to energized equipment"], "Disconnect power and use approved clean-agent or CO2 suppression", "Electrical fire response")
        ],
        "safety officer": [
            ("safe-risk", "Risk assessment action", ["Stop the activity, assess controls and escalate", "Continue because controls are normally sufficient"], "Stop the activity, assess controls and escalate", "Hazard assessment"),
            ("safe-ppe", "PPE compliance check", ["Correct the breach and verify task-specific protection", "Record it but allow work to continue"], "Correct the breach and verify task-specific protection", "PPE compliance")
        ]
    }
    common_questions = [
        ("common-flood", "Common flooding response", ["Raise alarm, preserve watertight integrity and report compartment", "Open adjacent doors"], "Raise alarm, preserve watertight integrity and report compartment", "Flooding response"),
        ("common-muster", "Common evacuation and muster", ["Use a safe route, report to muster and account for crew", "Collect belongings before reporting"], "Use a safe route, report to muster and account for crew", "Muster accountability"),
        ("common-life", "Life jacket and lifeboat safety", ["Follow command, inspect the lifejacket and enter only when ordered", "Board before the headcount"], "Follow command, inspect the lifejacket and enter only when ordered", "Life-saving appliance use"),
        ("common-comm", "Emergency communication", ["Use agreed alarm and radio channels with clear location and need", "Use informal messages only"], "Use agreed alarm and radio channels with clear location and need", "Emergency communication"),
        ("common-fire-gas", "Fire and gas alarm response", ["Raise alarm, isolate energy or source and move to a safe zone", "Investigate without protection"], "Raise alarm, isolate energy or source and move to a safe zone", "Fire and gas response")
    ]
    def insert_assessment(code, category, role_key, prompt, options, correct, marks=25, weak="Decision-making"):
        cursor.execute("""INSERT INTO assessment_questions
            (code, category, role_key, stage, prompt, options, correct_option, marks, feedback, weak_area)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET category=excluded.category, role_key=excluded.role_key, prompt=excluded.prompt, options=excluded.options, correct_option=excluded.correct_option, feedback=excluded.feedback, weak_area=excluded.weak_area""",
            (code, category, role_key, prompt, prompt, json.dumps(options), correct, marks, "Follow the vessel-approved emergency plan and report clearly.", weak))
    for role_key, questions in role_questions.items():
        for index, (code, stage, options, correct, weak) in enumerate(questions):
            insert_assessment(code, "individual", role_key, stage + " — choose the safest action.", options, correct, 50, weak)
    for code, stage, options, correct, weak in common_questions:
        insert_assessment(code, "common", "common", stage + " — choose the safest action.", options, correct, 20, weak)

    for user in cursor.execute("SELECT id, password FROM users WHERE password_hash IS NULL"):
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(user["password"]), user["id"]))


def seed_data(cursor):
    user_rows = [
        ("admin", "marinva123", "Asha Raman", "Operator",),
        ("captain", "marinva123", "Nadia Iqbal", "Master",),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
        user_rows,
    )
    captain_user = cursor.execute("SELECT id FROM users WHERE username = 'captain'").fetchone()
    if captain_user:
        cursor.execute("UPDATE users SET crew_id = COALESCE(crew_id, 'CAPTAIN-SEED') WHERE id = ?", (captain_user[0],))
        cursor.execute("INSERT OR IGNORE INTO crew_profiles (crew_id, full_name, language, ship_id, role, user_id, responsibilities) VALUES ('CAPTAIN-SEED', 'Nadia Iqbal', 'English', 1, 'Captain', ?, 'Navigation command, flooding decisions, evacuation coordination')", (captain_user[0],))

    ship_rows = [
        ("MV Atlas", "MAR-101", "Container", "At Sea", "VLSFO", 2600, 1780, 17.5, 24.6, 69.7, "Rotterdam", "Moderate", 1),
        ("MV Horizon", "MAR-205", "Bulk Carrier", "Docked", "HFO", 3300, 2400, 15.1, 32.8, 118.2, "Singapore", "Calm", 1),
        ("MV Neptune", "MAR-323", "Tanker", "At Sea", "LSFO", 4300, 3150, 14.7, 21.3, 88.4, "Dubai", "Rough", 1),
        ("MV Solace", "MAR-418", "RoRo", "Port", "Marine Gas Oil", 1900, 970, 16.2, 35.4, 127.6, "Hamburg", "Calm", 1),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO ships (name, vessel_id, vessel_type, status, fuel_type, fuel_capacity_tons, current_fuel_tons, speed_knots, latitude, longitude, destination_port, weather_condition, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ship_rows,
    )

    fuel_record_rows = [
        (1, 82.0, 68.0, 77.0, 2100),
        (2, 66.0, 52.0, 58.0, 1800),
        (3, 94.0, 80.0, 88.0, 2550),
        (4, 48.0, 43.0, 45.0, 1300),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO fuel_records (ship_id, fuel_consumed_tons, predicted_consumption_tons, actual_consumption_tons, cost_usd) VALUES (?, ?, ?, ?, ?)",
        fuel_record_rows,
    )

    voyage_rows = [
        (1, "Port Klang", "Rotterdam", 6500, 17.5, "VLSFO", "Moderate", 620, 600, 1480),
        (2, "Busan", "Singapore", 4300, 15.1, "HFO", "Calm", 410, 390, 980),
        (3, "Jeddah", "Dubai", 5100, 14.7, "LSFO", "Rough", 560, 540, 1300),
        (4, "Oslo", "Hamburg", 3900, 16.2, "Marine Gas Oil", "Calm", 330, 310, 740),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO voyage_records (ship_id, start_port, destination_port, distance_nm, speed_knots, fuel_type, weather_condition, predicted_fuel_tons, actual_fuel_tons, emissions_tco2) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        voyage_rows,
    )

    port_rows = [
        ("Rotterdam", "Netherlands", 51.95, 4.05, "VLSFO,LSFO,MGO", 1, "Pilotage, Fire Response", "High", 1.08),
        ("Singapore", "Singapore", 1.35, 103.88, "LSFO,VLSFO,MGO", 1, "Emergency Tug, Fire", "High", 1.12),
        ("Dubai", "UAE", 25.27, 55.29, "LSFO,MGO, LNG", 1, "Port Safety, Hazmat", "Medium", 1.1),
        ("Hamburg", "Germany", 53.55, 9.99, "VLSFO,LSFO,MGO", 1, "Emergency Response", "High", 1.06),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO port_information (name, country, latitude, longitude, available_fuels, shore_power_available, emergency_services, accessibility, fuel_cost_multiplier) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        port_rows,
    )

    fuel_availability_rows = [
        (1, "VLSFO", 680, 1, "Available"),
        (1, "LSFO", 520, 1, "Available"),
        (2, "LSFO", 760, 1, "Available"),
        (2, "HFO", 320, 1, "Limited"),
        (3, "LSFO", 600, 1, "Available"),
        (4, "Marine Gas Oil", 420, 1, "Available"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO fuel_availability (port_id, fuel_type, quantity_tons, compatible, availability_status) VALUES (?, ?, ?, ?, ?)",
        fuel_availability_rows,
    )

    emission_rows = [
        (1, "2026-10-01", 2420.5, 68.4),
        (2, "2026-10-01", 2650.2, 72.2),
        (3, "2026-10-01", 2875.6, 74.1),
        (4, "2026-10-01", 1790.4, 52.0),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO emission_records (ship_id, recorded_at, total_co2_tons, carbon_budget_pct) VALUES (?, ?, ?, ?)",
        emission_rows,
    )

    emergency_rows = [
        (1, "Engine failure", "High", "Monitoring", "Moderate", 320),
        (2, "Gas leakage", "Critical", "Active", "Calm", 410),
        (3, "Flooding", "High", "Monitoring", "Rough", 270),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO emergency_alerts (ship_id, emergency_type, severity, status, weather_condition, remaining_fuel_tons) VALUES (?, ?, ?, ?, ?, ?)",
        emergency_rows,
    )

    nearby_rows = [
        (1, 2, 188.0, "Tug assistance", "Available", 82.5),
        (1, 3, 240.0, "Fire response", "Available", 75.3),
        (1, 4, 340.0, "Salvage support", "Delayed", 54.8),
        (2, 1, 188.0, "Tug assistance", "Available", 81.2),
        (2, 3, 196.0, "Safety escort", "Available", 79.1),
        (3, 1, 240.0, "Fire response", "Available", 88.1),
        (3, 4, 260.0, "Medical support", "Available", 77.0),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO nearby_vessels (ship_id, target_ship_id, distance_nm, capability, availability, suitability_score) VALUES (?, ?, ?, ?, ?, ?)",
        nearby_rows,
    )

    module_rows = [
        ("fire-engine", "Engine-room fire", "Fire", "Respond to a compartment fire alarm and identify correct safety equipment.", "English", "Which action is most suitable for an engine-room fire alarm?", "['Isolate fuel and electrical power before firefighting','Continue normal engine speed to reduce smoke','Open ventilation to clear smoke','Use water spray on a live electrical panel']", "Isolate fuel and electrical power before firefighting", "Fire suppression", "Fire suppression", "VLSFO"),
        ("gas-leak", "Gas leakage", "Gas", "Recognize hazardous gas conditions and choose safe controls.", "English", "What should the crew do first during a suspected gas leak?", "['Stop ventilation and isolate the leak source','Ignore it if it is minor','Turn on extra machinery to dilute gas','Continue cargo discharge']", "Stop ventilation and isolate the leak source", "Gas containment", "Gas containment", "LNG"),
        ("evacuation", "Emergency evacuation", "Evacuation", "Choose the right emergency response and life-saving equipment.", "English", "Where should crew assemble during an evacuation?", "['Muster station with headcount and safety officer','The engine room','The galley','On the main deck near hot work']", "Muster station with headcount and safety officer", "Life safety", "Life safety", "All"),
        ("ppe", "PPE identification", "PPE", "Identify personal protective equipment required for hazardous tasks.", "English", "Which item is required before entering a chemical spill area?", "['Chemical-resistant gloves and goggles','A cap only','Regular footwear only','No PPE required']", "Chemical-resistant gloves and goggles", "PPE compliance", "PPE compliance", "All"),
        ("muster", "Muster station", "Muster", "Identify proper escape route and safety muster points.", "English", "What is the key purpose of a muster station?", "['To account for crew and coordinate evacuation','To store spare fuel','To load cargo','To start the generator']", "To account for crew and coordinate evacuation", "Escape route", "Escape route", "All"),
        ("fire-engine-hi", "Engine-room fire", "Fire", "Respuesta rápida a alarma de incendio en sala de máquinas.", "Hindi", "¿Cuál es la mejor acción ante una alarma de incendio en la sala de máquinas?", "['Aislar combustible y energía antes de combatir incendios','Mantener velocidad normal del motor','Abrir ventilación para limpiar humo','Usar agua sobre un panel eléctrico activo']", "Aislar combustible y energía antes de combatir incendios", "Fire suppression", "Fire suppression", "VLSFO"),
        ("engine-fire", "Engine-room Fire Safety", "Engine fire", "Identify fire risks, isolate energy and select the correct fire response.", "English", "What is the first safe action when an engine-room fire alarm sounds?", "['Raise the alarm and stop fuel and electrical supply','Open ventilation and doors','Attempt to restart engines','Use water on energized equipment']", "Raise the alarm and stop fuel and electrical supply", "CO2 system", "Fire isolation", "VLSFO"),
        ("gas-toxic", "Gas Leakage & Toxic Exposure", "Gas hazard", "Recognize gas warnings and select safe isolation and PPE actions.", "English", "What should the crew do first when toxic gas is suspected?", "['Leave the area and raise alarm upwind','Enter without breathing protection','Increase ventilation toward the crew','Start cargo discharge']", "Leave the area and raise alarm upwind", "SCBA and gas detector", "Toxic exposure", "LNG"),
        ("ship-flooding", "Ship Flooding & Water Ingress", "Flooding", "Find the water ingress point and coordinate a controlled response.", "English", "What is the safest immediate response to confirmed flooding?", "['Raise alarm, isolate the space and start dewatering planning','Open more doors to inspect','Continue transit at full speed','Pump without finding the source']", "Raise alarm, isolate the space and start dewatering planning", "Pumps and plugs", "Water ingress", "All"),
        ("emergency-muster", "Emergency Evacuation & Muster", "Evacuation", "Follow escape-route and muster procedures safely.", "English", "Where should crew assemble during an evacuation?", "['At the designated muster station for headcount','Near the engine room exit','At the cargo hold','In the accommodation corridor']", "At the designated muster station for headcount", "Life jacket and immersion suit", "Muster procedure", "All"),
        ("marine-ppe", "Personal Protective Equipment", "PPE", "Choose task-specific PPE and inspect it before use.", "English", "Which equipment is suitable for entering a toxic gas atmosphere?", "['Approved SCBA, gloves and eye protection','Ordinary safety helmet only','No protection below deck','Cotton gloves only']", "Approved SCBA, gloves and eye protection", "SCBA and PPE kit", "PPE compliance", "All"),
        ("alternative-fuels", "Alternative Marine Fuel Handling", "Fuel safety", "Apply isolation, leak detection and PPE controls to alternative fuels.", "English", "Before an alternative-fuel transfer, what should crew prioritize?", "['Confirm compatibility, bonding, leak detection and emergency isolation','Open transfer valves immediately','Bypass alarm systems','Vent vapors toward accommodation']", "Confirm compatibility, bonding, leak detection and emergency isolation", "Gas detector and spill kit", "Fuel handling", "LNG/methanol/ammonia"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO training_modules (code, title, scenario, description, language, question, options, correct_answer, recommended_equipment, risk_area, fuel_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        module_rows,
    )

    crew_rows = [
        ("CREW-1001", "Rohan Singh", "English", 1, "Engineer"),
        ("CREW-1002", "Priya Nair", "Hindi", 2, "Safety Officer"),
        ("CREW-1003", "Amit Verma", "English", 3, "Deck Officer"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO crew_profiles (crew_id, full_name, language, ship_id, role) VALUES (?, ?, ?, ?, ?)",
        crew_rows,
    )

    assessment_rows = [
        ("CREW-1001", "fire-engine", 85.0, 1, "Fire response", "Retake the fire safety drill on the simulated engine-room exercise"),
        ("CREW-1002", "ppe", 70.0, 1, "PPE compliance", "Review the dangerous goods and PPE checklist"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO training_assessments (crew_id, module_code, score, passed, weak_area, recommendation) VALUES (?, ?, ?, ?, ?, ?)",
        assessment_rows,
    )

    progress_rows = [
        ("CREW-1001", "fire-engine", "Completed", 85.0, "2026-10-15", "Repeat an engine-room drill every 30 days"),
        ("CREW-1002", "ppe", "In progress", 70.0, "2026-10-20", "Focus on gas hazard PPE identification"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO training_progress (crew_id, module_code, status, score, completed_at, next_recommendation) VALUES (?, ?, ?, ?, ?, ?)",
        progress_rows,
    )


if __name__ == "__main__":
    init_db()
    print(f"SQLite database initialized at: {DB_PATH}")
