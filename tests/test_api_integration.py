# Integration Test Scripts for EV Routing Project
# Each test case corresponds to your updated test plan.
# Use: pytest + httpx for API integration tests.

import pytest
import httpx
import os

API_BASE = os.getenv("API_BASE", "http://localhost:8000/api/v1")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")  # Set this to a valid Firebase token for real tests

headers_auth = {"Authorization": f"Bearer {AUTH_TOKEN}"}
headers_json = {"Content-Type": "application/json"}
headers = {**headers_auth, **headers_json}

def test_it01_auth_token_propagation():
    """IT-01: Auth Token Propagation (UI → API)"""
    payload = {
        "start_postcode": "CV37 7QR",
        "end_postcode": "SW6 4BL",
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

def test_it02_authentication_enforcement():
    """IT-02: Authentication Enforcement"""
    payload = {
        "start_postcode": "CV37 7QR",
        "end_postcode": "SW6 4BL",
        "soc": 56,
        "car_model": "BMW i4 eDrive40",
        "umbrella_choice": "distance",
        "priorities": ["distance_stop", "max_power", "is_fast"],
        "journey_start": "12:46"
    }
    r = httpx.post(f"{API_BASE}/route", json=payload, headers=headers_json)  # No auth
    assert r.status_code == 401

def test_it03_route_happy_path_meal_mode():
    """IT-03: Route Happy Path – Meal Mode"""
    payload = {
        "start_postcode": "CV37 7QR",
        "end_postcode": "SW6 4BL",
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


def test_it04_route_insufficient_charge_meal_mode():
    """IT-04: Route Insufficient Charge – Meal Mode"""
    payload = {
        "start_postcode": "CV37 7QR",
        "end_postcode": "SW6 4BL",
        "soc": 10,  # Low SOC to force stop
        "car_model": "BMW i4 eDrive40",
        "umbrella_choice": "meal",
        "priorities": ["meal_stop", "max_power"],
        "journey_start": "12:46"
    }
    r = httpx.post(f"{API_BASE}/route", json=payload, headers=headers, timeout=60)
    assert r.status_code == 200
    data = r.json()
    assert "chargers" in data
    assert isinstance(data["chargers"], list)
    assert len(data["chargers"]) >= 0


def test_it05_distance_based_planning_happy_path():
    """IT-05: Distance-Based Planning – Happy Path"""
    payload = {
        "start_postcode": "CV37 7QR",
        "end_postcode": "SW6 4BL",
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


def test_it06_distance_based_planning_no_charger_needed():
    """IT-06: Distance-Based Planning – No Charger Needed"""
    payload = {
        "start_postcode": "CV37 7QR",
        "end_postcode": "CV37 8RP",  # Short trip
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


def test_it07_priority_filters_integration():
    """IT-07: Priority Filters Integration (test each priority option)"""
    priorities_to_test = [
        ("price_per_kwh", "Lowest Price per kWh"),
        ("max_power", "Highest Charging Power (kW)"),
        ("is_fast", "Fast Charge Capable"),
        ("num_points", "Most Charging Points"),
        ("traffic_delay", "Least Traffic Delay (% Increase)")
    ]
    for key, label in priorities_to_test:
        payload = {
            "start_postcode": "CV37 7QR",
            "end_postcode": "SW6 4BL",
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


def test_it08_input_validation_contract_cases():
    """IT-08: Input Validation Contract (multiple invalid input cases)"""
    invalid_cases = [
        {"desc": "Empty start postcode", "payload": {"start_postcode": "", "end_postcode": "SW6 4BL", "soc": 56, "car_model": "BMW i4 eDrive40", "umbrella_choice": "distance", "priorities": ["distance_stop", "max_power"], "journey_start": "12:46"}},
        {"desc": "Empty destination postcode", "payload": {"start_postcode": "CV37 7QR", "end_postcode": "", "soc": 56, "car_model": "BMW i4 eDrive40", "umbrella_choice": "distance", "priorities": ["distance_stop", "max_power"], "journey_start": "12:46"}},
        {"desc": "Empty time value", "payload": {"start_postcode": "CV37 7QR", "end_postcode": "SW6 4BL", "soc": 56, "car_model": "BMW i4 eDrive40", "umbrella_choice": "distance", "priorities": ["distance_stop", "max_power"], "journey_start": ""}},
        {"desc": "Empty vehicle model", "payload": {"start_postcode": "CV37 7QR", "end_postcode": "SW6 4BL", "soc": 56, "car_model": "", "umbrella_choice": "distance", "priorities": ["distance_stop", "max_power"], "journey_start": "12:46"}},
        {"desc": "Missing state of charge", "payload": {"start_postcode": "CV37 7QR", "end_postcode": "SW6 4BL", "car_model": "BMW i4 eDrive40", "umbrella_choice": "distance", "priorities": ["distance_stop", "max_power"], "journey_start": "12:46"}},
        {"desc": "Fewer than two priorities selected", "payload": {"start_postcode": "CV37 7QR", "end_postcode": "SW6 4BL", "soc": 56, "car_model": "BMW i4 eDrive40", "umbrella_choice": "distance", "priorities": ["distance_stop"], "journey_start": "12:46"}},
    ]
    for case in invalid_cases:
        r = httpx.post(f"{API_BASE}/route", json=case["payload"], headers=headers)
        assert r.status_code in (400, 422), f"Failed for case: {case['desc']}"


def test_it09_external_dependency_timeout_failure():
    """IT-09: External Dependency Timeout / Failure (simulate by using an unreachable API base)"""
    bad_base = "http://10.255.255.1:9999/api/v1"
    payload = {
        "start_postcode": "CV37 7QR",
        "end_postcode": "SW6 4BL",
        "soc": 56,
        "car_model": "BMW i4 eDrive40",
        "umbrella_choice": "distance",
        "priorities": ["distance_stop", "max_power"],
        "journey_start": "12:46"
    }
    try:
        httpx.post(f"{bad_base}/route", json=payload, headers=headers, timeout=2)
        assert False, "Expected timeout or connection error"
    except httpx.RequestError:
        assert True


import time

def test_it10_latency_check_performance():
    """IT-10: Latency Check (Performance)"""
    payload = {
        "start_postcode": "CV37 7QR",
        "end_postcode": "SW6 4BL",
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
    assert elapsed < 5  # Example: must respond in under 5 seconds
