import os
from datetime import datetime, timedelta
import requests
import logging

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT_SECONDS = float(os.getenv("EXTERNAL_API_TIMEOUT_SECONDS", "10"))

YELP_SEARCH_URL = "https://api.yelp.com/v3/businesses/search"

TIME_WINDOWS = {
    "breakfast": (7, 0, 9, 30),
    "lunch": (12, 0, 14, 0),
    "dinner": (18, 0, 20, 0),
    "coffee": (9, 0, 11, 0),
}

CATEGORIES_BY_WINDOW = {
    "breakfast": "breakfast_brunch,coffee,cafes,supermarkets",
    "lunch": "restaurants,food,cafes,fastfood,supermarkets",
    "dinner": "restaurants,food,cafes,fastfood,supermarkets",
    "coffee": "coffee,supermarkets",
}

DEFAULT_CATEGORIES = CATEGORIES_BY_WINDOW["lunch"]


def _search_yelp_businesses(lat, lon, *, radius, limit, window_type):
    # Read the API key at call time so changes to env vars are picked up
    yelp_key = os.getenv("YELP_API_KEY")
    if not yelp_key:
        logger.debug("YELP_API_KEY not set; skipping Yelp lookup")
        return []

    categories = CATEGORIES_BY_WINDOW.get(window_type, DEFAULT_CATEGORIES)
    params = {
        "latitude": lat,
        "longitude": lon,
        "radius": radius,
        "categories": categories,
        "limit": limit,
    }
    headers = {"Authorization": f"Bearer {yelp_key}"}

    try:
        resp = requests.get(
            YELP_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception("Yelp API request failed")
        return []

    if resp.status_code != 200:
        logger.debug("Yelp returned status %s", resp.status_code)
        return []

    try:
        data = resp.json()
    except Exception:
        return []

    return data.get("businesses", [])


def get_nearby_food_places(lat, lon, radius=500, limit=5, window_type="lunch"):
    businesses = _search_yelp_businesses(
        lat,
        lon,
        radius=radius,
        limit=limit,
        window_type=window_type,
    )
    return [business.get("name", "Unknown") for business in businesses]


def is_meal_time(arrival_time, window_type="lunch"):
    if window_type not in TIME_WINDOWS:
        raise ValueError(f"Unknown window_type: {window_type}")
    start_h, start_m, end_h, end_m = TIME_WINDOWS[window_type]
    start = arrival_time.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = arrival_time.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    return start <= arrival_time <= end


def _window_bounds(base_time, window_type):
    start_h, start_m, end_h, end_m = TIME_WINDOWS[window_type]
    window_start = base_time.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    window_end = base_time.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    return window_start, window_end


def _interval_overlaps_window(start_time, end_time, window_type):
    if end_time < start_time:
        start_time, end_time = end_time, start_time
    window_start, window_end = _window_bounds(start_time, window_type)
    return max(start_time, window_start) <= min(end_time, window_end)


def has_nearby_food(lat, lon, radius=500, window_type="lunch"):
    businesses = _search_yelp_businesses(
        lat,
        lon,
        radius=radius,
        limit=1,
        window_type=window_type,
    )
    return bool(businesses)


def filter_meal_time_chargers(chargers, journey_start, window_type=None):
    meal_stops = []
    if window_type is not None and window_type not in TIME_WINDOWS:
        raise ValueError(f"Unknown window_type: {window_type}")

    candidate_windows = [window_type] if window_type else list(TIME_WINDOWS.keys())

    for charger in chargers:
        minutes_from_start = charger.get('minutes_from_start', 0)
        arrival_time = journey_start + timedelta(minutes=minutes_from_start)

        lat = charger.get('Latitude', charger.get('latitude'))
        lon = charger.get('Longitude', charger.get('longitude'))
        if lat is None or lon is None:
            continue

        matched_windows = [
            window
            for window in candidate_windows
            if _interval_overlaps_window(journey_start, arrival_time, window)
        ]

        if not matched_windows:
            continue

        accepted_window = None
        for window in matched_windows:
            if has_nearby_food(lat, lon, window_type=window):
                accepted_window = window
                break

        if accepted_window:
            enriched = dict(charger)
            enriched['arrival_time'] = arrival_time
            enriched['meal_window'] = accepted_window
            enriched['meal_windows_matched'] = matched_windows
            meal_stops.append(enriched)

    return meal_stops


if __name__ == "__main__":
    chargers = [
        {"ChargerID": 1, "Latitude": 51.5, "Longitude": -0.1, "minutes_from_start": 180},
        {"ChargerID": 2, "Latitude": 53.48, "Longitude": -2.24, "minutes_from_start": 240},
    ]

    user_time = input("Enter your journey start time (HH:MM) or type 'now': ").strip().lower()
    if user_time == 'now':
        journey_start = datetime.now()
    else:
        try:
            today = datetime.now()
            hour, minute = map(int, user_time.split(":"))
            journey_start = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if journey_start < today:
                journey_start += timedelta(days=1)
        except Exception:
            print("Invalid time format. Using current time.")
            journey_start = datetime.now()

    meal_stops = filter_meal_time_chargers(chargers, journey_start)
    print(f"Found {len(meal_stops)} meal-time chargers:")
    for charger in meal_stops:
        print(f"Charger {charger['ChargerID']} at {charger['arrival_time'].strftime('%H:%M')}")