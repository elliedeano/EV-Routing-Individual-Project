import math
from datetime import datetime, timedelta
import pandas as pd
from backend.routing.services.route_planner import _safe_float
from backend.routing import range_estimator
from backend.routing import traffic_calculations
from backend.routing.food_places_identifier import is_meal_time, _interval_overlaps_window
from backend.routing import vehicle_specs_loader

def test_all_value_cases():
    assert _safe_float("3.5") == 3.5
    assert _safe_float(None, default=7.7) == 7.7
    assert _safe_float("not-a-number", default=1.2) == 1.2
    assert _safe_float(-5) == 0.0
    assert _safe_float(float("inf"), default=9.9) == 9.9
    assert _safe_float(float("nan"), default=4.4) == 4.4


def test_load_and_estimate_range(monkeypatch):
    def fake_get_car_specs(model):
        return {"battery_kwh": 60, "wh_per_km": 200}
    monkeypatch.setattr(range_estimator, "get_car_specs", fake_get_car_specs)
    out = range_estimator.load_and_estimate_range("AnyCar", 50)
    assert out is not None
    assert out["car_model"] == "AnyCar"
    assert out["usable_battery_wh"] == 60 * 1000 * 0.5
    assert math.isclose(out["est_range_km"], 150.0, rel_tol=1e-6)


def test_traffic_delay_percent_filter(monkeypatch):
    def fake_summary_positive(a, b, c, d, depart_at=None):
        return {"travelTimeInSeconds": 1200, "noTrafficTravelTimeInSeconds": 1000}
    monkeypatch.setattr(traffic_calculations, "fetch_route_summary", fake_summary_positive)
    pct = traffic_calculations.get_traffic_delay_percent((0, 0), (1, 1))
    assert math.isclose(pct, 20.0, rel_tol=1e-6)
    def fake_summary_none(a, b, c, d, depart_at=None):
        return None
    monkeypatch.setattr(traffic_calculations, "fetch_route_summary", fake_summary_none)
    assert traffic_calculations.get_traffic_delay_percent((0, 0), (1, 1)) == 0.0
    def fake_summary_zero(a, b, c, d, depart_at=None):
        return {"travelTimeInSeconds": 1000, "noTrafficTravelTimeInSeconds": 0}
    monkeypatch.setattr(traffic_calculations, "fetch_route_summary", fake_summary_zero)
    assert traffic_calculations.get_traffic_delay_percent((0, 0), (1, 1)) == 0.0


def test_meal_time_window():
    dt = datetime(2026, 3, 17, 12, 30)
    assert is_meal_time(dt, window_type="lunch") is True
    dt2 = datetime(2026, 3, 17, 11, 0)
    assert is_meal_time(dt2, window_type="lunch") is False
    start = datetime(2026, 3, 17, 11, 50)
    end = datetime(2026, 3, 17, 12, 10)
    assert _interval_overlaps_window(start, end, "lunch") is True


def test_get_car_specs(monkeypatch):
    df = pd.DataFrame([
        {"Car Model": "TestCar", "battery_kwh": 55.0, "wh_per_km_raw": 150},
        {"Car Model": "OtherCar", "battery_kwh": 40.0, "wh_per_km_raw": 180},
    ])
    monkeypatch.setattr(pd, "read_csv", lambda path: df)
    specs = vehicle_specs_loader.get_car_specs("TestCar")
    assert specs["battery_kwh"] == 55.0
    assert specs["wh_per_km"] == 150
