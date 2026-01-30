import pandas as pd
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parents[2]

    TRIP_ENERGY_FILE = project_root / "data" / "raw" / "trip_energy.csv"
    CAR_DB_FILE = project_root / "data" / "raw" / "car-energy-database.csv"
    SCALED_TRIPS_FILE = project_root / "data" / "raw" / "scaled_trip_energy.csv"
    CAR_STATS_FILE = project_root / "data" / "raw" / "car_wh_per_km.csv"

    JAC_MASS = {"JAC iEV7s": 1300, "JAC iEV40": 1690}

    SCALED_TRIPS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Force consistent column names so the rest of the script is stable
    car_df = pd.read_csv(
        CAR_DB_FILE,
        usecols=[0, 1],  # adjust if needed
        names=["Car Model", "Energy Consumption (Wh/KM)"],
        header=0,
    )

    trip_df = pd.read_csv(TRIP_ENERGY_FILE)

    # baseline JAC iEV7s Wh/km from spec
    jac_row = car_df[car_df["Car Model"] == "JAC iEV7s"]
    jac_wh_per_km = float(jac_row["Energy Consumption (Wh/KM)"].iloc[0])

    scaled_data = []

    for _, car_row in car_df.iterrows():
        model_name = car_row["Car Model"]
        car_wh_per_km_spec = float(car_row["Energy Consumption (Wh/KM)"])
        scaling_factor = car_wh_per_km_spec / jac_wh_per_km

        if model_name == "JAC iEV40":
            scaling_factor *= (JAC_MASS["JAC iEV40"] / JAC_MASS["JAC iEV7s"])

        for _, trip_row in trip_df.iterrows():
            base_energy_Wh = trip_row["trip_energy_Wh"]
            dist_km = trip_row["trip_distance_km"]

            trip_energy_Wh = base_energy_Wh * scaling_factor
            wh_per_km_raw = trip_energy_Wh / dist_km if dist_km != 0 else None

            scaled_data.append(
                {
                    "COND": trip_row["COND"],
                    "Car Model": model_name,
                    "trip_energy_Wh": trip_energy_Wh,
                    "trip_rows": trip_row["trip_rows"],
                    "trip_distance_km": dist_km,
                    "wh_per_km_raw": wh_per_km_raw,
                }
            )

    scaled_trips = pd.DataFrame(scaled_data)
    scaled_trips.to_csv(SCALED_TRIPS_FILE, index=False)

    car_stats = (
        scaled_trips.groupby("Car Model")
        .agg(
            wh_per_km_avg=("wh_per_km_raw", "mean"),
            wh_per_km_std=("wh_per_km_raw", "std"),
        )
        .reset_index()
    )
    car_stats.to_csv(CAR_STATS_FILE, index=False)


if __name__ == "__main__":
    main()
