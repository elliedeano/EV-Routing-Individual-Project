import sys
import requests
import polyline
import math
import csv
from pathlib import Path
# Add project root to sys.path for meal_time_routing import
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from meal_time_routing import filter_meal_time_chargers
from load_and_estimate_range import load_and_estimate_range
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
    sample = list(unique.values())
    return sample



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



def get_car_specs(car_model):
    # Looks up car specs from the scaled_trip_energy.csv file
    project_root = Path(__file__).resolve().parents[2]
    csv_path = project_root / "src" / "energy-consumption" / "output_files" / "scaled_trip_energy.csv"
    import pandas as pd
    df = pd.read_csv(csv_path)
    # Use the mean wh_per_km for the selected car model
    car_rows = df[df["Car Model"] == car_model]
    wh_per_km = car_rows["wh_per_km_raw"].mean() if not car_rows.empty else 200
    specs = {
        "battery_kwh": 60,  # Default/fallback value, update if you have battery info
        "wh_per_km": wh_per_km,
    }
    return specs


def main():
    all_chargers = []
    # After trip simulation, rank chargers using user priorities
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from charger_ranking.rank_chargers import rank_and_filter_chargers
    # After charging stops and all_chargers are built, print both baseline and ranked chargers
    if all_chargers:
        print("Baseline Charger Options:")
        for i, c in enumerate(all_chargers, 1):
            addr = c.get('AddressInfo', {}).get('Title', 'Unknown')
            print(f"{i}. {addr}")
        # Print ranked chargers
        ranked = rank_and_filter_chargers(all_chargers, priorities)
        print("\nFiltered Charger Recommendations:")
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
    battery_kwh = 60  # Default/fallback value, update as needed
    wh_per_km = 200   # Default/fallback value, update as needed
    car_specs = {
        "battery_kwh": battery_kwh,
        "wh_per_km": wh_per_km
    }
    mean_wh_per_km = car_specs["wh_per_km"]

    print("\n\033[1mEV Routing Input\033[0m")

    from datetime import datetime, timedelta
    user_time = input("\033[1mEnter your journey start time (HH:MM) or type 'now':\033[0m\n> ").strip().lower()
    if user_time == 'now':
        journey_start = datetime.now()
    else:
        try:
            today = datetime.now()
            hour, minute = map(int, user_time.split(":"))
            journey_start = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if journey_start < today:
                journey_start += timedelta(days=1)
        except Exception as e:
            print("Invalid time format. Using current time.")
            journey_start = datetime.now()

    print(f"[DEBUG] Journey start time: {journey_start} (input: '{user_time}')")

    start_postcode = input("\033[1mEnter your start postcode:\033[0m\n> ").strip()
    end_postcode = input("\033[1mEnter your destination postcode:\033[0m\n> ").strip()
    while True:
        soc_input = input("\033[1mEnter your current battery percentage (e.g. 80):\033[0m\n> ").strip()
        try:
            soc = float(soc_input)
            if 0 < soc <= 100:
                break
            else:
                print("Please enter a value between 1 and 100.")
        except ValueError:
            print("Please enter a valid number.")

    # Load car models and specs from CSV
    import csv
    car_models = []
    car_specs_dict = {}
    csv_path = Path(__file__).resolve().parents[2] / "data" / "raw" / "car-energy-database-30.csv"
    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            model = row['Car Model '].strip()
            if model:
                car_models.append(model)
                try:
                    wh_per_km = float(row['Energy Consumption (Wh/KM)']) if row['Energy Consumption (Wh/KM)'] else None
                except Exception:
                    wh_per_km = None
                try:
                    mass = float(row['Mass (kg)']) if row['Mass (kg)'] else None
                except Exception:
                    mass = None
                car_specs_dict[model] = {
                    'wh_per_km': wh_per_km,
                    'mass': mass
                }

    while True:
        print("\n\033[1mAvailable car models (select by number):\033[0m")
        for idx, model in enumerate(car_models, 1):
            print(f"  {idx}. {model}")
        model_input = input("> ").strip()
        if model_input.isdigit() and 1 <= int(model_input) <= len(car_models):
            car_model = car_models[int(model_input)-1]
            break
        else:
            print("Please enter a valid number from the list above.")

    battery_kwh = 60  # Fallback value, update if you have battery info
    wh_per_km = car_specs_dict[car_model]['wh_per_km'] if car_specs_dict[car_model]['wh_per_km'] is not None else 200
    mass = car_specs_dict[car_model]['mass'] if car_specs_dict[car_model]['mass'] is not None else None
    car_specs = {
        "battery_kwh": battery_kwh,
        "wh_per_km": wh_per_km,
        "mass": mass
    }
    mean_wh_per_km = car_specs["wh_per_km"]

    start_coords = geocode_postcode(start_postcode)
    dest_coords = geocode_postcode(end_postcode)
    route = get_route(start_coords, dest_coords)
    stops, total_km = trip_simulation(route, car_specs, soc)

    # --- Umbrella Filter Selection ---
    umbrella_options = [
        ("distance", "Distance-based stops (default)"),
        ("meal", "Meal-based stops (food/cafe nearby, smaller window)")
    ]
    print("\n\033[1mSelect your stop type:\033[0m")
    for idx, (_, desc) in enumerate(umbrella_options, 1):
        print(f"  {idx}. {desc}")
    while True:
        umbrella_input = input("> ").strip()
        if umbrella_input.isdigit() and 1 <= int(umbrella_input) <= len(umbrella_options):
            umbrella_choice = umbrella_options[int(umbrella_input)-1][0]
            break
        else:
            print("Please enter 1 or 2.")

    # --- Secondary Priorities Selection ---
    # Add umbrella filter as a priority
    priorities_list = [
        ("price", "Lowest price per kWh"),
        ("max_power", "Highest charging power (kW)"),
        ("is_fast", "Fast charge capable"),
        ("num_points", "Most charging points"),
        ("distance", "Closest distance"),
        ("traffic_delay", "Least traffic delay (% increase)")
    ]
    umbrella_priority = ("meal_stop", "Meal stop suitability") if umbrella_choice == "meal" else ("distance_stop", "Distance-based stop")
    priorities_list = [umbrella_priority] + priorities_list
    print("\n\033[1mSelect your top 2 additional priorities (comma separated numbers):\033[0m")
    for idx, (_, desc) in enumerate(priorities_list, 1):
        print(f"  {idx}. {desc}")
    while True:
        user_input = input("> ").strip()
        nums = [n.strip() for n in user_input.split(',') if n.strip().isdigit()]
        if len(nums) == 2 and all(1 <= int(n) <= len(priorities_list) for n in nums):
            priorities = [priorities_list[0][0]] + [priorities_list[int(n)-1][0] for n in nums]
            break
        else:
            print("Invalid input. Please enter 2 numbers from the list above.")

    print("\n\033[1m\033[4mRoute Summary\033[0m")
    print(f"Total distance: {total_km:.1f} km")
    print(f"Using energy consumption: {mean_wh_per_km:.1f} Wh/km")
    usable_wh = car_specs["battery_kwh"] * 1000 * (soc / 100)
    est_reachable_km = usable_wh / mean_wh_per_km if mean_wh_per_km else 0
    print(f"Estimated range on current charge: {est_reachable_km:.1f} km")

    # Traffic analysis output
    # analyze_traffic(start_coords, dest_coords, total_km)  # No longer needed; traffic handled per charger

    from traffic import get_traffic_delay_percent
    all_chargers = []
    # Always show meal-based charger recommendations if selected, but add fallback if battery is too low to reach meal window
    if umbrella_choice == "meal":
        from meal_time_routing import has_nearby_food, get_nearby_food_places, is_meal_time
        avg_speed_kmh = 90
        route_points = route
        from datetime import timedelta
        # Scan route for which windows are covered
        window_types = ["coffee", "lunch", "dinner"]
        covered_windows = set()
        route_times = []
        for idx, pt in enumerate(route_points):
            # Estimate time at this point
            if idx == 0:
                eta = journey_start
                route_times.append(eta)
                continue
            seg_km = route_segment_distance(route_points[idx-1][0], route_points[idx-1][1], pt[0], pt[1])
            seg_hr = seg_km / avg_speed_kmh
            eta = route_times[-1] + timedelta(hours=seg_hr)
            route_times.append(eta)
            # Debug: print ETA and meal window match for first 20 points
            if idx < 20:
                for w in window_types:
                    match = is_meal_time(eta, window_type=w)
                    print(f"[DEBUG] idx={idx}, ETA={eta}, window={w}, is_meal_time={match}")
                    if match:
                        covered_windows.add(w)
            else:
                for w in window_types:
                    if is_meal_time(eta, window_type=w):
                        covered_windows.add(w)
        print(f"[DEBUG] Route points: {len(route_points)}")
        # Find first meal window index and its distance
        meal_window_indices = []
        for w in window_types:
            meal_window_indices += [i for i, eta in enumerate(route_times) if is_meal_time(eta, window_type=w)]
        meal_window_indices = sorted(meal_window_indices)
        route_kms = []
        kms = 0.0
        for i in range(1, len(route_points)):
            kms += route_segment_distance(route_points[i-1][0], route_points[i-1][1], route_points[i][0], route_points[i][1])
            route_kms.append(kms)
        first_meal_idx = meal_window_indices[0] if meal_window_indices else None
        first_meal_km = route_kms[first_meal_idx-1] if first_meal_idx is not None and first_meal_idx > 0 else 0.0
        usable_wh = car_specs["battery_kwh"] * 1000 * (soc / 100)
        est_reachable_km = usable_wh / mean_wh_per_km if mean_wh_per_km else 0
        # If battery can't reach first meal window, skip meal-based charger search and only recommend chargers within estimated range
        if est_reachable_km < first_meal_km:
            print(f"\n[INFO] Battery is too low to reach the first meal window ({first_meal_km:.1f} km). Switching to distance-based charger recommendations before your estimated range ({est_reachable_km:.1f} km).")
            BASE_DIST_KM_WINDOW = 5
            MAX_DIST_KM_WINDOW = 50
            found_charger = False
            for s in stops:
                stop_km = s["at_km"]
                # Only consider stops before the estimated range
                if stop_km > est_reachable_km:
                    continue
                window = BASE_DIST_KM_WINDOW
                chargers_in_window = []
                while len(chargers_in_window) < 3 and window <= MAX_DIST_KM_WINDOW:
                    chargers_in_window = []
                    if s["chargers"]:
                        for c in s["chargers"]:
                            addr = c.get("AddressInfo", {})
                            charger_coords = (addr.get('Latitude'), addr.get('Longitude'))
                            if charger_coords[0] is not None and charger_coords[1] is not None:
                                charger_km = route_segment_distance(route[0][0], route[0][1], charger_coords[0], charger_coords[1])
                                delay_pct = get_traffic_delay_percent(start_coords, charger_coords)
                            else:
                                charger_km = None
                                delay_pct = 0.0
                            c['traffic_delay'] = delay_pct
                            c['meal_stop'] = False
                            c['distance_stop'] = True
                            c['route_km'] = charger_km
                            # Only recommend chargers within estimated range
                            if charger_km is not None and charger_km <= est_reachable_km and abs(charger_km - stop_km) <= window:
                                chargers_in_window.append(c)
                    if len(chargers_in_window) < 3:
                        window += 5
                if chargers_in_window:
                    all_chargers.extend(chargers_in_window)
                    found_charger = True
                else:
                    print(f"No chargers found within {MAX_DIST_KM_WINDOW} km of stop at {stop_km:.1f} km.")
            if not found_charger:
                print(f"[WARNING] No chargers found before your estimated range ({est_reachable_km:.1f} km). Please check charger availability or increase your battery level.")
            # Skip meal charger search entirely
        else:
            # ...existing meal window logic...
            selected_windows = []
            if "lunch" in covered_windows and "dinner" in covered_windows:
                selected_windows = ["lunch", "dinner"]
            elif "lunch" in covered_windows:
                selected_windows = ["lunch"]
            elif "coffee" in covered_windows:
                selected_windows = ["coffee"]
            elif "dinner" in covered_windows:
                selected_windows = ["dinner"]
            # Precompute cumulative kms along the route
            route_kms = []
            kms = 0.0
            for i in range(1, len(route_points)):
                kms += route_segment_distance(route_points[i-1][0], route_points[i-1][1], route_points[i][0], route_points[i][1])
                route_kms.append(kms)

            # Determine which meal windows have an earliest match within estimated range
            reachable_windows = []
            for window_type in selected_windows:
                indices_in_window = [i for i, eta in enumerate(route_times) if is_meal_time(eta, window_type=window_type)]
                if not indices_in_window:
                    continue
                earliest_idx = indices_in_window[0]
                earliest_km = route_kms[earliest_idx-1] if earliest_idx > 0 else 0.0
                if earliest_km <= est_reachable_km:
                    reachable_windows.append(window_type)
                else:
                    print(f"[INFO] Earliest {window_type} stop at {earliest_km:.1f} km is beyond your estimated range ({est_reachable_km:.1f} km); skipping {window_type} meal search.")

            all_chargers = []
            # If no meal window is reachable, fall back to distance-based recommendations
            if not reachable_windows:
                print("[INFO] No meal windows are reachable within your current estimated range. Falling back to distance-based charger recommendations.")
                BASE_DIST_KM_WINDOW = 5
                MAX_DIST_KM_WINDOW = 50
                found_charger = False
                for s in stops:
                    stop_km = s["at_km"]
                    # Only consider stops before the estimated range
                    if stop_km > est_reachable_km:
                        continue
                    window = BASE_DIST_KM_WINDOW
                    chargers_in_window = []
                    while len(chargers_in_window) < 3 and window <= MAX_DIST_KM_WINDOW:
                        chargers_in_window = []
                        if s["chargers"]:
                            for c in s["chargers"]:
                                addr = c.get("AddressInfo", {})
                                charger_coords = (addr.get('Latitude'), addr.get('Longitude'))
                                if charger_coords[0] is not None and charger_coords[1] is not None:
                                    charger_km = route_segment_distance(route[0][0], route[0][1], charger_coords[0], charger_coords[1])
                                    delay_pct = get_traffic_delay_percent(start_coords, charger_coords)
                                else:
                                    charger_km = None
                                    delay_pct = 0.0
                                c['traffic_delay'] = delay_pct
                                c['meal_stop'] = False
                                c['distance_stop'] = True
                                c['route_km'] = charger_km
                                # Only recommend chargers within estimated range
                                if charger_km is not None and charger_km <= est_reachable_km and abs(charger_km - stop_km) <= window:
                                    chargers_in_window.append(c)
                        if len(chargers_in_window) < 3:
                            window += 5
                    if chargers_in_window:
                        all_chargers.extend(chargers_in_window)
                        found_charger = True
                    else:
                        print(f"No chargers found within {MAX_DIST_KM_WINDOW} km of stop at {stop_km:.1f} km.")
                if not found_charger:
                    print(f"[WARNING] No chargers found before your estimated range ({est_reachable_km:.1f} km). Please check charger availability or increase your battery level.")
            else:
                # Search only reachable meal windows
                for window_type in reachable_windows:
                    print(f"\n[DEBUG] Searching for {window_type} stop...")
                    SEARCH_KM_WINDOW = 10
                    meal_chargers = []
                    indices_in_window = [i for i, eta in enumerate(route_times) if is_meal_time(eta, window_type=window_type)]
                    if not indices_in_window:
                        print(f"[DEBUG] No suitable {window_type} stop found: no route points match meal window.")
                        continue
                    # pick a middle index to check for variety, but ensure it's within estimated range when possible
                    mid = len(indices_in_window) // 2
                    checked_indices = set([indices_in_window[mid]])
                    for idx in checked_indices:
                        pt_km = route_kms[idx-1] if idx > 0 else 0.0
                        # If selected point is beyond range, skip
                        if pt_km > est_reachable_km:
                            print(f"[INFO] Selected {window_type} point at {pt_km:.1f} km is beyond estimated range ({est_reachable_km:.1f} km); skipping this index.")
                            continue
                        pt = route_points[idx]
                        chargers = get_chargers_near_route([pt], max_results=10, distance_km=7)
                        print(f"[DEBUG] Checking route point {idx} at {pt_km:.1f} km for {window_type}: found {len(chargers)} chargers")
                        found_here = 0
                        found_names = []
                        for c in chargers:
                            addr = c.get('AddressInfo', {})
                            lat = addr.get('Latitude')
                            lon = addr.get('Longitude')
                            if lat is not None and lon is not None and has_nearby_food(lat, lon, window_type=window_type):
                                charger_coords = (lat, lon)
                                delay_pct = get_traffic_delay_percent(start_coords, charger_coords) if charger_coords[0] is not None and charger_coords[1] is not None else 0.0
                                c['traffic_delay'] = delay_pct
                                c['meal_stop'] = True
                                c['distance_stop'] = False
                                c['route_km'] = pt_km
                                c['meal_window'] = window_type
                                # Set default values for ranking fields if missing
                                c['price'] = c.get('price') if c.get('price') is not None else 0.1
                                c['max_power'] = c.get('max_power') if c.get('max_power') is not None else 100.0
                                c['is_fast'] = c.get('is_fast') if c.get('is_fast') is not None else True
                                c['num_points'] = c.get('num_points') if c.get('num_points') is not None else 4
                                c['distance'] = addr.get('Distance') if addr.get('Distance') is not None else 0.1
                                meal_chargers.append(c)
                                found_here += 1
                                found_names.append(addr.get('Title', 'Unknown'))
                        print(f"[DEBUG]   Chargers with food/cafe nearby at this point: {found_here}")
                        if found_names:
                            print(f"[DEBUG]     Names: {', '.join(found_names)}")
                    if not meal_chargers:
                        print(f"[DEBUG] No suitable {window_type} stop found on your route.")
                    unique_meal_chargers = {c['ID']: c for c in meal_chargers}.values()
                    # Wrap each charger in a dict with 'raw' key for ranking compatibility
                    for c in unique_meal_chargers:
                        all_chargers.append({'raw': c, **c})
                    print(f"\n[DEBUG] Restaurants/cafes near each recommended charger for {window_type}:")
                    for i, c in enumerate(meal_chargers, 1):
                        addr = c.get('AddressInfo', {})
                        lat = addr.get('Latitude')
                        lon = addr.get('Longitude')
                        print(f"{i}. {addr.get('Title', 'Unknown')}:")
                        if lat is not None and lon is not None:
                            places = get_nearby_food_places(lat, lon, window_type=window_type)
                            if places:
                                for p in places:
                                    print(f"    - {p}")
                            else:
                                print("    (No restaurants/cafes found)")
                        else:
                            print("    (No coordinates available)")
                if not all_chargers:
                    print("[DEBUG] No meal stop chargers found for any window. Please check meal window logic and API responses.")
    elif stops:
        route_points = route  # Ensure route_points is defined for distance-based stops
        avg_speed_kmh = 90    # Set default average speed for ETA calculations
        first_stop_km = stops[0]['at_km'] if stops else None
        if first_stop_km is not None:
            print(f"Charge stop recommended at: {first_stop_km:.1f} km")
        # Distance-based: adaptively expand window until chargers are found (up to max window)
        BASE_DIST_KM_WINDOW = 5
        MAX_DIST_KM_WINDOW = 50
        for s in stops:
            stop_km = s["at_km"]
            window = BASE_DIST_KM_WINDOW
            chargers_in_window = []
            while len(chargers_in_window) < 3 and window <= MAX_DIST_KM_WINDOW:
                chargers_in_window = []
                if s["chargers"]:
                    for c in s["chargers"]:
                        addr = c.get("AddressInfo", {})
                        charger_coords = (addr.get('Latitude'), addr.get('Longitude'))
                        if charger_coords[0] is not None and charger_coords[1] is not None:
                            charger_km = route_segment_distance(route[0][0], route[0][1], charger_coords[0], charger_coords[1])
                            delay_pct = get_traffic_delay_percent(start_coords, charger_coords)
                        else:
                            charger_km = None
                            delay_pct = 0.0
                        c['traffic_delay'] = delay_pct
                        c['meal_stop'] = False
                        c['distance_stop'] = True
                        c['route_km'] = charger_km
                        if charger_km is not None and abs(charger_km - stop_km) <= window:
                            chargers_in_window.append(c)
                if len(chargers_in_window) < 3:
                    window += 5
            if chargers_in_window:
                all_chargers.extend(chargers_in_window)
            else:
                print(f"No chargers found within {MAX_DIST_KM_WINDOW} km of stop at {stop_km:.1f} km.")
    else:
        print("\nNo charging stops needed as destination is reachable based on current estimated range.")
    # Save all found chargers to baseline_chargers.json for ranking
    if all_chargers:
        import json
        out_dir = Path(__file__).resolve().parents[1] / "output"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "baseline_chargers.json"
        with open(out_path, "w") as f:
            json.dump(all_chargers, f, indent=2)

        # Print baseline chargers with correct heading
        if umbrella_choice == "meal":
            print("\n\033[1m\033[4mMeal-Based Charger Recommendations\033[0m")
        else:
            print("\n\033[1m\033[4mDistance Based Charger Recommendations\033[0m")
        for i, c in enumerate(all_chargers, 1):
            addr = c.get('AddressInfo', {}).get('Title', 'Unknown')
            dist = c.get('AddressInfo', {}).get('Distance', None)
            if dist is not None:
                print(f"{i}. {addr} ({dist:.2f} km)")
            else:
                print(f"{i}. {addr}")
        print("")

        # Rank and print only the top 3 chargers by user priorities
        from charger_ranking.rank_chargers import rank_and_filter_chargers
        ranked = rank_and_filter_chargers(all_chargers, priorities)
        print("\n\033[1m\033[4mPriority Based Charger Recommendations\033[0m\n")
        priority_headers = {
            'meal_stop': ('Meal Stop', lambda c: 'Yes' if c.get('meal_stop') else 'No'),
            'distance_stop': ('Distance Stop', lambda c: 'Yes' if c.get('distance_stop') else 'No'),
            'route_km': ('Route KM', lambda c: f"{c['route_km']:.1f}" if c.get('route_km') is not None else '-'),
            'price': ('Price (per kWh)', lambda c: c['price']),
            'max_power': ('Charging Power (kW)', lambda c: c['max_power']),
            'is_fast': ('Fast Charge', lambda c: 'Yes' if c['is_fast'] else 'No'),
            'num_points': ('Number of Points', lambda c: c['num_points']),
            'distance': ('Distance (km)', lambda c: f"{c['distance']:.2f}"),
            'traffic_delay': ('Traffic Delay (%)', lambda c: f"{c['traffic_delay']:.1f}")
        }
        headers = ['No.', 'Charger'] + [priority_headers[p][0] for p in priorities]
        col_widths = [4, 35] + [max(15, len(priority_headers[p][0])+2) for p in priorities]
        header_fmt = ''.join([f'{{:<{w}}}' for w in col_widths])
        print(header_fmt.format(*headers))
        print('-' * (sum(col_widths)))
        for i, c in enumerate(ranked[:3], 1):
            addr = c['raw'].get('AddressInfo', {}).get('Title', 'Unknown')
            row = [i, addr[:33]] + [priority_headers[p][1](c) for p in priorities]
            # Replace None values with '-'
            row = [('-' if v is None else v) for v in row]
            print(header_fmt.format(*row))
        if len(ranked) < 3:
            print(f"(Only {len(ranked)} charger(s) matched your filter criteria.)")
        # ...existing code...
    # else block intentionally left empty; no message needed if no chargers


