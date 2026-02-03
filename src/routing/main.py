from car_specs import get_car_specs
from load_and_estimate_range import load_and_estimate_range
import requests
import polyline
import math
import csv
from pathlib import Path
from ors_config import ORS_API_KEY
from ocm_config import OCM_API_KEY


# -------------------------
# GEO + ROUTING
# -------------------------
def geocode_postcode(postcode):
    url = "https://api.openrouteservice.org/geocode/search"
    params = {
        "api_key": ORS_API_KEY,
        "text": postcode,
        "boundary.country": "GB"
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    features = r.json().get("features", [])
    if not features:
        raise ValueError(f"No geocoding result for {postcode}")
    lon, lat = features[0]["geometry"]["coordinates"]
    return lat, lon


def get_route(start_coords, dest_coords):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_API_KEY}
    body = {
        "coordinates": [
            [start_coords[1], start_coords[0]],
            [dest_coords[1], dest_coords[0]]
        ]
    }
    r = requests.post(url, json=body, headers=headers)
    r.raise_for_status()
    data = r.json()
    if not data.get("routes"):
        raise RuntimeError("ORS returned no route")
    return polyline.decode(data["routes"][0]["geometry"])


# -------------------------
# CHARGERS
# -------------------------
def get_chargers_near_route(route_coords, max_results=6, distance_km=5):
    chargers = []
    sample_points = [route_coords[0], route_coords[-1]]

    if len(route_coords) > 8:
        step = max(1, len(route_coords) // 6)
        sample_points += route_coords[1:-1:step]

    for lat, lon in sample_points:
        r = requests.get(
            "https://api.openchargemap.io/v3/poi/",
            params={
                "key": OCM_API_KEY,
                "latitude": lat,
                "longitude": lon,
                "distance": distance_km,
                "distanceunit": "KM",
                "maxresults": max_results
            }
        )
        r.raise_for_status()
        chargers += r.json()

    # Deduplicate by charger ID
    unique = {c["ID"]: c for c in chargers}
    return list(unique.values())


# -------------------------
# PHYSICS
# -------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# -------------------------
# TRIP SIMULATION
# -------------------------
def simulate_trip_with_charging(route, car_specs, soc_percent, min_buffer_km=20):
    wh_per_km = car_specs["wh_per_km"]
    battery_kwh = car_specs["battery_kwh"]

    usable_wh = battery_kwh * 1000 * (soc_percent / 100)
    remaining_km = usable_wh / wh_per_km

    distance = 0.0
    last = route[0]
    stops = []

    for pt in route[1:]:
        seg = haversine(last[0], last[1], pt[0], pt[1])
        distance += seg
        remaining_km -= seg

        if remaining_km < min_buffer_km:
            chargers = get_chargers_near_route([pt])
            stops.append({
                "at_km": distance,
                "location": pt,
                "chargers": chargers[:3]
            })
            remaining_km = battery_kwh * 1000 / wh_per_km

        last = pt

    return stops, distance


# -------------------------
# MAIN
# -------------------------
def main():
    print("\nEV Route Planner\n")

    start_postcode = input("Enter start postcode: ").strip()
    dest_postcode = input("Enter destination postcode: ").strip()
    soc = float(input("Enter your current battery percentage: ").strip())
    car_model = input("Enter your car model (e.g., JAC iEV7s): ").strip()

    # -------------------------
    # LOAD ML RESULTS
    # -------------------------
    project_root = Path(__file__).resolve().parents[2]
    csv_path = project_root / "data" / "raw" / "scaled_trip_energy.csv"

    wh_values = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Car Model"].strip().lower() == car_model.lower():
                wh = float(row["wh_per_km_raw"])
                if 30 < wh < 350:   # realistic EV bounds
                    wh_values.append(wh)

    if wh_values:
        mean_wh_per_km = sum(wh_values) / len(wh_values)
        print(f"Loaded {len(wh_values)} ML trips for {car_model}")
    else:
        print("⚠️ No ML data found — using spec fallback")
        mean_wh_per_km = get_car_specs(car_model)["wh_per_km"]

    # -------------------------
    # ROUTE + SIMULATION
    # -------------------------
    start_coords = geocode_postcode(start_postcode)
    dest_coords = geocode_postcode(dest_postcode)
    route = get_route(start_coords, dest_coords)

    car_specs = get_car_specs(car_model)
    car_specs["wh_per_km"] = mean_wh_per_km

    stops, total_km = simulate_trip_with_charging(route, car_specs, soc)

    # -------------------------
    # OUTPUT
    # -------------------------
    print("\n--- TRIP SUMMARY ---")
    print(f"Total distance: {total_km:.1f} km")
    print(f"Using consumption: {mean_wh_per_km:.1f} Wh/km")

    if stops:
        print(f"\nCharging stops needed: {len(stops)}")
        for i, s in enumerate(stops, 1):
            print(f"\nStop {i} at {s['at_km']:.1f} km")
            if s["chargers"]:
                for j, c in enumerate(s["chargers"], 1):
                    addr = c.get("AddressInfo", {})
                    print(
                        f"  Option {j}: "
                        f"{addr.get('Title', 'Unknown')} "
                        f"({addr.get('Latitude')}, {addr.get('Longitude')})"
                    )
            else:
                print("  ⚠️ No chargers found nearby")
    else:
        print("\n✅ No charging stops needed — trip is reachable")


if __name__ == "__main__":
    main()
