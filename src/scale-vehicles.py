import pandas as pd
from pathlib import Path

# Paths to files
TRIP_ENERGY_FILE = Path("data/raw/trip_energy.csv")  # JAC trip-level output
CAR_DB_FILE = Path("data/raw/car-energy-database.csv")  # Car energy consumption CSV
OUTPUT_FILE = Path("data/raw/scaled_trip_energy.csv")  # Scaled output

# Mass info for JAC models
JAC_MASS = {
    "JAC iEV7s": 1300,  # kg
    "JAC iEV40": 1690  # kg
}

def main():
    # Ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load JAC trip data
    trip_df = pd.read_csv(TRIP_ENERGY_FILE)

    # Load car energy consumption database
    car_df = pd.read_csv(CAR_DB_FILE)
    car_df.rename(columns=lambda x: x.strip(), inplace=True)  # Remove extra spaces

    # Get JAC iEV7s energy consumption
    jac_consumption_row = car_df[car_df["Car Model"] == "JAC iEV7s"]
    if jac_consumption_row.empty:
        raise ValueError("JAC iEV7s not found in car database.")
    jac_wh_per_km = float(jac_consumption_row["Energy Consumption (Wh/KM)"])

    scaled_data = []

    for _, car_row in car_df.iterrows():
        model_name = car_row["Car Model"]
        car_wh_per_km = float(car_row["Energy Consumption (Wh/KM)"])
        scaling_factor = car_wh_per_km / jac_wh_per_km

        # If scaling to JAC iEV40, apply mass adjustment
        if model_name == "JAC iEV40":
            mass_ratio = JAC_MASS["JAC iEV40"] / JAC_MASS["JAC iEV7s"]
            scaling_factor *= mass_ratio

        for _, trip_row in trip_df.iterrows():
            scaled_energy = trip_row["trip_energy_Wh"] * scaling_factor
            scaled_data.append({
                "COND": trip_row["COND"],
                "Car Model": model_name,
                "trip_energy_Wh": scaled_energy,
                "trip_rows": trip_row["trip_rows"],
                "trip_distance_km": trip_row["trip_distance_km"]
            })

    # Convert to DataFrame and save
    final_df = pd.DataFrame(scaled_data)
    final_df.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved scaled energy estimates to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
