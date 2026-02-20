
"""
traffic_time.py

Provides functions to fetch and print travel time (with traffic) for a route using TomTom API.

Usage (from routing-main.py):
    from traffic_time import print_travel_time_with_traffic, get_travel_time_from_coords
    print_travel_time_with_traffic(start_coords, dest_coords)
    travel_time_sec = get_travel_time_from_coords(start_coords, dest_coords)
"""
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1] / "energy-consumption"))
from fetch_traffic_data import fetch_travel_time

def print_travel_time_with_traffic(start_coords, dest_coords):
    """
    Fetches and prints travel time (with traffic) using TomTom API.
    Args:
        start_coords: (lat, lon) tuple
        dest_coords: (lat, lon) tuple
    """
    travel_time_sec = fetch_travel_time(
        start_coords[0], start_coords[1], dest_coords[0], dest_coords[1]
    )
    if travel_time_sec is not None:
        print(f"Estimated travel time (with traffic): {travel_time_sec/60:.1f} minutes")
    else:
        print("Could not fetch travel time from TomTom API.")

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
