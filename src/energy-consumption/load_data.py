import pandas as pd
from pathlib import Path
import numpy as np


def load_ev_data(filename="Kaggle-EV-Dataset.csv"):
   
    project_root = Path(__file__).resolve().parents[2]  
    file_path = project_root / "data" / "raw" / filename

    df = pd.read_csv(file_path)

    df["acc_mag"] = np.sqrt(df["AX"] ** 2 + df["AY"] ** 2 + df["AZ"] ** 2)
    df["gyro_mag"] = np.sqrt(df["GX"] ** 2 + df["GY"] ** 2 + df["GZ"] ** 2)
    df["delta_alt"] = df.groupby("COND")["ALT"].diff().fillna(0)
    df["delta_odo"] = df.groupby("COND")["ODO"].diff().fillna(0.001)  
    df["road_grad"] = df["delta_alt"] / df["delta_odo"]
    # Assume CUR is in deci-amps (dA), so convert to amps
    df["CUR"] = df["CUR"] * 10
    df["power"] = df["VOL"] * df["CUR"]

    rolling_window = 5
    df["acc_mag_roll"] = (
        df.groupby("COND")["acc_mag"]
        .rolling(window=rolling_window, min_periods=1)
        .mean()
        .reset_index(0, drop=True)
    )
    df["spd_roll"] = (
        df.groupby("COND")["SPD"]
        .rolling(window=rolling_window, min_periods=1)
        .mean()
        .reset_index(0, drop=True)
    )

    df = df.drop(columns=["delta_alt", "delta_odo"])

    features_to_keep = [
        "id", "COND", "LAT", "LON", "ALT", "AX", "AY", "AZ",
        "GX", "GY", "GZ", "CH", "VOL", "CUR", "SPD", "ODO",
        "BRK", "ACC", "AUT", "ECO", "AIR",
        "acc_mag", "gyro_mag", "road_grad", "power",
        "acc_mag_roll", "spd_roll",
    ]

    df = df[features_to_keep]
    # Filter out rows where SPD <= 1 or CUR == 0
    df = df[(df["SPD"] > 1) & (df["CUR"] != 0)]
    return df
