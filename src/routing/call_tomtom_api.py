"""
call_tomtom_api.py

This script demonstrates how to use the start and end coordinates from routing-main.py to fetch travel time from the TomTom API.
"""
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1] / "energy-consumption"))
from fetch_traffic_data import fetch_travel_time

def get_travel_time_from_coords(start_coords, dest_coords):
    """
    Fetches travel time (in seconds) from TomTom API using start and end coordinates.
    Args:
        start_coords: (lat, lon) tuple
        dest_coords: (lat, lon) tuple
    Returns:
        travel_time_sec: Estimated travel time in seconds (or None if error)
    """
    return fetch_travel_time(
        start_coords[0], start_coords[1], dest_coords[0], dest_coords[1]
    )

if __name__ == "__main__":
    # Example usage: manually enter coordinates or import from routing-main
    start_coords = (51.5074, -0.1278)  # London
    dest_coords = (52.4862, -1.8904)   # Birmingham
    travel_time_sec = get_travel_time_from_coords(start_coords, dest_coords)
    if travel_time_sec is not None:
        print(f"Estimated travel time (with traffic): {travel_time_sec/60:.1f} minutes")
    else:
        print("Could not fetch travel time from TomTom API.")
