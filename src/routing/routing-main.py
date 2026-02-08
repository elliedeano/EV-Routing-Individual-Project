from car_specs import get_car_specs
from load_and_estimate_range import load_and_estimate_range
import requests
import polyline
import math
import csv
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from charger_ranking.traffic_filter_calcs import get_traffic_delay_percent
from charger_ranking.traffic_filter_calcs import get_traffic_delay_percent
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImJjMWY3ZTRiMGQ0ZTQ1NTRiMjlmNjQ4Y2NlM2I0ZTdlIiwiaCI6Im11cm11cjY0In0="
OCM_API_KEY = "bc0fb54f-d673-4829-9bbb-f2abac2c11f8"


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
        raise ValueError(f"No result for {postcode}")
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


def get_chargers_near_route(route_coords, max_results=5, distance_km=10):
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

    unique = {c["ID"]: c for c in chargers}
    return list(unique.values())



def route_segment_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))



def trip_simulation(route, car_specs, soc_percent, min_buffer_km=20):
    wh_per_km = car_specs["wh_per_km"]
    battery_kwh = car_specs["battery_kwh"]

    usable_wh = battery_kwh * 1000 * (soc_percent / 100)
    remaining_km = usable_wh / wh_per_km

    distance = 0.0
    last = route[0]
    stops = []

    for pt in route[1:]:
        seg = route_segment_distance(last[0], last[1], pt[0], pt[1])
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



def main():
    all_chargers = []
    # After trip simulation, rank chargers using user priorities
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from charger_ranking.rank_chargers import rank_and_filter_chargers
    # After charging stops and all_chargers are built, print both baseline and ranked chargers
    if all_chargers:
        print("\nBaseline Charger Options:")
        for i, c in enumerate(all_chargers, 1):
            addr = c.get('AddressInfo', {}).get('Title', 'Unknown')
            print(f"{i}. {addr}")
        # Print ranked chargers
        ranked = rank_and_filter_chargers(all_chargers, priorities)
        print("\nTop Filtered Charger Recommendations:")
        for i, c in enumerate(ranked[:5], 1):
            addr = c['raw'].get('AddressInfo', {}).get('Title', 'Unknown')
            print(f"{i}. {addr} | Price: {c['price']} | Power: {c['max_power']} kW | Fast: {c['is_fast']} | Points: {c['num_points']} | Distance: {c['distance']:.2f} km | Traffic Delay: {c['traffic_delay']:.1f}%")
            if i == 1:
                print("  --- Breakdown for top charger ---")
                for p in priorities:
                    b = c['breakdown'][p]
                    print(f"    {p}: weight={b['weight']}, normalized={b['normalized']:.2f}, points={b['points']:.2f}")
                print(f"    Total score: {c['score']:.2f}")
    # ...existing code...
    # After car model selection, calculate energy and route
    # Estimate wh_per_km for selected car
    battery_kwh = 60  # Default/fallback value, update as needed
    wh_per_km = 200   # Default/fallback value, update as needed
    # If you have a CSV or lookup, replace these with actual values
    car_specs = {
        "battery_kwh": battery_kwh,
        "wh_per_km": wh_per_km
    }
    mean_wh_per_km = car_specs["wh_per_km"]

    print("\n--- EV Routing Input ---")
    start_postcode = input("Enter your start postcode: ").strip()
    end_postcode = input("Enter your destination postcode: ").strip()
    while True:
        soc_input = input("Enter your current battery percentage (e.g. 80): ").strip()
        try:
            soc = float(soc_input)
            if 0 < soc <= 100:
                break
            else:
                print("Please enter a value between 1 and 100.")
        except ValueError:
            print("Please enter a valid number.")

    car_models = [
        "Hyundai IONIQ 5",
        "Hyundai Kona Electric",
        "JAC iEV7s",
        "Jeep Avenger",
        "Kia EV3",
        "Peugeot E-2008",
        "Porsche Taycan",
        "Renault Scenic",
        "Skoda Enyaq",
        "Tesla Model 3"
    ]
    while True:
        print("\nAvailable car models:")
        for idx, model in enumerate(car_models, 1):
            print(f"  {idx}. {model}")
        model_input = input("Select your car model by number: ").strip()
        if model_input.isdigit() and 1 <= int(model_input) <= len(car_models):
            car_model = car_models[int(model_input)-1]
            break
        else:
            print("Please enter a valid number from the list above.")

    # Fallback car specs
    battery_kwh = 60
    wh_per_km = 200
    car_specs = {
        "battery_kwh": battery_kwh,
        "wh_per_km": wh_per_km
    }
    mean_wh_per_km = car_specs["wh_per_km"]

    start_coords = geocode_postcode(start_postcode)
    dest_coords = geocode_postcode(end_postcode)
    route = get_route(start_coords, dest_coords)
    stops, total_km = trip_simulation(route, car_specs, soc)

        # --- Filter/Priorities Selection ---
    # ...existing code...

        # --- Filter/Priorities Selection ---
    priorities_list = [
        ("price", "Lowest price per kWh"),
        ("max_power", "Highest charging power (kW)"),
        ("is_fast", "Fast charge capable"),
        ("num_points", "Most charging points"),
        ("distance", "Closest distance"),
        ("traffic_delay", "Least traffic delay (% increase)")
    ]
    print("\nSelect your top 3 priorities by number (comma separated):")
    for idx, (key, desc) in enumerate(priorities_list, 1):
        print(f"  {idx}. {key} - {desc}")
    while True:
        user_input = input("Enter 3 numbers (e.g. 1,3,6): ").strip()
        nums = [n.strip() for n in user_input.split(',') if n.strip().isdigit()]
        if len(nums) == 3 and all(1 <= int(n) <= len(priorities_list) for n in nums):
            priorities = [priorities_list[int(n)-1][0] for n in nums]
            break
        else:
            print("Invalid input. Please enter 3 numbers from the list above.")
    print("\nRoute Summary")
    print(f"Total distance: {total_km:.1f} km")
    print(f"Using energy consumption: {mean_wh_per_km:.1f} Wh/km")

    # Traffic analysis output
    # analyze_traffic(start_coords, dest_coords, total_km)  # No longer needed; traffic handled per charger

    from traffic_analysis import get_traffic_delay_percent
    all_chargers = []
    if stops:
        print(f"\nCharging stops needed: {len(stops)}")
        for i, s in enumerate(stops, 1):
            print(f"\nStop {i} at {s['at_km']:.1f} km")
            if s["chargers"]:
                for j, c in enumerate(s["chargers"], 1):
                    addr = c.get("AddressInfo", {})
                    print(f"  Option {j}: {addr.get('Title', 'Unknown')}")
                    # Calculate traffic delay percent for this charger
                    charger_coords = (addr.get('Latitude'), addr.get('Longitude'))
                    if charger_coords[0] is not None and charger_coords[1] is not None:
                        delay_pct = get_traffic_delay_percent(start_coords, charger_coords)
                    else:
                        delay_pct = 0.0
                    c['traffic_delay'] = delay_pct
                    all_chargers.append(c)
            else:
                print("No chargers found nearby")
    else:
        print("\nNo charging stops needed — destination is reachable")
    # Save all found chargers to baseline_chargers.json for ranking
    if all_chargers:
        import json
        out_dir = Path(__file__).resolve().parents[1] / "output"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "baseline_chargers.json"
        with open(out_path, "w") as f:
            json.dump(all_chargers, f, indent=2)
        print(f"\nSaved {len(all_chargers)} chargers to {out_path}")

        # Print baseline chargers
        print("\n--- Baseline Charger Options (by distance) ---")
        for i, c in enumerate(all_chargers, 1):
            addr = c.get('AddressInfo', {}).get('Title', 'Unknown')
            dist = c.get('AddressInfo', {}).get('Distance', None)
            if dist is not None:
                print(f"{i}. {addr} ({dist:.2f} km)")
            else:
                print(f"{i}. {addr}")

        # Rank and print chargers by user priorities
        from charger_ranking.rank_chargers import rank_and_filter_chargers
        ranked = rank_and_filter_chargers(all_chargers, priorities)
        print("\n--- Top 3 Filtered Charger Recommendations (by your priorities) ---")
        top_n = min(3, len(ranked))
        if top_n == 0:
            print("No chargers matched your filter criteria.")
        else:
            for i, c in enumerate(ranked[:top_n], 1):
                addr = c['raw'].get('AddressInfo', {}).get('Title', 'Unknown')
                print(f"{i}. {addr} | Price: {c['price']} | Power: {c['max_power']} kW | Fast: {c['is_fast']} | Points: {c['num_points']} | Distance: {c['distance']:.2f} km | Traffic Delay: {c['traffic_delay']:.1f}%")
                if i == 1:
                    print("  --- Breakdown for top charger ---")
                    for p in priorities:
                        b = c['breakdown'][p]
                        print(f"    {p}: weight={b['weight']}, normalized={b['normalized']:.2f}, points={b['points']:.2f}")
                    print(f"    Total score: {c['score']:.2f}")
            if top_n < 3:
                print(f"(Only {top_n} charger(s) matched your filter criteria.)")

            # Print the full JSON for each filtered charger for inspection
            import json as _json
            print("\n--- Filtered Charger JSON Data ---")
            for i, c in enumerate(ranked[:top_n], 1):
                print(f"\nFiltered Charger {i} JSON:")
                print(_json.dumps(c['raw'], indent=2))
    else:
        print("\nNo chargers to save for ranking.")


if __name__ == "__main__":
    main()
