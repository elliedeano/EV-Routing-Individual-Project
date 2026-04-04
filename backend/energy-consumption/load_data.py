import pandas as pd
import numpy as np
from pathlib import Path

ROLLING_WINDOW = 5

def load_ev_data(filename="Kaggle-EV-Dataset.csv"):
    project_root = Path(__file__).resolve().parents[2]
    file_path = project_root / "data" / "raw" / filename
    df = pd.read_csv(file_path)

    df["total_seconds"] = df["H"] * 3600 + df["MIN"] * 60 + df["SEC"]
    sort_cols = ["COND"]
    for c in ("Y", "M", "D"):
        if c in df.columns:
            sort_cols.append(c)
    sort_cols.append("total_seconds")
    df = df.sort_values(sort_cols).reset_index(drop=True)
    df["time_difference"] = df.groupby("COND")["total_seconds"].diff().fillna(0)
    df["time_difference"] = df["time_difference"].clip(lower=0)

    df["acceleration_magnitude"] = np.sqrt(df["AX"]**2 + df["AY"]**2 + df["AZ"]**2)
    df["gyroscope_magnitude"] = np.sqrt(df["GX"]**2 + df["GY"]**2 + df["GZ"]**2)

    df["altitude_change"] = df.groupby("COND")["ALT"].diff().fillna(0)
    df["odometer_change"] = df.groupby("COND")["ODO"].diff().fillna(0)

    df["road_gradient"] = np.where(
        df["odometer_change"] > 0,
        df["altitude_change"] / df["odometer_change"],
        0,
    )

    df["power"] = df["VOL"] * df["CUR"]


    df["energy_Wh"] = df["power"] * df["time_difference"] / 3600
    

    df["acceleration_magnitude_roll"] = (
        df.groupby("COND")["acceleration_magnitude"]
        .rolling(ROLLING_WINDOW, min_periods=1)
        .mean()
        .reset_index(0, drop=True)
    )
    df["speed_roll"] = (
        df.groupby("COND")["SPD"]
        .rolling(ROLLING_WINDOW, min_periods=1)
        .mean()
        .reset_index(0, drop=True)
    )

    df = df[
        (df["VOL"] >= 100) &
        (df["CUR"] > 0) &
        (df["SPD"] > 1) &
        (df["time_difference"] > 0)
    ]
    return df
