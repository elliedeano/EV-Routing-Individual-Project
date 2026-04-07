import pytest
import httpx
import os
import time

API_BASE = os.getenv("API_BASE", "http://localhost:8000/api/v1")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")  

headers_auth = {"Authorization": f"Bearer {AUTH_TOKEN}"}
headers_json = {"Content-Type": "application/json"}
headers = {**headers_auth, **headers_json}

def test_1_auth_endpoint():
    payload = {
        "start_postcode": "SW1A 0AA",
        "end_postcode": "SP4 7DE",
        "soc": 56,
        "car_model": "BMW i4 eDrive40",
        "umbrella_choice": "distance",
        "priorities": ["distance_stop", "max_power", "is_fast"],
        "journey_start": "12:46"
    }
    r = httpx.post(f"{API_BASE}/route", json=payload, headers=headers)
    assert r.status_code == 200
    assert "chargers" in r.json()
    assert "total_km" in r.json()
    assert "est_range_km" in r.json()

def test_2_auth_endpoint_invalid():
    payload = {
        "start_postcode": "SW1A 0AA",
        "end_postcode": "SP4 7DE",
        "soc": 56,
        "car_model": "BMW i4 eDrive40",
        "umbrella_choice": "distance",
        "priorities": ["distance_stop", "max_power", "is_fast"],
        "journey_start": "12:46"
    }
    r = httpx.post(f"{API_BASE}/route", json=payload, headers=headers_json)  
    assert r.status_code == 401

def test_3_meal_mode_happy_path():
    payload = {
        "start_postcode": "SW1A 0AA",
        "end_postcode": "SP4 7DE",
        "soc": 80,
        "car_model": "BMW i4 eDrive40",
        "umbrella_choice": "meal",
        "priorities": ["meal_stop", "max_power"],
        "journey_start": "12:46"
    }
    r = httpx.post(f"{API_BASE}/route", json=payload, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "chargers" in data
    assert isinstance(data["chargers"], list)
    assert len(data["chargers"]) >= 0

def test_4_meal_mode_sad_path():
    payload = {
        "start_postcode": "SW1A 0AA",
        "end_postcode": "SP4 7DE",
        "soc": 10,  
        "car_model": "BMW i4 eDrive40",
        "umbrella_choice": "meal",
        "priorities": ["meal_stop", "max_power"],
        "journey_start": "12:46"
    }
    r = httpx.post(f"{API_BASE}/route", json=payload, headers=headers, timeout=6000)
    assert r.status_code == 200
    data = r.json()
    assert "chargers" in data
    assert isinstance(data["chargers"], list)
    assert len(data["chargers"]) >= 0


def test_5_distance_mode_happy_path():
    payload = {
        "start_postcode": "SW1A 0AA",
        "end_postcode": "SP4 7DE",
        "soc": 56,
        "car_model": "BMW i4 eDrive40",
        "umbrella_choice": "distance",
        "priorities": ["distance_stop", "max_power"],
        "journey_start": "12:46"
    }
    r = httpx.post(f"{API_BASE}/route", json=payload, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "chargers" in data
    assert isinstance(data["chargers"], list)
    assert "total_km" in data
    assert "est_range_km" in data


def test_6_distance_mode_high_charge():
    payload = {
        "start_postcode": "SW1A 0AA",
        "end_postcode": "SP4 7DE",  
        "soc": 100,
        "car_model": "BMW i4 eDrive40",
        "umbrella_choice": "distance",
        "priorities": ["distance_stop", "max_power"],
        "journey_start": "12:46"
    }
    r = httpx.post(f"{API_BASE}/route", json=payload, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "chargers" in data
    assert isinstance(data["chargers"], list)
    assert len(data["chargers"]) == 0

def test_7_user_filters():
    priorities_to_test = [
        ("price_per_kwh", "Lowest Price per kWh"),
        ("max_power", "Highest Charging Power (kW)"),
        ("is_fast", "Fast Charge Capable"),
        ("num_points", "Most Charging Points"),
        ("traffic_delay", "Least Traffic Delay (% Increase)")
    ]
    for key, label in priorities_to_test:
        payload = {
            "start_postcode": "SW1A 0AA",
            "end_postcode": "SP4 7DE",
            "soc": 56,
            "car_model": "BMW i4 eDrive40",
            "umbrella_choice": "distance",
            "priorities": [key, "max_power"],
            "journey_start": "12:46"
        }
        r = httpx.post(f"{API_BASE}/route", json=payload, headers=headers)
        assert r.status_code == 200, f"Failed for priority: {label}"
        data = r.json()
        assert "chargers" in data
        assert isinstance(data["chargers"], list)


def test_8_missing_input_entry():
    invalid_cases = [
        {"desc": "Empty start postcode", "payload": {"start_postcode": "", "end_postcode": "SP4 7DE", "soc": 56, "car_model": "BMW i4 eDrive40", "umbrella_choice": "distance", "priorities": ["distance_stop", "max_power"], "journey_start": "12:46"}},
        {"desc": "Empty destination postcode", "payload": {"start_postcode": "SW1A 0AA", "end_postcode": "", "soc": 56, "car_model": "BMW i4 eDrive40", "umbrella_choice": "distance", "priorities": ["distance_stop", "max_power"], "journey_start": "12:46"}},
        {"desc": "Empty time of day", "payload": {"start_postcode": "SW1A 0AA", "end_postcode": "SP4 7DE", "soc": 56, "car_model": "BMW i4 eDrive40", "umbrella_choice": "distance", "priorities": ["distance_stop", "max_power"], "journey_start": ""}},
        {"desc": "Empty vehicle model", "payload": {"start_postcode": "SW1A 0AA", "end_postcode": "SP4 7DE", "soc": 56, "car_model": "", "umbrella_choice": "distance", "priorities": ["distance_stop", "max_power"], "journey_start": "12:46"}},
        {"desc": "Empty soc", "payload": {"start_postcode": "SW1A 0AA", "end_postcode": "SP4 7DE", "car_model": "BMW i4 eDrive40", "umbrella_choice": "distance", "priorities": ["distance_stop", "max_power"], "journey_start": "12:46"}},
        {"desc": " < 2 priorities selected", "payload": {"start_postcode": "SW1A 0AA", "end_postcode": "SP4 7DE", "soc": 56, "car_model": "BMW i4 eDrive40", "umbrella_choice": "distance", "priorities": ["distance_stop"], "journey_start": "12:46"}},
    ]
    for case in invalid_cases:
        r = httpx.post(f"{API_BASE}/route", json=case["payload"], headers=headers)
        assert r.status_code in (400, 422), f"Failed for case: {case['desc']}"

def test_9_api_timeout():
    bad_base = "http://10.255.255.1:9999/api/v1"
    payload = {
        "start_postcode": "SW1A 0AA",
        "end_postcode": "SP4 7DE",
        "soc": 56,
        "car_model": "BMW i4 eDrive40",
        "umbrella_choice": "distance",
        "priorities": ["distance_stop", "max_power"],
        "journey_start": "12:46"
    }
    try:
        httpx.post(f"{bad_base}/route", json=payload, headers=headers, timeout=2)
        assert False, "timeout error"
    except httpx.RequestError:
        assert True



def test_10_application_response_time():
    payload = {
        "start_postcode": "SW1A 0AA",
        "end_postcode": "SP4 7DE",
        "soc": 56,
        "car_model": "BMW i4 eDrive40",
        "umbrella_choice": "distance",
        "priorities": ["distance_stop", "max_power"],
        "journey_start": "12:46"
    }
    start = time.time()
    r = httpx.post(f"{API_BASE}/route", json=payload, headers=headers)
    elapsed = time.time() - start
    assert r.status_code == 200
    assert elapsed < 5 
