import pandas as pd
import numpy as np
from pathlib import Path

average_row_smoothing = 5

# This is a function that loads and processes the Kaggle dataset from the original csv file.
def load_kaggle_dataset(filename="Kaggle-EV-Dataset.csv"):
    root = Path(__file__).resolve().parents[2]
    file_path = root / "data" / "raw" / filename
    df = pd.read_csv(file_path)

    df["total_seconds"] = df["H"] * 3600 + df["MIN"] * 60 + df["SEC"]

#sorted data by driving condition and time so data is in time order.
    sorted_columns = ["COND"]
    for columns in ("Y", "M", "D"):
        if columns in df.columns:
            sorted_columns.append(columns)
    sorted_columns.append("total_seconds")
    df = df.sort_values(sorted_columns).reset_index(drop=True)
    df["time_difference"] = df.groupby("COND")["total_seconds"].diff().fillna(0)
    df["time_difference"] = df["time_difference"].clip(lower=0)
    df["acceleration_magnitude"] = np.sqrt(df["AX"]**2 + df["AY"]**2 + df["AZ"]**2)
    df["gyroscope_magnitude"] = np.sqrt(df["GX"]**2 + df["GY"]**2 + df["GZ"]**2)
    df["altitude_change"] = df.groupby("COND")["ALT"].diff().fillna(0)
    df["odometer_change"] = df.groupby("COND")["ODO"].diff().fillna(0)
    df["road_gradient"] = np.where(df["odometer_change"] > 0,df["altitude_change"] / df["odometer_change"],0,)
    df["power"] = df["VOL"] * df["CUR"]
    df["energy_Wh"] = df["power"] * df["time_difference"] / 3600
    df["acceleration_magnitude_roll"] = (df.groupby("COND")["acceleration_magnitude"].rolling(average_row_smoothing, min_periods=1).mean().reset_index(0, drop=True) )
    df["speed_roll"] = (df.groupby("COND")["SPD"].rolling(average_row_smoothing, min_periods=1).mean().reset_index(0, drop=True) )

    df = df[(df["VOL"] >= 100) & (df["CUR"] > 0) & (df["SPD"] > 1) & (df["time_difference"] > 0)]
#function then returns the cleaned and feature-engineered dataframe ready to be trained. 
    return df
