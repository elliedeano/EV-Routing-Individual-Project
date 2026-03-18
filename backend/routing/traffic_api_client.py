import requests
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


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
    # Prefer environment-provided key but fall back to the project's default
    # TomTom key (used elsewhere in the repo) so traffic calculations still
    # work when the env var is not set during local development.
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
    depart_at_value = _normalize_depart_at(depart_at)
    if depart_at_value:
        params["departAt"] = depart_at_value
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        routes = data.get("routes", [])
        if not routes:
            logger.debug("TomTom response had no routes: %s", data)
            return None
        summary = routes[0].get("summary", {})
        logger.debug("TomTom route summary: %s", summary)
        return summary
    except Exception as exc:
        logger.exception("Error fetching TomTom route summary: %s", exc)
        return None

def fetch_travel_time(start_lat, start_lon, end_lat, end_lon, depart_at=None):
    summary = fetch_route_summary(start_lat, start_lon, end_lat, end_lon, depart_at=depart_at)
    if not summary:
        return None
    return summary.get("travelTimeInSeconds")
