"""
traffic.py
Unified traffic analysis and travel time module for TomTom API.
"""
from fetch_traffic_data import fetch_travel_time, fetch_route_summary

# --- Travel Time Functions ---
def get_travel_time_from_coords(start_coords, dest_coords, depart_at=None):
    """
    Fetches travel time (in seconds) from TomTom API using start and end coordinates.
    Args:
        start_coords: (lat, lon) tuple
        dest_coords: (lat, lon) tuple
    Returns:
        travel_time_sec: Estimated travel time in seconds (or None if error)
    """
    return fetch_travel_time(
        start_coords[0], start_coords[1], dest_coords[0], dest_coords[1], depart_at=depart_at
    )

def print_travel_time_with_traffic(start_coords, dest_coords, depart_at=None):
    travel_time_sec = get_travel_time_from_coords(start_coords, dest_coords, depart_at=depart_at)
    if travel_time_sec is not None:
        print(f"Estimated travel time (with traffic): {travel_time_sec/60:.1f} minutes")
    else:
        print("Could not fetch travel time from TomTom API.")

# --- Traffic Delay Functions ---
def get_traffic_delay_percent(start_coords, dest_coords, depart_at=None):
    """
    Returns the percentage traffic delay for a route using TomTom API.
    """
    summary = fetch_route_summary(
        start_coords[0], start_coords[1], dest_coords[0], dest_coords[1], depart_at=depart_at
    )
    if not summary:
        return 0.0
    try:
        time_with_traffic_sec = summary.get("travelTimeInSeconds")
        time_no_traffic_sec = summary.get("noTrafficTravelTimeInSeconds")
        if time_with_traffic_sec and time_no_traffic_sec and time_no_traffic_sec > 0:
            delay_pct = ((time_with_traffic_sec - time_no_traffic_sec) / time_no_traffic_sec) * 100
            return max(delay_pct, 0.0)
        else:
            return 0.0
    except Exception:
        return 0.0

def analyze_traffic(start_coords, dest_coords, distance_km, depart_at=None):
    """
    Prints both ideal (no traffic) and traffic-adjusted times from TomTom API for a given route.
    """
    summary = fetch_route_summary(
        start_coords[0], start_coords[1], dest_coords[0], dest_coords[1], depart_at=depart_at
    )
    if not summary:
        print("No routes returned from TomTom API.")
        return
    try:
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
    except Exception as e:
        print(f"Unexpected error during traffic analysis: {e}")
