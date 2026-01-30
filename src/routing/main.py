"""
Main entry point for EV route planning.
- Takes user input (start postcode, destination postcode, charger intake)
- Geocodes postcodes
- Loads JAC iEV7s specs and estimates range
- Gets route from ORS
- Finds chargers from OCM along the route
- Outputs route and charger breakdown
"""


from car_specs import get_car_specs
from load_and_estimate_range import load_and_estimate_range
import requests
import polyline
import math
import csv
from ors_config import ORS_API_KEY
from ocm_config import OCM_API_KEY


def geocode_postcode(postcode):
    url = f"https://api.openrouteservice.org/geocode/search"
    params = {
        "api_key": ORS_API_KEY,
        "text": postcode,
        "boundary.country": "GB"
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    features = resp.json().get("features", [])
    if not features:
        raise ValueError(f"No geocoding result for {postcode}")
    coords = features[0]["geometry"]["coordinates"]
    return coords[1], coords[0]  # (lat, lon)

def get_route(start_coords, dest_coords):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_API_KEY}
    body = {
        "coordinates": [
            [start_coords[1], start_coords[0]],
            [dest_coords[1], dest_coords[0]]
        ]
    }
    resp = requests.post(url, json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if "routes" not in data or not data["routes"]:
        print("ORS directions API error response:")
        print(data)
        raise ValueError("ORS directions API did not return a route. See above for details.")
    encoded_polyline = data["routes"][0]["geometry"]
    # Decode polyline to (lat, lon) tuples
    route_coords = polyline.decode(encoded_polyline)
    return route_coords

def get_chargers_near_route(route_coords, max_results=10, distance_km=2):
    # Use the first, last, and every Nth point along the route for charger search
    points = [route_coords[0], route_coords[-1]]
    if len(route_coords) > 10:
        points += [route_coords[i] for i in range(1, len(route_coords)-1, max(1, len(route_coords)//8))]
    chargers = []
    for lat, lon in points:
        url = "https://api.openchargemap.io/v3/poi/"
        params = {
            "key": OCM_API_KEY,
            "latitude": lat,
            "longitude": lon,
            "distance": distance_km,
            "distanceunit": "KM",
            "maxresults": max_results
        }
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        chargers += resp.json()
    # Remove duplicates by OCM ID
    unique = {}
    for c in chargers:
        unique[c["ID"]] = c
    return list(unique.values())

def haversine(lat1, lon1, lat2, lon2):
    # Calculate the great-circle distance between two points (in km)
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def simulate_trip_with_charging(route, car_specs, start_soc_percent, min_buffer_km=20):
    wh_per_km = car_specs['wh_per_km']
    battery_kwh = car_specs['battery_kwh']
    usable_battery_wh = battery_kwh * 1000 * (start_soc_percent / 100.0)
    max_range_km = usable_battery_wh / wh_per_km
    remaining_range_km = max_range_km
    trip_distance = 0.0
    last_point = route[0]
    charging_stops = []
    i = 1
    while i < len(route):
        seg_dist = haversine(last_point[0], last_point[1], route[i][0], route[i][1])
        trip_distance += seg_dist
        remaining_range_km -= seg_dist
        # If remaining range is below buffer, plan a charge stop
        if remaining_range_km < min_buffer_km:
            # Find chargers near this point
            chargers = get_chargers_near_route([route[i]], max_results=5, distance_km=5)
            if chargers:
                charging_stops.append({
                    'at_km': trip_distance,
                    'location': (route[i][0], route[i][1]),
                    'chargers': chargers[:3]  # Up to 3 options
                })
                # Simulate full recharge
                remaining_range_km = (battery_kwh * 1000) / wh_per_km
            else:
                charging_stops.append({
                    'at_km': trip_distance,
                    'location': (route[i][0], route[i][1]),
                    'chargers': []
                })
                # Still simulate recharge to continue
                remaining_range_km = (battery_kwh * 1000) / wh_per_km
        last_point = route[i]
        i += 1
    return charging_stops, trip_distance

def main():
    print("EV Route Planner")
    start_postcode = input("Enter start postcode: ")
    dest_postcode = input("Enter destination postcode: ")
    current_soc_percent = input("Enter your current battery percentage (e.g., 40 for 40%): ")
    current_soc_percent = float(current_soc_percent)

    car_model = input("Enter your car model (e.g., JAC iEV7s): ").strip()
    car_model_lower = car_model.lower()
    soc = current_soc_percent

    # Load mean wh_per_km_raw for this car from scaled_trip_energy.csv
    csv_path = "../../data/raw/scaled_trip_energy.csv"
    wh_per_km_list = []
    with open(csv_path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            row_car_model = row["Car Model"].strip().lower()
            if row_car_model == car_model_lower:
                try:
                    wh = float(row["wh_per_km_raw"])
                    # Filter on raw value: only keep reasonable values (0 < wh < 20)
                    if 0 < wh < 20:
                        wh_per_km_list.append(wh)
                except Exception:
                    continue
    SCALING_FACTOR = 48  # Adjust as needed for your car/model
    if wh_per_km_list:
        mean_wh_per_km = (sum(wh_per_km_list) / len(wh_per_km_list)) * SCALING_FACTOR
    else:
        print(f"Warning: No wh_per_km_raw found for {car_model}, using car_specs fallback.")
        mean_wh_per_km = get_car_specs(car_model)["wh_per_km"]

    # Geocode postcodes
    print(f"Geocoding {start_postcode} and {dest_postcode} ...")
    start_coords = geocode_postcode(start_postcode)
    dest_coords = geocode_postcode(dest_postcode)

    # Load car specs and estimate range (override wh_per_km with mean from CSV)
    car_specs = get_car_specs(car_model)
    car_specs["wh_per_km"] = mean_wh_per_km
    range_info = load_and_estimate_range(car_model, soc)
    print(f"Car: {car_model}, Using mean wh_per_km_raw: {mean_wh_per_km:.2f} Wh/km")
    print(f"Estimated range: {range_info['est_range_km']:.1f} km")

    # Get route from ORS
    print("Getting route from ORS ...")
    route = get_route(start_coords, dest_coords)

    # Simulate trip and plan charging stops
    print("Simulating trip and planning charging stops ...")
    charging_stops, total_distance = simulate_trip_with_charging(
        route, car_specs, soc, min_buffer_km=20)

    print("\nTrip summary:")
    print(f"Total route distance: {total_distance:.1f} km")
    if charging_stops:
        print(f"Charging stops needed: {len(charging_stops)}")
        for idx, stop in enumerate(charging_stops, 1):
            chargers = stop['chargers']
            print(f"Stop {idx}: At {stop['at_km']:.1f} km")
            if chargers:
                for cidx, charger in enumerate(chargers, 1):
                    addr = charger.get('AddressInfo', {})
                    print(f"  Option {cidx}: {addr.get('Title', 'Unknown')} ({addr.get('Latitude')}, {addr.get('Longitude')})")
            else:
                print("  No chargers found nearby!")
    else:
        print("No charging stops needed for this trip.")

if __name__ == "__main__":
    main()
