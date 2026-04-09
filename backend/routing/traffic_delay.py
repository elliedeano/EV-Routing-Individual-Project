import requests
import os
import logging
from datetime import datetime

def normalise_departure_time(depart_at):
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
    api_key = os.getenv("TOMTOM_API_KEY") or "AlmtymL0xYZG08ULKfWbjWOg6PzcZtEd"
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
    depart_at_value = normalise_departure_time(depart_at)
    if depart_at_value:
        params["departAt"] = depart_at_value
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        routes = data.get("routes", [])
        if not routes:
            return None
        summary = routes[0].get("summary", {})
        return summary
    except Exception as exc:
        return None

def fetch_travel_time_from_coords(start_coords, dest_coords, depart_at=None):
    return fetch_travel_time(
        start_coords[0], start_coords[1], dest_coords[0], dest_coords[1], depart_at=depart_at)

def fetch_travel_time(start_lat, start_lon, end_lat, end_lon, depart_at=None):
    totals = fetch_route_summary(start_lat, start_lon, end_lat, end_lon, depart_at=depart_at)
    if not totals:
        return None
    return totals.get("travelTimeInSeconds")

def fetch_traffic_delay_percent(start_coords, dest_coords, depart_at=None):
    summary = fetch_route_summary(
        start_coords[0], start_coords[1], dest_coords[0], dest_coords[1], depart_at=depart_at)
    if not summary:
        return 0.0
    try:
        time_traffic_sec = summary.get("travelTimeInSeconds")
        time_no_traffic_sec = summary.get("noTrafficTravelTimeInSeconds")
        if time_traffic_sec and time_no_traffic_sec and time_no_traffic_sec > 0:
            delay_percent = ((time_traffic_sec - time_no_traffic_sec) / time_no_traffic_sec) * 100
        return max(delay_percent, 0.0)
    except Exception:
        return 0.0

