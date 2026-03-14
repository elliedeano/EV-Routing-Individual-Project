import math

from backend.routing.services.charger_provider import get_chargers_near_route

def route_segment_distance(lat1, lon1, lat2, lon2):
    radius_km = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def trip_simulation(route, car_specs, soc_percent, min_buffer_km=20):
    wh_per_km = car_specs["wh_per_km"]
    battery_kwh = car_specs["battery_kwh"]

    usable_wh = battery_kwh * 1000 * (soc_percent / 100)
    remaining_km = usable_wh / wh_per_km

    distance = 0.0
    last = route[0]
    stops = []

    for point in route[1:]:
        segment = route_segment_distance(last[0], last[1], point[0], point[1])
        distance += segment
        remaining_km -= segment

        if remaining_km < min_buffer_km:
            chargers = get_chargers_near_route([point])
            stops.append(
                {
                    "at_km": distance,
                    "location": point,
                    "chargers": chargers[:3],
                }
            )
            remaining_km = battery_kwh * 1000 / wh_per_km

        last = point

    return stops, distance
