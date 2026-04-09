import os
import requests


def postcode_to_coords(postcode):
    """Geocode a UK postcode using OpenRouteService.

    Reads `ORS_API_KEY` from the environment at call time so the key
    is respected even if it was loaded after module import.
    """
    key = os.getenv("ORS_API_KEY")
    if not key or not key.strip():
        raise RuntimeError("Missing Open Route Service API key.")

    url = "https://api.openrouteservice.org/geocode/search"
    params = {"api_key": key, "text": postcode, "boundary.country": "GB"}
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    features = response.json().get("features", [])
    if not features:
        raise ValueError(f"No result for {postcode}")
    longitude, latitude = features[0]["geometry"]["coordinates"]
    return latitude, longitude

