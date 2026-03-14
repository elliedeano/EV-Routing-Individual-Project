from datetime import timedelta
from backend.routing.food_places_identifier import has_nearby_food, get_nearby_food_places, is_meal_time
from backend.routing.traffic_calculations import get_traffic_delay_percent
from backend.charger_ranking.rank_chargers import rank_and_filter_chargers
from backend.routing.services.simulation import route_segment_distance, trip_simulation
from backend.routing.services.charger_provider import get_chargers_near_route


def _rank_distance_fallback_chargers(route, car_specs, soc, est_reachable_km, priorities, start_coords, traffic_depart_at):
    base_dist_km_window = 5
    max_dist_km_window = 50
    found_charger = False
    all_chargers = []

    try:
        stops, _ = trip_simulation(route, car_specs, soc)
    except Exception:
        stops = []

    for stop in stops:
        stop_km = stop["at_km"]
        if stop_km > est_reachable_km:
            continue

        window = base_dist_km_window
        chargers_in_window = []

        while len(chargers_in_window) < 3 and window <= max_dist_km_window:
            chargers_in_window = []
            if stop.get("chargers"):
                for charger in stop["chargers"]:
                    addr = charger.get("AddressInfo", {})
                    charger_coords = (addr.get("Latitude"), addr.get("Longitude"))

                    if charger_coords[0] is not None and charger_coords[1] is not None:
                        charger_km = route_segment_distance(
                            route[0][0], route[0][1], charger_coords[0], charger_coords[1]
                        )
                        origin_coords = start_coords or route[0]
                        delay_pct = get_traffic_delay_percent(
                            origin_coords, charger_coords, depart_at=traffic_depart_at
                        )
                    else:
                        charger_km = None
                        delay_pct = 0.0

                    charger["traffic_delay"] = delay_pct
                    charger["meal_stop"] = False
                    charger["distance_stop"] = True
                    charger["route_km"] = charger_km

                    if (
                        charger_km is not None
                        and charger_km <= est_reachable_km
                        and abs(charger_km - stop_km) <= window
                    ):
                        chargers_in_window.append(charger)

            if len(chargers_in_window) < 3:
                window += 5

        if chargers_in_window:
            all_chargers.extend(chargers_in_window)
            found_charger = True
        else:
            pass

    ranked = rank_and_filter_chargers(all_chargers, priorities or [])
    return ranked

def find_meal_based_chargers(route, car_specs, soc, journey_start, priorities=None, start_coords=None, traffic_depart_at=None):
    avg_speed_kmh = 90
    route_points = route
    window_types = ["breakfast", "coffee", "lunch", "dinner"]
    covered_windows = set()
    route_times = []
    for idx, pt in enumerate(route_points):
        if idx == 0:
            eta = journey_start
            route_times.append(eta)
            continue
        seg_km = route_segment_distance(route_points[idx-1][0], route_points[idx-1][1], pt[0], pt[1])
        seg_hr = seg_km / avg_speed_kmh
        eta = route_times[-1] + timedelta(hours=seg_hr)
        route_times.append(eta)
        for w in window_types:
            if is_meal_time(eta, window_type=w):
                covered_windows.add(w)
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
    mean_wh_per_km = car_specs["wh_per_km"]
    est_reachable_km = usable_wh / mean_wh_per_km if mean_wh_per_km else 0
    all_chargers = []
    if est_reachable_km < first_meal_km:
        return _rank_distance_fallback_chargers(
            route,
            car_specs,
            soc,
            est_reachable_km,
            priorities,
            start_coords,
            traffic_depart_at,
        )
    selected_windows = [w for w in window_types if w in covered_windows]
    # Determine which meal windows are reachable within estimated range
    reachable_windows = []
    for window_type in selected_windows:
        indices_in_window = [i for i, eta in enumerate(route_times) if is_meal_time(eta, window_type=window_type)]
        if not indices_in_window:
            continue
        earliest_idx = indices_in_window[0]
        earliest_km = route_kms[earliest_idx-1] if earliest_idx > 0 else 0.0
        if earliest_km <= est_reachable_km:
            reachable_windows.append(window_type)

    # If no meal windows are reachable, fall back to distance-based chargers
    if not reachable_windows:
        return _rank_distance_fallback_chargers(
            route,
            car_specs,
            soc,
            est_reachable_km,
            priorities,
            start_coords,
            traffic_depart_at,
        )

    for window_type in reachable_windows:
        SEARCH_KM_WINDOW = 10
        meal_chargers = []
        indices_in_window = [i for i, eta in enumerate(route_times) if is_meal_time(eta, window_type=window_type)]
        if not indices_in_window:
              continue

        in_range_indices = [
            i for i in indices_in_window
            if (route_kms[i - 1] if i > 0 else 0.0) <= est_reachable_km
        ]
        if not in_range_indices:
            continue

        first_idx = in_range_indices[0]
        mid_idx = in_range_indices[len(in_range_indices) // 2]
        last_idx = in_range_indices[-1]
        checked_indices = []
        for idx in (first_idx, mid_idx, last_idx):
            if idx not in checked_indices:
                checked_indices.append(idx)

        for idx in checked_indices:
            pt_km = route_kms[idx-1] if idx > 0 else 0.0
            if pt_km > est_reachable_km:
                continue
            pt = route_points[idx]
            chargers = get_chargers_near_route([pt], max_results=10, distance_km=7)
            for c in chargers:
                addr = c.get('AddressInfo', {})
                lat = addr.get('Latitude')
                lon = addr.get('Longitude')
                if lat is not None and lon is not None and has_nearby_food(lat, lon, window_type=window_type):
                    places = get_nearby_food_places(lat, lon, window_type=window_type)
                    charger_coords = (lat, lon)
                    origin_coords = start_coords or route[0]
                    delay_pct = get_traffic_delay_percent(origin_coords, charger_coords, depart_at=traffic_depart_at) if charger_coords[0] is not None and charger_coords[1] is not None else 0.0
                    c['traffic_delay'] = delay_pct
                    c['meal_stop'] = True
                    c['distance_stop'] = False
                    c['route_km'] = pt_km
                    c['meal_window'] = window_type
                    c['nearby_places'] = (places or [])[:3]
                    c['price'] = c.get('price') if c.get('price') is not None else 0.1
                    c['max_power'] = c.get('max_power') if c.get('max_power') is not None else 100.0
                    c['is_fast'] = c.get('is_fast') if c.get('is_fast') is not None else True
                    c['num_points'] = c.get('num_points') if c.get('num_points') is not None else 4
                    c['distance'] = addr.get('Distance') if addr.get('Distance') is not None else 0.1
                    meal_chargers.append(c)
        unique_meal_chargers = {c['ID']: c for c in meal_chargers}.values()
        for c in unique_meal_chargers:
            all_chargers.append({'raw': c, **c})
    ranked = rank_and_filter_chargers(all_chargers, priorities or [])
    return ranked


