import pandas as pd
import numpy as np
from pathlib import Path
import lightgbm as lgb
from sklearn.model_selection import train_test_split
import joblib
from datetime import datetime
import json

# -------------------------
# CONFIG
# -------------------------
ROLLING_WINDOW = 5
JAC_MASS = {"JAC iEV7s": 1300, "JAC iEV40": 1690}


# -------------------------
# LOAD + CLEAN DATA
# -------------------------
def load_ev_data(filename="Kaggle-EV-Dataset.csv"):

    project_root = Path(__file__).resolve().parents[2]
    file_path = project_root / "data" / "raw" / filename
    df = pd.read_csv(file_path)

    # Time
    df["t_sec"] = df["H"] * 3600 + df["MIN"] * 60 + df["SEC"]
    df["dt"] = df.groupby("COND")["t_sec"].diff().fillna(0)
    df["dt"] = df["dt"].clip(lower=0, upper=5)  # loosened from 2 → 5s

    print("\n=== TIMESTEP CHECK ===")
    print(df["dt"].describe())

    # Motion
    df["acc_mag"] = np.sqrt(df["AX"]**2 + df["AY"]**2 + df["AZ"]**2)
    df["gyro_mag"] = np.sqrt(df["GX"]**2 + df["GY"]**2 + df["GZ"]**2)

    df["delta_alt"] = df.groupby("COND")["ALT"].diff().fillna(0)
    df["delta_odo"] = df.groupby("COND")["ODO"].diff().fillna(0)

    df["road_grad"] = np.where(
        df["delta_odo"] > 0,
        df["delta_alt"] / df["delta_odo"],
        0,
    )

    # Energy (physics-correct)
    df["power"] = df["VOL"] * df["CUR"]
    df["energy_Wh"] = df["power"] * df["dt"] / 3600

    # Rolling features
    df["acc_mag_roll"] = (
        df.groupby("COND")["acc_mag"]
        .rolling(ROLLING_WINDOW, min_periods=1)
        .mean()
        .reset_index(0, drop=True)
    )
    df["spd_roll"] = (
        df.groupby("COND")["SPD"]
        .rolling(ROLLING_WINDOW, min_periods=1)
        .mean()
        .reset_index(0, drop=True)
    )

    # Clean
    df = df[
        (df["VOL"] >= 100) &
        (df["CUR"] > 0) &
        (df["SPD"] > 1) &
        (df["dt"] > 0)
    ]

    print(f"\nLoaded {len(df)} valid rows from raw data")
    return df


# -------------------------
# TRAIN MODEL
# -------------------------
def train_energy_model(df):

    target = "energy_Wh"
    drop_cols = ["id", "COND", "H", "MIN", "SEC", "power"]
    features = df.columns.difference(drop_cols + [target])

    X = df[features]
    y = df[target]

    print("\n=== TRAINING DATA CHECK ===")
    print("Energy per row (Wh):", y.describe())

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = lgb.LGBMRegressor(
        objective="regression",
        learning_rate=0.05,
        num_leaves=31,
        n_estimators=800,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )

    model.fit(X_train, y_train)

    # Save model
    joblib.dump(model, "lgbm_ev_energy_model.pkl")
    print("Saved energy model: lgbm_ev_energy_model.pkl")

    return model, features


# -------------------------
# PREDICT TRIP ENERGY
# -------------------------
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


# -------------------------
# SCALE TO OTHER CARS
# -------------------------
def scale_to_other_cars(trip_df):

    project_root = Path(__file__).resolve().parents[2]
    car_df = pd.read_csv(
        project_root / "data" / "raw" / "car-energy-database.csv",
        usecols=[0, 1],
        names=["Car Model", "Energy Consumption (Wh/KM)"],
        header=0,
    )

    jac_wh_per_km = float(
        car_df[car_df["Car Model"] == "JAC iEV7s"]
        ["Energy Consumption (Wh/KM)"]
        .iloc[0]
    )

    scaled = []

    for _, car in car_df.iterrows():
        scale = car["Energy Consumption (Wh/KM)"] / jac_wh_per_km

        if car["Car Model"] == "JAC iEV40":
            scale *= JAC_MASS["JAC iEV40"] / JAC_MASS["JAC iEV7s"]

        for _, trip in trip_df.iterrows():
            scaled.append({
                "COND": trip["COND"],
                "Car Model": car["Car Model"],
                "wh_per_km": trip["wh_per_km_raw"] * scale,
            })

    scaled_df = pd.DataFrame(scaled)

    print("\n=== SCALED CAR CHECK ===")
    print(scaled_df.groupby("Car Model")["wh_per_km"].describe())

    return scaled_df


# -------------------------
# MAIN
# -------------------------
def main():

    df = load_ev_data()
    model, features = train_energy_model(df)
    trip_df = predict_trip_energy(df, model, features)
    scaled_df = scale_to_other_cars(trip_df)

    print("\n✅ PIPELINE COMPLETE — CHECK RANGES ABOVE")


if __name__ == "__main__":
    main()
