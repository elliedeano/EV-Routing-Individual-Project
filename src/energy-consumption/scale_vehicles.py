import pandas as pd
from pathlib import Path

def scale_to_other_cars(trip_df):
    project_root = Path(__file__).resolve().parents[2]
    car_df = pd.read_csv(
        project_root / "data" / "raw" / "car-energy-database.csv",
        usecols=[0, 1, 2],
        names=["Car Model", "Energy Consumption (Wh/KM)", "Mass(kg)"],
        header=0,
    )
    jac_row = car_df[car_df["Car Model"] == "JAC iEV7s"].iloc[0]
    jac_wh_per_km = float(jac_row["Energy Consumption (Wh/KM)"])
    jac_mass = float(jac_row["Mass(kg)"]) if not pd.isna(jac_row["Mass(kg)"]) else None
    scaled = []
    for _, car in car_df.iterrows():
        scale = car["Energy Consumption (Wh/KM)"] / jac_wh_per_km
        if not pd.isna(car["Mass (kg)"]) and jac_mass is not None:
            scale *= float(car["Mass (kg)"]) / jac_mass
        for _, trip in trip_df.iterrows():
            scaled.append({
                "COND": trip["COND"],
                "Car Model": car["Car Model"],
                "wh_per_km": trip["wh_per_km_raw"] * scale,
            })
    scaled_df = pd.DataFrame(scaled)
    scaled_df = scaled_df.rename(columns={"wh_per_km": "wh_per_km_raw"})
    output_dir = Path(__file__).parent / "output_files"
    output_dir.mkdir(exist_ok=True)
    scaled_df.to_csv(
        output_dir / "scaled_trip_energy.csv",
        columns=["COND", "Car Model", "wh_per_km_raw"],
        index=False
    )
    return scaled_df
