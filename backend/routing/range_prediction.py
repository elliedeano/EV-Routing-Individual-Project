import pandas as pd
from pathlib import Path

def get_car_specs(car_model):
    project_root = Path(__file__).resolve().parents[2]
    file_path = project_root / "data" / "raw" / "scaled_trip_energy.csv"
    df = pd.read_csv(file_path)
   
    row = df[df["Car Model"] == car_model].iloc[0]
    print("Matched row:", row)
    car_spec_data = {
        "battery_kwh": row.get("battery_kwh", 42.8),  
        "wh_per_km": row["wh_per_km_raw"],
    }
    return car_spec_data

def range_prediction(car_model, soc_percent):
    try:
        specs = get_car_specs(car_model)
        battery_kwh = specs["battery_kwh"]
        wh_per_km = specs["wh_per_km"]
        soc = soc_percent / 100.0
        usable_battery_wh = battery_kwh * 1000 * soc  
        est_range_km = usable_battery_wh / wh_per_km
        return {
            "car_model": car_model,
            "battery_kwh": battery_kwh,
            "wh_per_km": wh_per_km,
            "usable_battery_wh": usable_battery_wh,
            "est_range_km": est_range_km,
        }
    except Exception as e:
        return None

