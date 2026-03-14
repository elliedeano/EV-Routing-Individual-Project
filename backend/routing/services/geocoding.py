import os

import requests


ORS_API_KEY = os.getenv("ORS_API_KEY")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("EXTERNAL_API_TIMEOUT_SECONDS", "10"))


def _is_placeholder_key(value: str) -> bool:
    if value is None:
        return True
    v = value.strip().lower()
    return (
        not v
        or v.startswith("your_")
        or v.endswith("_here")
        or v in {"changeme", "replace_me"}
    )


def geocode_postcode(postcode):
    if _is_placeholder_key(ORS_API_KEY):
        raise RuntimeError(
            "Missing valid ORS_API_KEY. Set a real OpenRouteService key in backend/.env or .env."
        )

    url = "https://api.openrouteservice.org/geocode/search"
    params = {
        "api_key": ORS_API_KEY,
        "text": postcode,
        "boundary.country": "GB",
    }
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    features = response.json().get("features", [])
    if not features:
        raise ValueError(f"No result for {postcode}")
    lon, lat = features[0]["geometry"]["coordinates"]
    return lat, lon
