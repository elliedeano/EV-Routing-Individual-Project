"""
fetch_traffic_data.py

This module provides a function to fetch traffic/time data for a given route segment using the TomTom Traffic API.
Replace the API key with your own if needed.
"""

import requests

def fetch_travel_time(lat1, lon1, lat2, lon2, api_key="AlmtymL0xYZG08ULKfWbjWOg6PzcZtEd"):
    """
    Fetches travel time (in seconds) for a route segment from TomTom Traffic API.
    Args:
        lat1, lon1: Start coordinates
        lat2, lon2: End coordinates
        api_key: TomTom API key
    Returns:
        travel_time_sec: Estimated travel time in seconds (or None if error)
    """
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{lat1},{lon1}:{lat2},{lon2}/json"
    params = {
        "key": api_key,
        "traffic": "true",
        "travelMode": "car"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        # TomTom returns travel time in seconds in 'summary' field
        travel_time_sec = data['routes'][0]['summary']['travelTimeInSeconds']
        return travel_time_sec
    except Exception as e:
        print(f"Error fetching travel time: {e}")
        return None
