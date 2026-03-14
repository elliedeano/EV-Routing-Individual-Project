import os

import polyline
import requests

from backend.routing.services.geocoding import ORS_API_KEY


REQUEST_TIMEOUT_SECONDS = float(os.getenv("EXTERNAL_API_TIMEOUT_SECONDS", "10"))


def get_route(start_coords, dest_coords):
    if not ORS_API_KEY:
        raise RuntimeError("Missing required environment variable: ORS_API_KEY")

    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_API_KEY}
    body = {
        "coordinates": [
            [start_coords[1], start_coords[0]],
            [dest_coords[1], dest_coords[0]],
        ]
    }
    response = requests.post(url, json=body, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    if not data.get("routes"):
        raise RuntimeError("ORS returned no route")
    return polyline.decode(data["routes"][0]["geometry"])
