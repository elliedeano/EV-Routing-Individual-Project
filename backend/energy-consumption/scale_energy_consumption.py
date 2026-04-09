import pandas as pd
from pathlib import Path

def scale_for_vehicle_specs(trip_df):
    project_root = Path(__file__).resolve().parents[2]
    car_model_info = pd.read_csv(project_root / "data" / "raw" / "car-energy-database-30.csv",usecols=[0, 1],names=["Car Model", "Energy Consumption (Wh/KM)"],header=0,)

    # Get baseline values for JAC iEV7s
    jac_baseline_value = car_model_info.loc[car_model_info["Car Model"] == "JAC iEV7s","Energy Consumption (Wh/KM)"].iloc[0]

    # Create scaling factor column so that other vehicles can be scaled
    car_model_info["scale"] = car_model_info["Energy Consumption (Wh/KM)"] / jac_baseline_value

    #Apply scaling to all other car models.
    trip_df["key"] = 1
    car_model_info["key"] = 1
    merge_for_all_cars = trip_df.merge(car_model_info, on="key").drop("key", axis=1)
    merge_for_all_cars["wh_per_km_raw"] = merge_for_all_cars["wh_per_km_raw"] * merge_for_all_cars["scale"]
    scaled_df = merge_for_all_cars[["COND", "Car Model", "wh_per_km_raw"]]

    # Save the outputs to a csv file for the routing module to use.
    output_directory = Path(__file__).parent / "output_files"
    output_directory.mkdir(exist_ok=True)
    scaled_df.to_csv(output_directory / "scaled_trip_energy.csv", index=False)

    return scaled_df

if __name__ == "__main__":
    output_directory = Path(__file__).parent / "output_files"
    journey_energy_path = output_directory / "trip_energy.csv"
    trip_df = pd.read_csv(journey_energy_path)
    scaled_df = scale_for_vehicle_specs(trip_df)
   