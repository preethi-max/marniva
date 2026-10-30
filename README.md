# MARINVA Prototype

MARINVA is a Python + Flask prototype for a maritime sustainability, fuel intelligence, emergency coordination, and crew safety training platform.

## Features
- Green fleet and carbon intelligence overview
- AI-assisted fuel prediction and compatibility checks
- Simulated emergency response recommendation engine
- Adaptive crew training dashboard with assessment scoring
- SQLite-backed shared vessel and operational data

## Project structure
- app.py — Flask application and API routes
- database/init_db.py — SQLite schema and seeded demonstration data
- services/ — business logic for fleet, fuel, emergency and training modules
- templates/ — HTML pages for login, dashboard and module views
- static/css/style.css — professional maritime theme and responsive layout
- static/js/main.js — page interactions and frontend logic

## Setup on Windows PowerShell
1. Open PowerShell in the project folder.
2. Create a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Initialize the SQLite database with sample data:
   ```powershell
   python database/init_db.py
   ```
5. Run the app:
   ```powershell
   python app.py
   ```
6. Open http://127.0.0.1:5000

## Demo login
- Username: admin
- Password: marinva123

## Notes
- All operational, route and emergency values are simulated demonstration data.
- The prototype is intended for hackathon demonstration and decision-support testing, not live operational dispatch.
