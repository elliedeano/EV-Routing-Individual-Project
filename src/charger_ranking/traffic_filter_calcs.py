import requests
from datetime import datetime

def _normalize_depart_at(depart_at):
    if depart_at is None:
        return None
    if isinstance(depart_at, datetime):
        if depart_at.tzinfo is None:
            depart_at = depart_at.astimezone()
        return depart_at.isoformat(timespec="seconds")
    if isinstance(depart_at, str):
        return depart_at
    return None


def get_traffic_delay_percent(start_coords, dest_coords, depart_at=None):
    """
    Returns the percentage traffic delay for a route using TomTom API.
    """
    api_key = "AlmtymL0xYZG08ULKfWbjWOg6PzcZtEd"
    url = (
        f"https://api.tomtom.com/routing/1/calculateRoute/"
        f"{start_coords[0]},{start_coords[1]}:"
        f"{dest_coords[0]},{dest_coords[1]}/json"
    )
    params = {
        "key": api_key,
        "traffic": "true",
        "travelMode": "car",
        "computeTravelTimeFor": "all"
    }
    depart_at_value = _normalize_depart_at(depart_at)
    if depart_at_value:
        params["departAt"] = depart_at_value
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        routes = data.get("routes", [])
        if not routes:
            return 0.0
        summary = routes[0].get("summary", {})
        time_with_traffic_sec = summary.get("travelTimeInSeconds")
        time_no_traffic_sec = summary.get("noTrafficTravelTimeInSeconds")
        if time_with_traffic_sec and time_no_traffic_sec and time_no_traffic_sec > 0:
            delay_pct = ((time_with_traffic_sec - time_no_traffic_sec) / time_no_traffic_sec) * 100
            return max(delay_pct, 0.0)
        else:
            return 0.0
    except Exception:
        return 0.0
