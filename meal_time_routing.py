def get_nearby_food_places(lat, lon, radius=500, limit=5, window_type="lunch"):
    """
    Returns a list of names of food/cafe venues within radius (meters) of (lat, lon) using Yelp Fusion API.
    window_type: "breakfast", "lunch", "dinner", or "coffee". Determines categories searched.
    """
    categories_by_window = {
        "breakfast": "breakfast_brunch,coffee,cafes,supermarkets",
        "lunch": "restaurants,food,cafes,fastfood,supermarkets",
        "dinner": "restaurants,food,cafes,fastfood,supermarkets",
        "coffee": "coffee,supermarkets"
    }
    categories = categories_by_window.get(window_type, "restaurants,food,cafes,fastfood,supermarkets")
    url = "https://api.yelp.com/v3/businesses/search"
    headers = {
        "Authorization": f"Bearer {YELP_API_KEY}"
    }
    params = {
        "latitude": lat,
        "longitude": lon,
        "radius": radius,
        "categories": categories,
        "limit": limit
    }
    try:
        resp = requests.get(url, headers=headers, params=params)
    except Exception:
        return []
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    return [b.get("name", "Unknown") for b in data.get("businesses", [])]
import requests
from datetime import datetime, timedelta




# Yelp Fusion API Key (replace with your own if needed)
YELP_API_KEY = "AlQNzNZ0I0M6dF_3sfXTLiQjrntZMOPdyg1iqMCAbeWzyDnR6K6MBrt71jXboqh7EdC5_33JTAehhMW-WgSDCSyrpgZY82nn7mYcsurtxmtJqMCJrQBMi7fRkjubaXYx"

# Define time windows for breakfast, coffee, lunch, and dinner
TIME_WINDOWS = {
    "breakfast": (7, 0, 9, 30),   # 07:00-09:30
    "lunch":    (12, 0, 14, 0),   # 12:00-14:00
    "dinner":   (18, 0, 20, 0),   # 18:00-20:00
    "coffee":   (9, 0, 11, 0),    # 09:00-11:00
}

def is_meal_time(arrival_time, window_type="lunch"):
    """
    Returns True if arrival_time is within the specified window_type (breakfast, lunch, dinner, coffee).
    """
    if window_type not in TIME_WINDOWS:
        raise ValueError(f"Unknown window_type: {window_type}")
    start_h, start_m, end_h, end_m = TIME_WINDOWS[window_type]
    start = arrival_time.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = arrival_time.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    return start <= arrival_time <= end


def has_nearby_food(lat, lon, radius=500, window_type="lunch"):
    """
    Returns True if there are food/cafe venues within radius (meters) of (lat, lon) using Yelp Fusion API.
    window_type: "breakfast", "lunch", "dinner", or "coffee". Determines categories searched.
    """
    categories_by_window = {
        "breakfast": "breakfast_brunch,coffee,cafes,supermarkets",
        "lunch": "restaurants,food,cafes,fastfood,supermarkets",
        "dinner": "restaurants,food,cafes,fastfood,supermarkets",
        "coffee": "coffee,supermarkets"
    }
    categories = categories_by_window.get(window_type, "restaurants,food,cafes,fastfood,supermarkets")
    url = "https://api.yelp.com/v3/businesses/search"
    headers = {
        "Authorization": f"Bearer {YELP_API_KEY}"
    }
    params = {
        "latitude": lat,
        "longitude": lon,
        "radius": radius,
        "categories": categories,
        "limit": 1
    }
    try:
        resp = requests.get(url, headers=headers, params=params)
    except Exception as e:
        return False
    if resp.status_code != 200:
        return False
    try:
        data = resp.json()
    except Exception:
        return False
    return len(data.get("businesses", [])) > 0


def filter_meal_time_chargers(chargers, journey_start):
    """
    chargers: list of dicts, each with at least 'Latitude', 'Longitude', 'minutes_from_start'
    journey_start: datetime object
    Returns: list of chargers suitable for meal stops
    """
    meal_stops = []
    for charger in chargers:
        arrival_time = journey_start + timedelta(minutes=charger['minutes_from_start'])
        if is_meal_time(arrival_time):
            if has_nearby_food(charger['Latitude'], charger['Longitude']):
                charger['arrival_time'] = arrival_time
                meal_stops.append(charger)
    return meal_stops


if __name__ == "__main__":
    # Example usage (replace with your real data and routing logic)
    chargers = [
        {"ChargerID": 1, "Latitude": 51.5, "Longitude": -0.1, "minutes_from_start": 180},
        {"ChargerID": 2, "Latitude": 53.48, "Longitude": -2.24, "minutes_from_start": 240},
        # ... more chargers ...
    ]

    # Ask user for journey start time
    user_time = input("Enter your journey start time (HH:MM) or type 'now': ").strip().lower()
    if user_time == 'now':
        journey_start = datetime.now()
    else:
        try:
            today = datetime.now()
            hour, minute = map(int, user_time.split(":"))
            journey_start = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
            # If the time has already passed today, assume it's for tomorrow
            if journey_start < today:
                journey_start += timedelta(days=1)
        except Exception as e:
            print("Invalid time format. Using current time.")
            journey_start = datetime.now()

    meal_stops = filter_meal_time_chargers(chargers, journey_start)
    print(f"Found {len(meal_stops)} meal-time chargers:")
    for charger in meal_stops:
        print(f"Charger {charger['ChargerID']} at {charger['arrival_time'].strftime('%H:%M')}")
