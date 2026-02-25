import requests

def fetch_travel_time(start_lat, start_lon, end_lat, end_lon):
    """
    Fetches travel time (in seconds) from TomTom API for a route between two coordinates.
    Returns None if the API call fails.
    """
    api_key = "AlmtymL0xYZG08ULKfWbjWOg6PzcZtEd"
    url = (
        f"https://api.tomtom.com/routing/1/calculateRoute/"
        f"{start_lat},{start_lon}:{end_lat},{end_lon}/json"
    )
    params = {
        "key": api_key,
        "traffic": "true",
        "travelMode": "car",
        "computeTravelTimeFor": "all"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        routes = data.get("routes", [])
        if not routes:
            return None
        summary = routes[0].get("summary", {})
        return summary.get("travelTimeInSeconds")
    except Exception:
        return None
