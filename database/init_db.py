import sqlite3
from pathlib import Path

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
    conn.commit()
    conn.close()


def seed_data(cursor):
    user_rows = [
        ("admin", "marinva123", "Asha Raman", "Operator",),
        ("captain", "marinva123", "Nadia Iqbal", "Master",),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
        user_rows,
    )

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
