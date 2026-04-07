import sys
from pathlib import Path
import math
from datetime import datetime
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.routing.services.route_planner import _safe_float
from backend.routing import range_estimator
from backend.routing import traffic_calculations
from backend.routing.food_places_identifier import is_meal_time, _interval_overlaps_window
from backend.routing import vehicle_specs_loader

def test_float_value_conversion():
    assert _safe_float("3.9") == 3.9
    assert _safe_float(None, default=6.8) == 6.8
    assert _safe_float("string given", default=6.8) == 6.8
    assert _safe_float(-8) == 0.0
    assert _safe_float(float("inf"), default=9.8) == 9.8
    assert _safe_float(float("nan"), default=9.8) == 9.8


def test_meal_time_window():
    dt = datetime(2026, 2, 19, 12, 30)
    assert is_meal_time(dt, window_type="lunch") is True
    dt2 = datetime(2026, 2, 19, 11, 0)
    assert is_meal_time(dt2, window_type="lunch") is False
    start = datetime(2026, 2, 19, 6, 50)
    end = datetime(2026, 2, 19, 9, 10)
    assert _interval_overlaps_window(start, end, "breakfast") is True


def test_car_spec_extraction(monkeypatch):
    df = pd.DataFrame([
        {"Car Model": "CarTest", "battery_kwh": 65.0, "wh_per_km_raw": 150},
        
    ])
    monkeypatch.setattr(pd, "read_csv", lambda path: df)
    specs = vehicle_specs_loader.get_car_specs("CarTest")
    assert specs["battery_kwh"] == 65.0
    assert specs["wh_per_km"] == 150


def test_ev__range_estimation(monkeypatch):
    def mock_car_specs(model):
        return {"battery_kwh": 60, "wh_per_km": 200}
    monkeypatch.setattr(range_estimator, "get_car_specs", mock_car_specs)
    out = range_estimator.load_and_estimate_range("AnyCar", 50)
    assert out is not None
    assert out["car_model"] == "AnyCar"
    assert out["usable_battery_wh"] == 60 * 1000 * 0.5
    assert math.isclose(out["est_range_km"], 150.0, rel_tol=1e-6)


def test_traffic_filter(monkeypatch):
    def normal_traffic_case(a, b, c, d, depart_at=None):
        return {"travelTimeInSeconds": 1200, "noTrafficTravelTimeInSeconds": 1000}
    monkeypatch.setattr(traffic_calculations, "fetch_route_summary", normal_traffic_case)
    pct = traffic_calculations.get_traffic_delay_percent((0, 0), (1, 1))
    assert math.isclose(pct, 20.0, rel_tol=1e-6)
    def none_returned(a, b, c, d, depart_at=None):
        return None
    monkeypatch.setattr(traffic_calculations, "fetch_route_summary", none_returned)
    assert traffic_calculations.get_traffic_delay_percent((0, 0), (1, 1)) == 0.0
    
