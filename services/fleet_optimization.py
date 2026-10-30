def compare_route_alternatives(ship, weather, distance, speed, fuel_type, start_port, destination_port):
    weather_factor = {"Calm": 0.94, "Moderate": 1.08, "Rough": 1.2, "Storm": 1.35}.get(weather, 1.0)
    speed_factor = 1.0 + max(0, (speed - ship["speed_knots"]) / 18.0)
    alternatives = []
    base_speed_values = [max(10, speed * 0.9), speed, min(22, speed * 1.1)]
    for index, test_speed in enumerate(base_speed_values):
        fuel_consumed = distance * (0.00092 + (test_speed / 200.0)) * weather_factor * speed_factor
        emissions = fuel_consumed * ({"VLSFO": 3.11, "HFO": 3.19, "LSFO": 3.05, "Marine Gas Oil": 2.97}.get(fuel_type, 3.1))
        cost = fuel_consumed * 360.0 * ({"VLSFO": 1.0, "HFO": 0.96, "LSFO": 0.98, "Marine Gas Oil": 1.03}.get(fuel_type, 1.0))
        alt = {
            "label": f"Alternative {index + 1}",
            "start_port": start_port,
            "destination_port": destination_port,
            "speed": round(test_speed, 1),
            "distance": round(distance, 1),
            "weather": weather,
            "fuel_type": fuel_type,
            "fuel_consumed_tons": round(fuel_consumed, 2),
            "emissions_tco2": round(emissions, 2),
            "estimated_cost_usd": round(cost, 2),
            "route_efficiency": round(100 - (abs(test_speed - ship["speed_knots"]) * 4.5), 1),
        }
        alternatives.append(alt)
    alternatives.sort(key=lambda item: (item["fuel_consumed_tons"], item["emissions_tco2"]))
    return alternatives
