import math

from sklearn.linear_model import LinearRegression


def build_prediction_model():
    features = [
        [14.0, 1200, 1.0, 2.0, 42.0],
        [15.5, 1800, 1.0, 2.0, 56.0],
        [17.0, 2400, 1.2, 2.0, 60.0],
        [13.5, 1100, 1.2, 2.0, 48.0],
        [18.0, 2600, 1.5, 3.0, 72.0],
        [16.0, 2100, 1.5, 3.0, 68.0],
        [15.0, 1500, 1.0, 1.0, 40.0],
        [17.5, 2250, 1.4, 2.0, 62.0],
        [14.8, 1700, 1.3, 2.0, 57.0],
        [19.0, 3000, 1.8, 3.0, 74.0],
    ]
    targets = [110.0, 160.0, 205.0, 125.0, 240.0, 185.0, 130.0, 200.0, 150.0, 260.0]
    model = LinearRegression()
    model.fit(features, targets)
    score = model.score(features, targets)
    return {"r2": round(float(score), 3), "model": model}


def predict_fuel_consumption(ship, distance=2500, speed=None, weather="Calm"):
    model_data = build_prediction_model()
    model = model_data["model"]
    ship_type_scale = {"Container": 2.0, "Bulk Carrier": 1.0, "Tanker": 3.0, "RoRo": 1.5}
    weather_score = {"Calm": 1.0, "Moderate": 1.3, "Rough": 1.6, "Storm": 1.9}.get(weather, 1.1)
    performance_speed = speed if speed is not None else ship["speed_knots"]
    ship_score = ship_type_scale.get(ship["vessel_type"], 2.0)
    historical_usage = max(30, float(ship["current_fuel_tons"]) / 8.0)
    raw_prediction = model.predict([[performance_speed, distance, weather_score, ship_score, historical_usage]])[0]
    predicted = max(40.0, float(raw_prediction))
    return {
        "predicted_fuel_tons": round(float(predicted), 2),
        "actual_usage_tons": round(float(ship["current_fuel_tons"]) / 10.0, 2),
        "model_r2": model_data["r2"],
        "weather_factor": weather_score,
    }


def evaluate_fuel_status(ship, predicted_fuel_tons, planned_distance):
    reserve_ratio = float(ship["current_fuel_tons"]) / float(ship["fuel_capacity_tons"])
    required_for_route = predicted_fuel_tons * (planned_distance / 2500.0)
    sufficient = float(ship["current_fuel_tons"]) >= required_for_route * 1.12
    return {
        "reserve_ratio": round(reserve_ratio, 3),
        "required_tons": round(required_for_route, 2),
        "remaining_range_nm": round((float(ship["current_fuel_tons"]) / max(predicted_fuel_tons / 2500.0, 1.0)) * 100.0, 2),
        "sufficient_for_voyage": sufficient,
        "warning": "Low-fuel reserve: voyage would exceed available fuel on board." if not sufficient else "Adequate fuel reserve for the planned voyage.",
    }
