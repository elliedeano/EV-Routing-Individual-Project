import requests
import os
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


def fetch_route_summary(start_lat, start_lon, end_lat, end_lon, depart_at=None):
    """
    Fetches TomTom route summary for a route between two coordinates.
    Returns the `summary` dict or None if the API call fails.
    """
    api_key = os.getenv("TOMTOM_API_KEY")
    if not api_key:
        return None
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
    depart_at_value = _normalize_depart_at(depart_at)
    if depart_at_value:
        params["departAt"] = depart_at_value
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        routes = data.get("routes", [])
        if not routes:
            return None
        return routes[0].get("summary", {})
    except Exception:
        return None

def fetch_travel_time(start_lat, start_lon, end_lat, end_lon, depart_at=None):
    """
    Fetches travel time (in seconds) from TomTom API for a route between two coordinates.
    Returns None if the API call fails.
    """
    summary = fetch_route_summary(start_lat, start_lon, end_lat, end_lon, depart_at=depart_at)
    if not summary:
        return None
    return summary.get("travelTimeInSeconds")
