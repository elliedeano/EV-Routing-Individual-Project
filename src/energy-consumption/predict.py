import pandas as pd# import json

import pandas as pd

import pandas as pd

def predict_trip_energy(df, model, features):
    df["predicted_energy_Wh"] = model.predict(df[features])
    # Clip negative predictions
    df["predicted_energy_Wh"] = df["predicted_energy_Wh"].clip(lower=0)

    print("\n=== PREDICTION CHECK ===")
    print("Predicted energy per row (Wh):")
    print(df["predicted_energy_Wh"].describe())

    trip_energy = (
        df.groupby("COND")
        .agg(
            trip_energy_Wh=("predicted_energy_Wh", "sum"),
            trip_rows=("id", "count"),
            trip_distance_km=("ODO", lambda x: x.iloc[-1] - x.iloc[0]),
        )
        .reset_index()
    )

    # Loosened: allow trips ≥ 0.05 km (50 meters)
    trip_energy = trip_energy[trip_energy["trip_distance_km"] >= 0.05]

    trip_energy["wh_per_km_raw"] = (
        trip_energy["trip_energy_Wh"] / trip_energy["trip_distance_km"]
    )

    print("\n=== TRIP-LEVEL CHECK ===")
    print(trip_energy["wh_per_km_raw"].describe())
    print("Sample Wh/km:", trip_energy["wh_per_km_raw"].head(10).tolist())

    return trip_energy

    # ... (prediction and trip aggregation logic from run.py)

    return trip_energy# MODEL_META = Path("model_metadata.json")

# MODEL_PKL = Path("lgbm_ev_model.pkl")

# def main():
    
#     model = joblib.load(MODEL_PKL)
#     meta = json.loads(MODEL_META.read_text())
#     feature_names = meta["features"]
#     df = load_ev_data()
#     X = df[feature_names]

#     # If needed, scale VOL and CUR by 0.1 (if values look like deci-units)
#     # Uncomment the next two lines if you confirm scaling is needed:
#     # df["VOL"] = df["VOL"] * 0.1
#     # df["CUR"] = df["CUR"] * 0.1

#     df["predicted_power_W"] = model.predict(X)
#     print("Predicted power (W) stats:")
#     print("Min:", df['predicted_power_W'].min(), "Max:", df['predicted_power_W'].max(), "Mean:", df['predicted_power_W'].mean())

#     # Time integration for energy calculation
#     df["timestamp"] = df["H"].astype(int) * 3600 + df["MIN"].astype(int) * 60 + df["SEC"].astype(int)
#     df["delta_time"] = df.groupby("COND")["timestamp"].diff().fillna(1)
#     df = df[df["delta_time"] > 0]
#     dt_hours = df["delta_time"] / 3600
#     df["energy_Wh"] = df["predicted_power_W"] * dt_hours

#     # Aggregate by trip (COND)
#     trip_energy = (
#       df.groupby("COND").agg(
#         trip_energy_Wh=("energy_Wh", "sum"),
#         trip_rows=("id", "count"),
#         trip_distance_km=("ODO", lambda x: x.max() - x.min())  
#     )
#     .reset_index()
#     )

#     trip_energy.to_csv("trip_energy.csv", index=False)
#     print("Saved trip-level energy estimates with distance")


# if __name__ == "__main__":
#     main()

