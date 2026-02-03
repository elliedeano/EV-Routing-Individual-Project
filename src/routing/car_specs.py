

import pandas as pd
from pathlib import Path

def get_car_specs(car_model):
    project_root = Path(__file__).resolve().parents[2]
    csv_path = project_root / "data" / "raw" / "scaled_trip_energy.csv"
    df = pd.read_csv(csv_path)
   
    row = df[df["Car Model"] == car_model].iloc[0]
    print("Matched row:", row)
    specs = {
        "battery_kwh": row.get("battery_kwh", 42.8),  # fallback to 42.8 if not present
        "wh_per_km": row["wh_per_km_raw"],
    }
    return specs

if __name__ == "__main__":
    car_model = input("Enter your car model: ")
    specs = get_car_specs(car_model)
    print(f"Specs for {car_model}: {specs}")
