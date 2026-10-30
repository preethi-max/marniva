import os
import json

os.remove("database/database.db") if os.path.exists("database/database.db") else None

from app import app

client = app.test_client()
print("login_get", client.get("/login").status_code)
print("login_post", client.post("/login", data={"username": "admin", "password": "marinva123"}, follow_redirects=False).status_code)
print("dashboard", client.get("/dashboard").status_code)
print("fleet", client.get("/fleet").status_code)
print("fuel", client.get("/fuel").status_code)
print("emergency", client.get("/emergency").status_code)
print("training", client.get("/training").status_code)
print("reports", client.get("/reports").status_code)
print("profile", client.get("/profile").status_code)
print("fuel_api", client.get("/api/fuel-analysis?ship_id=1").status_code)
print("fleet_api", client.post("/api/fleet-sim", json={"ship_id": 1, "speed": 17.5, "distance": 6500, "weather": "Moderate", "fuel_type": "VLSFO", "start_port": "Port Klang", "destination_port": "Rotterdam"}).status_code)
print("emergency_api", client.post("/api/emergency-sim", json={"ship_id": 1, "emergency_type": "Engine failure", "weather": "Moderate"}).status_code)
print("training_api", client.get("/api/training-modules").status_code)
