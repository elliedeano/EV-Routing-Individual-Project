import os
import requests


def ocm_retrieval(route_coords, max_results=5, distance_km=10):
    """Retrieve nearby chargers from OpenChargeMap.

    Reads `OCM_API_KEY` from the environment at call time so the key
    is respected even if it was loaded after module import.
    """
    key = os.getenv("OCM_API_KEY")
    if not key or not key.strip():
        raise RuntimeError("Missing OCM API key.")

    chargers = []
    subset_coords = [route_coords[0], route_coords[-1]]

    if len(route_coords) > 8:
        step = max(1, len(route_coords) // 6)
        subset_coords += route_coords[1:-1:step]

    for lat, lon in subset_coords:
        call_ocm = requests.get(
            "https://api.openchargemap.io/v3/poi/",
            params={
                "key": key,
                "latitude": lat,
                "longitude": lon,
                "distance": distance_km,
                "distanceunit": "KM",
                "maxresults": max_results,
            },
            timeout=10,
        )
        call_ocm.raise_for_status()
        chargers += call_ocm.json()

    unique_chargers = {charger["ID"]: charger for charger in chargers}
    return list(unique_chargers.values())
