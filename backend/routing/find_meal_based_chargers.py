from datetime import timedelta
import os
from backend.routing.food_places_identifier import has_nearby_food, get_nearby_food_places, is_meal_time
from backend.routing.traffic_delay import fetch_traffic_delay_percent as get_traffic_delay_percent
from backend.routing.rank_chargers import rank_and_filter_chargers
from backend.routing.services.ev_battery_simulation import haversine_formula as route_segment_distance, trip_range_simulation as trip_simulation
from backend.routing.services.ocm_retrieval import ocm_retrieval


def rank_fallback_chargers(route, car_specs, soc, est_reachable_km, priorities, start_coords, traffic_depart_at):

    def trip_stops(route, car_specs, soc):
        try:
            stops, _ = trip_simulation(route, car_specs, soc)
        except Exception:
            stops = []
        return stops

    def distance_charger_filter(charger, route, start_coords, traffic_depart_at):
        address = charger.get("Address", {})
        latitude = address.get("Latitude")
        longitude = address.get("Longitude")
        charger_coords = (latitude, longitude)
        if charger_coords[0] is not None and charger_coords[1] is not None:
            charger_km = route_segment_distance(route[0][0], route[0][1], charger_coords[0], charger_coords[1])
            origin_coords = start_coords or route[0]
            delay_percent = get_traffic_delay_percent(origin_coords, charger_coords, depart_at=traffic_depart_at)
        else:
            charger_km = None
            delay_percent = 0.0
        charger["traffic_delay"] = delay_percent
        charger["meal_stop"] = False
        charger["distance_stop"] = True
        charger["route_distance"] = charger_km
        return charger

    def search_for_chargers(stop, route, est_reachable_km, start_coords, traffic_depart_at, base_dist_km_window=5, max_dist_km_window=50, min_results=3):
        stop_km = stop.get("at_km")
        window = base_dist_km_window
        chargers_in_window = []
        while len(chargers_in_window) < min_results and window <= max_dist_km_window:
            chargers_in_window = []
            for charger in stop.get("chargers", []):
                c = distance_charger_filter(charger, route, start_coords, traffic_depart_at)
                charger_distance = c.get("route_distance")
                if (
                    charger_distance is not None
                    and charger_distance <= est_reachable_km
                    and abs(charger_distance - stop_km) <= window
                ):
                    chargers_in_window.append(c)
            if len(chargers_in_window) < min_results:
                window += 5
        return chargers_in_window

    all_chargers = []
    stops = trip_stops(route, car_specs, soc)
    for stop in stops:
        stop_km = stop.get("at_km")
        if stop_km is None or stop_km > est_reachable_km:
            continue
        chargers = search_for_chargers(stop, route, est_reachable_km, start_coords, traffic_depart_at)
        if chargers:
            all_chargers.extend(chargers)

    ranked = rank_and_filter_chargers(all_chargers, priorities or [])
    return ranked


def calculate_route_time(route_points, journey_start, avg_speed_kmh=60):
    route_times = []
    for idex, point in enumerate(route_points):
        if idex == 0:
            eta = journey_start
            route_times.append(eta)
            continue
        seg_km = route_segment_distance(route_points[idex-1][0], route_points[idex-1][1], point[0], point[1])
        seg_hr = seg_km / avg_speed_kmh
        eta = route_times[-1] + timedelta(hours=seg_hr)
        route_times.append(eta)
    return route_times


def calculate_route_distance(route_points):
    route_distance = []
    kms = 0.0
    for i in range(1, len(route_points)):
        kms += route_segment_distance(
            route_points[i-1][0], route_points[i-1][1], route_points[i][0], route_points[i][1]
        )
        route_distance.append(kms)
    return route_distance


def estimate_distance_to_meal_window(car_specs, soc):
    usable_wh = car_specs["battery_kwh"] * 1000 * (soc / 100)
    mean_wh_per_km = car_specs.get("wh_per_km")
    return usable_wh / mean_wh_per_km if mean_wh_per_km else 0


def meal_windows(route_times, window_types):
    return {w for w in window_types if any(is_meal_time(eta, window_type=w) for eta in route_times)}


def meal_window_indices(route_times, window_types):
    indices = []
    for w in window_types:
        indices += [i for i, eta in enumerate(route_times) if is_meal_time(eta, window_type=w)]
    return sorted(indices)


def reachable_windows(route_times, route_distance, est_reachable_km, window_types):
    selected_windows = [w for w in window_types if any(is_meal_time(eta, window_type=w) for eta in route_times)]
    reachable_windows = []
    for window_type in selected_windows:
        indices_in_window = [i for i, eta in enumerate(route_times) if is_meal_time(eta, window_type=window_type)]
        if not indices_in_window:
            continue
        earliest_idx = indices_in_window[0]
        earliest_km = route_distance[earliest_idx-1] if earliest_idx > 0 else 0.0
        if earliest_km <= est_reachable_km:
            reachable_windows.append(window_type)
    return reachable_windows


def enrich_chargers(c, pt_km, window_type, start_coords, route, traffic_depart_at):
    addr = c.get('AddressInfo', {})
    lat = addr.get('Latitude')
    lon = addr.get('Longitude')
    charger_coords = (lat, lon)
    origin_coords = start_coords or route[0]
    delay_pct = get_traffic_delay_percent(origin_coords, charger_coords, depart_at=traffic_depart_at) if charger_coords[0] is not None and charger_coords[1] is not None else 0.0
    c['traffic_delay'] = delay_pct
    c['meal_stop'] = True
    c['distance_stop'] = False
    c['route_km'] = pt_km
    c['meal_window'] = window_type
    return c


def sample_reachable_indices(route_times, window_type, route_distance, est_reachable_km):
    indices_in_window = [i for i, eta in enumerate(route_times) if is_meal_time(eta, window_type=window_type)]
    if not indices_in_window:
        return []
    in_range = [i for i in indices_in_window if (route_distance[i - 1] if i > 0 else 0.0) <= est_reachable_km]
    if not in_range:
        return []
    first_idx = in_range[0]
    mid_idx = in_range[len(in_range) // 2]
    last_idx = in_range[-1]
    seen = set()
    chosen = []
    for idx in (first_idx, mid_idx, last_idx):
        if idx not in seen:
            seen.add(idx)
            chosen.append(idx)
    return chosen


def query_meal_chargers(pt, pt_km, window_type, start_coords, route, traffic_depart_at):
    try:
        chargers = ocm_retrieval([pt], max_results=10, distance_km=7)
    except Exception:
        return []
    meal_chargers = []
    for c in chargers:
        addr = c.get('AddressInfo', {})
        lat = addr.get('Latitude')
        lon = addr.get('Longitude')
        if lat is None or lon is None:
            continue
        # If Yelp key is missing, be permissive and allow chargers through
        yelp_key = os.getenv("YELP_API_KEY")
        has_food = True if not yelp_key else has_nearby_food(lat, lon, window_type=window_type)
        if not has_food:
            continue
        places = get_nearby_food_places(lat, lon, window_type=window_type) if yelp_key else []
        c = enrich_chargers(c, pt_km, window_type, start_coords, route, traffic_depart_at)
        c['nearby_places'] = (places or [])[:3]
        c['price'] = c.get('price') if c.get('price') is not None else 0.1
        c['max_power'] = c.get('max_power') if c.get('max_power') is not None else 100.0
        c['is_fast'] = c.get('is_fast') if c.get('is_fast') is not None else True
        c['num_points'] = c.get('num_points') if c.get('num_points') is not None else 4
        c['distance'] = addr.get('Distance') if addr.get('Distance') is not None else 0.1
        meal_chargers.append(c)
    return meal_chargers


def unique_chargers(all_chargers, meal_chargers):
    for c in {c['ID']: c for c in meal_chargers}.values():
        all_chargers.append({'raw': c, **c})


def find_meal_based_chargers(route, car_specs, soc, journey_start, priorities=None, start_coords=None, traffic_depart_at=None):
    avg_speed_kmh = 60
    route_points = route
    window_types = ["breakfast", "coffee", "lunch", "dinner"]

    route_times = calculate_route_time(route_points, journey_start, avg_speed_kmh=avg_speed_kmh)
    covered_windows = meal_windows(route_times, window_types)
    meal_window_idxs = meal_window_indices(route_times, window_types)
    route_distance = calculate_route_distance(route_points)

    first_meal_idx = meal_window_idxs[0] if meal_window_idxs else None
    first_meal_km = route_distance[first_meal_idx-1] if first_meal_idx is not None and first_meal_idx > 0 else 0.0

    est_reachable_km = estimate_distance_to_meal_window(car_specs, soc)

    if est_reachable_km < first_meal_km:
        return rank_fallback_chargers(route, car_specs, soc, est_reachable_km, priorities, start_coords, traffic_depart_at)

    reachable_window_list = reachable_windows(route_times, route_distance, est_reachable_km, window_types)

    if not reachable_window_list:
        return rank_fallback_chargers(route, car_specs, soc, est_reachable_km, priorities, start_coords, traffic_depart_at)

    all_chargers = []
    for window_type in reachable_window_list:
        for idx in sample_reachable_indices(route_times, window_type, route_distance, est_reachable_km):
            pt_km = route_distance[idx-1] if idx > 0 else 0.0
            if pt_km > est_reachable_km:
                continue
            pt = route_points[idx]
            meal_chargers = query_meal_chargers(pt, pt_km, window_type, start_coords, route, traffic_depart_at)
            unique_chargers(all_chargers, meal_chargers)

    ranked = rank_and_filter_chargers(all_chargers, priorities or [])
    return ranked


