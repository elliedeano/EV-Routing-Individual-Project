
def get_traffic_delay_percent(start_coords, dest_coords):
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
"""
traffic_analysis.py

This script imports start_coords and dest_coords from routing-main.py, calculates:
- Time without traffic (from TomTom free-flow estimate)
- Time with traffic (from TomTom live traffic)
- Prints both times for comparison
"""

from pathlib import Path
import sys
import requests

# Optional: keep if used elsewhere
sys.path.append(str(Path(__file__).resolve().parents[1] / "energy-consumption"))


def analyze_traffic(start_coords, dest_coords, distance_km):
    """
    Prints both ideal (no traffic) and traffic-adjusted times from TomTom API for a given route.

    Args:
        start_coords: (lat, lon) tuple
        dest_coords: (lat, lon) tuple
        distance_km: float, route distance in kilometers
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
        "computeTravelTimeFor": "all"  # 🔑 REQUIRED to get noTrafficTravelTimeInSeconds
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        routes = data.get("routes", [])

        if not routes:
            print("No routes returned from TomTom API.")
            return

        summary = routes[0].get("summary", {})

        time_with_traffic_sec = summary.get("travelTimeInSeconds")
        time_no_traffic_sec = summary.get("noTrafficTravelTimeInSeconds")
        historic_time_sec = summary.get("historicTrafficTravelTimeInSeconds")

        print("\nTraffic Analysis")
        print("----------------")
        print(f"Route distance: {distance_km:.1f} km")

        if time_no_traffic_sec is not None:
            print(f"Ideal / no traffic time: {time_no_traffic_sec / 60:.1f} min")
        else:
            print("No free-flow (no traffic) time available.")

        if time_with_traffic_sec is not None:
            print(f"Live traffic time: {time_with_traffic_sec / 60:.1f} min")
        else:
            print("No live traffic time available.")

        if historic_time_sec is not None:
            print(f"Historic traffic time: {historic_time_sec / 60:.1f} min")

        if time_with_traffic_sec and time_no_traffic_sec:
            delay_min = (time_with_traffic_sec - time_no_traffic_sec) / 60
            print(f"Traffic delay: {delay_min:+.1f} min")

    except requests.exceptions.RequestException as e:
        print(f"HTTP error while calling TomTom API: {e}")
    except Exception as e:
        print(f"Unexpected error during traffic analysis: {e}")
