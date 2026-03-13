"""Programmatic API logic for computing routes and chargers.
This wraps routing helpers in `routing_main.py`
to provide a single backend-friendly function `compute_route`.
"""
from pathlib import Path
import sys
import math
from typing import Optional, List, Dict, Any

# Ensure we can import routing_main helpers and meal_time_routing
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / 'src' / 'routing'))
import routing_main
sys.path.insert(0, str(project_root))
from traffic import get_traffic_delay_percent as get_traffic_delay_percent


def _safe_float(value, default=0.0):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    if out < 0:
        return 0.0
    return out


def _compute_traffic_delay(start_coords, dest_coords, depart_at=None):
    try:
        return _safe_float(get_traffic_delay_percent(start_coords, dest_coords, depart_at=depart_at), default=0.0)
    except Exception:
        return 0.0


def compute_route(
    start_postcode: str,
    end_postcode: str,
    soc: float,
    car_model: Optional[str] = None,
    umbrella_choice: str = 'distance',
    priorities: Optional[List[str]] = None,
    journey_start: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute route and return structured response for the API.

    Returns a dict with keys: total_km, est_range_km, chargers (list).
    Each charger in list is a dict compatible with backend.api.ChargerOut fields.
    """
    # Parse journey_start
    from datetime import datetime, timedelta
    if journey_start:
        if isinstance(journey_start, str) and journey_start.lower() == 'now':
            journey_start_dt = datetime.now()
        elif isinstance(journey_start, str):
            try:
                today = datetime.now()
                hour, minute = map(int, journey_start.split(":"))
                journey_start_dt = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if journey_start_dt < today:
                    journey_start_dt += timedelta(days=1)
            except Exception:
                journey_start_dt = datetime.now()
        else:
            journey_start_dt = journey_start
    else:
        journey_start_dt = datetime.now()

    # Geocode and compute route
    start_coords = routing_main.geocode_postcode(start_postcode)
    dest_coords = routing_main.geocode_postcode(end_postcode)
    route = routing_main.get_route(start_coords, dest_coords)

    # Car specs
    if car_model:
        car_specs = routing_main.get_car_specs(car_model)
    else:
        # fallback to default
        car_specs = {"battery_kwh": 60, "wh_per_km": 200}

    # Trip simulation
    stops, total_km = routing_main.trip_simulation(route, car_specs, soc)

    # Estimated reachable km
    usable_wh = car_specs["battery_kwh"] * 1000 * (soc / 100)
    mean_wh_per_km = car_specs.get("wh_per_km", 200)
    est_reachable_km = usable_wh / mean_wh_per_km if mean_wh_per_km else 0.0

    # If the estimated range already covers the journey, no charging stop is needed.
    if est_reachable_km >= total_km:
        return {
            'total_km': total_km,
            'est_range_km': est_reachable_km,
            'start_coords': [start_coords[0], start_coords[1]],
            'chargers': []
        }

    # Determine chargers depending on umbrella choice
    chargers = []
    # Try to use the dedicated helper if umbrella_choice == 'meal'
    try:
        if umbrella_choice == 'meal':
            # import the helper that already contains meal-based logic
            from find_meal_based_chargers import find_meal_based_chargers
            ranked = find_meal_based_chargers(
                route,
                car_specs,
                soc,
                journey_start_dt,
                priorities=priorities,
                start_coords=start_coords,
                traffic_depart_at=journey_start_dt,
            )
        else:
            # distance-based: build all_chargers similar to routing_main and rank
            # collect chargers from stops
            all_chargers = []
            from charger_ranking.rank_chargers import rank_and_filter_chargers
            for s in stops:
                if s.get('chargers'):
                    for c in s['chargers']:
                        addr = c.get('AddressInfo', {})
                        lat = addr.get('Latitude')
                        lon = addr.get('Longitude')
                        charger_km = None
                        try:
                            if lat is not None and lon is not None:
                                charger_km = routing_main.route_segment_distance(route[0][0], route[0][1], lat, lon)
                                traffic_delay = _compute_traffic_delay(start_coords, (lat, lon), depart_at=journey_start_dt)
                            else:
                                traffic_delay = 0.0
                        except Exception:
                            charger_km = None
                            traffic_delay = 0.0
                        c['route_km'] = charger_km
                        c['traffic_delay'] = traffic_delay
                        c['meal_stop'] = False
                        c['distance_stop'] = True
                        # Defaults for ranking
                        c['price'] = c.get('price', 0.1)
                        c['max_power'] = c.get('max_power', 100.0)
                        c['is_fast'] = c.get('is_fast', True)
                        c['num_points'] = c.get('num_points', 4)
                        c['distance'] = addr.get('Distance', 0.1)
                        all_chargers.append({'raw': c, **c})
            ranked = rank_and_filter_chargers(all_chargers, priorities or [])
    except Exception as e:
        # If the specialized helper fails, fallback to empty list but log
        print("api_logic.compute_route: error selecting chargers:", e)
        ranked = []

    # If nothing was found by the specialist logic, try a simple nearby search
    if not ranked:
        try:
            print("api_logic.compute_route: no chargers found by primary logic, doing nearby fallback")
            from charger_ranking.rank_chargers import rank_and_filter_chargers
            # Sample a few points along the route (start, middle, end)
            sample_points = []
            if route:
                sample_points.append(route[0])
                if len(route) > 2:
                    sample_points.append(route[len(route)//2])
                    sample_points.append(route[-1])
            all_chargers = []
            # Use routing_main.get_chargers_near_route if available
            try:
                get_near = routing_main.get_chargers_near_route
            except Exception:
                get_near = None
            seen = set()
            for pt in sample_points:
                if get_near:
                    try:
                        found = get_near([pt], max_results=10, distance_km=10)
                    except Exception:
                        found = []
                else:
                    found = []
                for c in (found or []):
                    cid = c.get('ID')
                    if cid in seen:
                        continue
                    seen.add(cid)
                    addr = c.get('AddressInfo', {})
                    lat = addr.get('Latitude')
                    lon = addr.get('Longitude')
                    route_km = None
                    try:
                        if lat is not None and lon is not None:
                            route_km = routing_main.route_segment_distance(route[0][0], route[0][1], lat, lon)
                            traffic_delay = _compute_traffic_delay(start_coords, (lat, lon), depart_at=journey_start_dt)
                        else:
                            traffic_delay = 0.0
                    except Exception:
                        route_km = None
                        traffic_delay = 0.0
                    # Normalise fields expected by the ranker
                    c['route_km'] = route_km
                    c['traffic_delay'] = traffic_delay
                    c['meal_stop'] = False
                    c['distance_stop'] = True
                    c['price'] = c.get('price', 0.1)
                    c['max_power'] = c.get('max_power', 100.0)
                    c['is_fast'] = c.get('is_fast', True)
                    c['num_points'] = c.get('num_points', 4)
                    c['distance'] = addr.get('Distance', 0.1)
                    all_chargers.append({'raw': c, **c})
            if all_chargers:
                ranked = rank_and_filter_chargers(all_chargers, priorities or [])
                print(f"api_logic.compute_route: fallback found {len(ranked)} chargers")
        except Exception as e:
            print("api_logic.compute_route: fallback search failed:", e)

    # Map ranked chargers to API-friendly schema
    out_chargers = []
    for c in (ranked or []):
        # c may be wrapper with 'raw'
        raw = c.get('raw', c)
        addr = raw.get('AddressInfo', {})
        traffic_delay = c.get('traffic_delay') if 'traffic_delay' in c else raw.get('traffic_delay')
        traffic_delay = _safe_float(traffic_delay, default=0.0)

        # Defensive fallback: if delay is missing/zero, recompute from coordinates for returned chargers.
        # This keeps frontend behaviour stable when upstream values are absent.
        if traffic_delay == 0.0:
            lat = addr.get('Latitude')
            lon = addr.get('Longitude')
            if lat is not None and lon is not None:
                try:
                    traffic_delay = _compute_traffic_delay(start_coords, (lat, lon), depart_at=journey_start_dt)
                except Exception:
                    traffic_delay = 0.0

        out_chargers.append({
            'id': raw.get('ID') or addr.get('ID'),
            'title': addr.get('Title'),
            'max_power': c.get('max_power') or raw.get('max_power'),
            'is_fast': c.get('is_fast') if 'is_fast' in c else raw.get('is_fast'),
            'route_km': c.get('route_km') if 'route_km' in c else raw.get('route_km'),
            'distance': c.get('distance') if 'distance' in c else addr.get('Distance'),
            'latitude': addr.get('Latitude'),
            'longitude': addr.get('Longitude'),
            'meal_window': c.get('meal_window') if 'meal_window' in c else raw.get('meal_window'),
            'nearby_places': c.get('nearby_places') if 'nearby_places' in c else raw.get('nearby_places'),
            'price': c.get('price') if 'price' in c else raw.get('price'),
            'num_points': c.get('num_points') if 'num_points' in c else raw.get('num_points'),
            'traffic_delay': traffic_delay,
            'meal_stop': c.get('meal_stop') if 'meal_stop' in c else raw.get('meal_stop', False),
            'score': c.get('score'),
            'breakdown': c.get('breakdown')
        })

    return {
        'total_km': total_km,
        'est_range_km': est_reachable_km,
        'start_coords': [start_coords[0], start_coords[1]],
        'chargers': out_chargers,
    }
