import math


def haversine_distance_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def assess_emergency_scenario(ship, emergency_type, weather, ships, ports):
    affected_lat = float(ship["latitude"])
    affected_lon = float(ship["longitude"])
    nearby_vessels = []
    for candidate in ships:
        if candidate["vessel_id"] == ship["vessel_id"]:
            continue
        distance_km = haversine_distance_km(affected_lat, affected_lon, float(candidate["latitude"]), float(candidate["longitude"]))
        distance_nm = distance_km / 1.852
        arrival_speed = max(8.0, float(candidate["speed_knots"]))
        arrival_hours = (distance_nm / arrival_speed) * 1.6
        availability = "Available" if candidate["status"] not in ["Docked", "Port"] else "Limited"
        capability_bonus = {
            "Container": 15,
            "Bulk Carrier": 10,
            "Tanker": 20,
            "RoRo": 12,
        }.get(candidate["vessel_type"], 8)
        weather_penalty = {"Calm": 1.0, "Moderate": 1.2, "Rough": 1.4}.get(weather, 1.0)
        suitability = max(0, 90 - distance_nm / 3.5 + capability_bonus + (10 if availability == "Available" else 0) - (weather_penalty * 10))
        nearby_vessels.append({
            "vessel_id": candidate["vessel_id"],
            "name": candidate["name"],
            "distance_nm": round(distance_nm, 1),
            "arrival_hours": round(arrival_hours, 1),
            "capability": candidate["vessel_type"],
            "availability": availability,
            "suitability_score": round(suitability, 1),
        })
    nearby_vessels.sort(key=lambda item: (-item["suitability_score"], item["distance_nm"]))

    ranked_ports = []
    for port in ports:
        distance_km = haversine_distance_km(affected_lat, affected_lon, float(port["latitude"]), float(port["longitude"]))
        distance_nm = distance_km / 1.852
        service_bonus = 10 if "Fire" in (port["emergency_services"] or "") or "Emergency" in (port["emergency_services"] or "") else 3
        suitability = max(0, 100 - distance_nm / 4.0 + service_bonus + (15 if port["shore_power_available"] else 0))
        ranked_ports.append({
            "port_name": port["name"],
            "distance_nm": round(distance_nm, 1),
            "accessibility": port["accessibility"],
            "emergency_services": port["emergency_services"],
            "shore_power": bool(port["shore_power_available"]),
            "suitability_score": round(suitability, 1),
        })
    ranked_ports.sort(key=lambda item: (-item["suitability_score"], item["distance_nm"]))

    return {
        "selected_ship": ship["name"],
        "emergency_type": emergency_type,
        "weather": weather,
        "remaining_fuel_tons": round(float(ship["current_fuel_tons"]), 2),
        "recommended_vessels": nearby_vessels[:3],
        "recommended_ports": ranked_ports[:3],
        "summary": "Simulated decision support only. This recommendation uses estimated vessel capability, distance, weather conditions and available fuel reserve.",
    }
