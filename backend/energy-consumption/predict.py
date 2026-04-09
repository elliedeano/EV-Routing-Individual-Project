import pandas as pd
from load_data import load_kaggle_dataset
from train_model import training_lightgbm
from pathlib import Path

#Function that predicts energy consumption and groups into journey summaries.
def predict_energy_consumption(df, model, features):
    df["predicted_energy_Wh"] = model.predict(df[features])
    df["predicted_energy_Wh"] = df["predicted_energy_Wh"].clip(lower=0)

#Aggregate by journey.
    journey_energy = (df.groupby("COND").agg(trip_energy_Wh=("predicted_energy_Wh", "sum"),trip_rows=("id", "count"),trip_distance_km=("ODO", lambda x: x.iloc[-1] - x.iloc[0]),).reset_index())
    journey_energy = journey_energy[journey_energy["trip_distance_km"] >= 0.05]
    journey_energy["wh_per_km_raw"] = (journey_energy["trip_energy_Wh"] / journey_energy["trip_distance_km"])
    output_directory = Path(__file__).parent / "output_files"
    output_directory.mkdir(exist_ok=True)
    journey_energy.to_csv(output_directory / "journey_energy.csv", index=False)
    return journey_energy

def main():
    df = load_kaggle_dataset()
    model, features = training_lightgbm(df)
    predict_energy_consumption(df, model, features)

if __name__ == "__main__":
    main()

