import math
from backend.routing.services.ocm_retrieval import ocm_retrieval

#calculates distance between two points using harvesine formula.
def haversine_formula(lat1, lon1, lat2, lon2):
    earths_radius_km = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(delta_lambda / 2) ** 2
    result = 2 * earths_radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return result


#Simulates car driving to simulate battery usage. 
def trip_range_simulation(route, car_specs, soc_percent, min_buffer_km=15):
    wh_per_km = car_specs["wh_per_km"]
    battery_kwh = car_specs["battery_kwh"]
    usable_wh = battery_kwh * 1000 * (soc_percent / 100)
    remaining_km = usable_wh / wh_per_km
    distance = 0.0
    last = route[0]
    stops = []

    for point in route[1:]:
        dist_between_points = haversine_formula(last[0], last[1], point[0], point[1])
        distance += dist_between_points
        remaining_km -= dist_between_points
        if remaining_km < min_buffer_km:
            chargers = ocm_retrieval([point])
            stops.append({"at_km": distance, "location": point, "chargers": chargers[:3],})
            remaining_km = battery_kwh * 1000 / wh_per_km
        last = point
    return stops, distance
