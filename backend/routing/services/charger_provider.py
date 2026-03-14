import os

import requests


OCM_API_KEY = os.getenv("OCM_API_KEY")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("EXTERNAL_API_TIMEOUT_SECONDS", "10"))


def get_chargers_near_route(route_coords, max_results=5, distance_km=10):
    if not OCM_API_KEY:
        raise RuntimeError("Missing required environment variable: OCM_API_KEY")

    chargers = []
    sample_points = [route_coords[0], route_coords[-1]]

    if len(route_coords) > 8:
        step = max(1, len(route_coords) // 6)
        sample_points += route_coords[1:-1:step]

    for lat, lon in sample_points:
        response = requests.get(
            "https://api.openchargemap.io/v3/poi/",
            params={
                "key": OCM_API_KEY,
                "latitude": lat,
                "longitude": lon,
                "distance": distance_km,
                "distanceunit": "KM",
                "maxresults": max_results,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        chargers += response.json()

    unique = {charger["ID"]: charger for charger in chargers}
    return list(unique.values())
