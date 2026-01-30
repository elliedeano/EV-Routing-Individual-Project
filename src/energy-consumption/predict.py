import json
import pandas as pd
from pathlib import Path
from load_data import load_ev_data
import joblib

MODEL_META = Path("model_metadata.json")
MODEL_PKL = Path("lgbm_ev_model.pkl")

def main():
    
    model = joblib.load(MODEL_PKL)
    meta = json.loads(MODEL_META.read_text())
    feature_names = meta["features"]
    df = load_ev_data()
    X = df[feature_names]


    df["predicted_power_W"] = model.predict(X)
    print("Predicted power (W) stats:")
    print("Min:", df['predicted_power_W'].min(), "Max:", df['predicted_power_W'].max(), "Mean:", df['predicted_power_W'].mean())
    # Assume 1 second between samples if no time columns
    df["delta_time"] = 1
    df["energy_Wh"] = df["predicted_power_W"] * df["delta_time"] / 3600
    
    trip_energy = (
      df.groupby("COND").agg(
        trip_energy_Wh=("energy_Wh", "sum"),
        trip_rows=("id", "count"),
        trip_distance_km=("ODO", lambda x: x.max() - x.min())  
    )
    .reset_index()
)

    trip_energy.to_csv("trip_energy.csv", index=False)
    print("Saved trip-level energy estimates with distance")


if __name__ == "__main__":
    main()

