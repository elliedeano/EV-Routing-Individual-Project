import math
from typing import Optional, List, Dict, Any
from backend.routing.find_meal_based_chargers import find_meal_based_chargers
from backend.routing.traffic_calculations import get_traffic_delay_percent
from backend.routing.services.geocoding import geocode_postcode
from backend.routing.services.route_provider import get_route
from backend.routing.services.charger_provider import get_chargers_near_route
from backend.routing.services.simulation import trip_simulation, route_segment_distance
from backend.charger_ranking.rank_chargers import rank_and_filter_chargers


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


def get_car_specs(car_model):
    from pathlib import Path
    import pandas as pd

    project_root = Path(__file__).resolve().parents[3]
    csv_path = project_root / "backend" / "energy-consumption" / "output_files" / "scaled_trip_energy.csv"
    df = pd.read_csv(csv_path)
    car_rows = df[df["Car Model"] == car_model]
    wh_per_km = car_rows["wh_per_km_raw"].mean() if not car_rows.empty else 200
    return {
        "battery_kwh": 60,
        "wh_per_km": wh_per_km,
    }


def compute_route(
    start_postcode: str,
    end_postcode: str,
    soc: float,
    car_model: Optional[str] = None,
    umbrella_choice: str = 'distance',
    priorities: Optional[List[str]] = None,
    journey_start: Optional[str] = None,
) -> Dict[str, Any]:
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

    start_coords = geocode_postcode(start_postcode)
    dest_coords = geocode_postcode(end_postcode)
    route = get_route(start_coords, dest_coords)

    if car_model:
        car_specs = get_car_specs(car_model)
    else:
        car_specs = {"battery_kwh": 60, "wh_per_km": 200}

    stops, total_km = trip_simulation(route, car_specs, soc)

    usable_wh = car_specs["battery_kwh"] * 1000 * (soc / 100)
    mean_wh_per_km = car_specs.get("wh_per_km", 200)
    est_reachable_km = usable_wh / mean_wh_per_km if mean_wh_per_km else 0.0

    if est_reachable_km >= total_km:
        return {
            'total_km': total_km,
            'est_range_km': est_reachable_km,
            'start_coords': [start_coords[0], start_coords[1]],
            'chargers': [],
        }

    try:
        if umbrella_choice == 'meal':
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
            all_chargers = []
            for stop in stops:
                if stop.get('chargers'):
                    for charger in stop['chargers']:
                        addr = charger.get('AddressInfo', {})
                        lat = addr.get('Latitude')
                        lon = addr.get('Longitude')
                        charger_km = None
                        try:
                            if lat is not None and lon is not None:
                                charger_km = route_segment_distance(route[0][0], route[0][1], lat, lon)
                                traffic_delay = _compute_traffic_delay(start_coords, (lat, lon), depart_at=journey_start_dt)
                            else:
                                traffic_delay = 0.0
                        except Exception:
                            charger_km = None
                            traffic_delay = 0.0
                        charger['route_km'] = charger_km
                        charger['traffic_delay'] = traffic_delay
                        charger['meal_stop'] = False
                        charger['distance_stop'] = True
                        charger['price'] = charger.get('price', 0.1)
                        charger['max_power'] = charger.get('max_power', 100.0)
                        charger['is_fast'] = charger.get('is_fast', True)
                        charger['num_points'] = charger.get('num_points', 4)
                        charger['distance'] = addr.get('Distance', 0.1)
                        all_chargers.append({'raw': charger, **charger})
            ranked = rank_and_filter_chargers(all_chargers, priorities or [])
    except Exception:
        ranked = []

    if not ranked:
        try:
            sample_points = []
            if route:
                sample_points.append(route[0])
                if len(route) > 2:
                    sample_points.append(route[len(route) // 2])
                    sample_points.append(route[-1])

            all_chargers = []
            seen = set()
            for point in sample_points:
                try:
                    found = get_chargers_near_route([point], max_results=10, distance_km=10)
                except Exception:
                    found = []

                for charger in (found or []):
                    cid = charger.get('ID')
                    if cid in seen:
                        continue
                    seen.add(cid)
                    addr = charger.get('AddressInfo', {})
                    lat = addr.get('Latitude')
                    lon = addr.get('Longitude')
                    route_km = None
                    try:
                        if lat is not None and lon is not None:
                            route_km = route_segment_distance(route[0][0], route[0][1], lat, lon)
                            traffic_delay = _compute_traffic_delay(start_coords, (lat, lon), depart_at=journey_start_dt)
                        else:
                            traffic_delay = 0.0
                    except Exception:
                        route_km = None
                        traffic_delay = 0.0

                    charger['route_km'] = route_km
                    charger['traffic_delay'] = traffic_delay
                    charger['meal_stop'] = False
                    charger['distance_stop'] = True
                    charger['price'] = charger.get('price', 0.1)
                    charger['max_power'] = charger.get('max_power', 100.0)
                    charger['is_fast'] = charger.get('is_fast', True)
                    charger['num_points'] = charger.get('num_points', 4)
                    charger['distance'] = addr.get('Distance', 0.1)
                    all_chargers.append({'raw': charger, **charger})

            if all_chargers:
                ranked = rank_and_filter_chargers(all_chargers, priorities or [])
        except Exception:
            pass

    out_chargers = []
    for charger in (ranked or []):
        raw = charger.get('raw', charger)
        addr = raw.get('AddressInfo', {})
        traffic_delay = charger.get('traffic_delay') if 'traffic_delay' in charger else raw.get('traffic_delay')
        traffic_delay = _safe_float(traffic_delay, default=0.0)

        if traffic_delay == 0.0:
            lat = addr.get('Latitude')
            lon = addr.get('Longitude')
            if lat is not None and lon is not None:
                try:
                    traffic_delay = _compute_traffic_delay(start_coords, (lat, lon), depart_at=journey_start_dt)
                except Exception:
                    traffic_delay = 0.0

        out_chargers.append(
            {
                'id': raw.get('ID') or addr.get('ID'),
                'title': addr.get('Title'),
                'max_power': charger.get('max_power') or raw.get('max_power'),
                'is_fast': charger.get('is_fast') if 'is_fast' in charger else raw.get('is_fast'),
                'route_km': charger.get('route_km') if 'route_km' in charger else raw.get('route_km'),
                'distance': charger.get('distance') if 'distance' in charger else addr.get('Distance'),
                'latitude': addr.get('Latitude'),
                'longitude': addr.get('Longitude'),
                'meal_window': charger.get('meal_window') if 'meal_window' in charger else raw.get('meal_window'),
                'nearby_places': charger.get('nearby_places') if 'nearby_places' in charger else raw.get('nearby_places'),
                'price': charger.get('price') if 'price' in charger else raw.get('price'),
                'num_points': charger.get('num_points') if 'num_points' in charger else raw.get('num_points'),
                'traffic_delay': traffic_delay,
                'meal_stop': charger.get('meal_stop') if 'meal_stop' in charger else raw.get('meal_stop', False),
                'score': charger.get('score'),
                'breakdown': charger.get('breakdown'),
            }
        )

    return {
        'total_km': total_km,
        'est_range_km': est_reachable_km,
        'start_coords': [start_coords[0], start_coords[1]],
        'chargers': out_chargers,
    }
