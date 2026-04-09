import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error
from load_data import load_kaggle_dataset
import matplotlib.pyplot as plt
import seaborn as sns
import joblib as _joblib


OUTPUT_DIR = Path(__file__).parent / "output_files"
OUTPUT_DIR.mkdir(exist_ok=True)

#Make sure bar chart has full feature names written on axis.
def full_feature_name(name: str) -> str:
    conversion = {
        "ACC": "Acceleration",
        "AX": "Acceleration X",
        "AY": "Acceleration Y",
        "AZ": "Acceleration Z",
        "GX": "Gyroscope X",
        "GY": "Gyroscope Y",
        "GZ": "Gyroscope Z",
        "SPD": "Speed",
        "ODO": "Odometer",
        "ALT": "Altitude",
        "LAT": "Latitude",
        "LON": "Longitude",
        "CH": "Battery charge level",
        "AUT": "Autonomy",
        "AIR": "Air conditioning",
        "ECO": "Eco mode",
        "BRK": "Brake status",
        "Y": "Year",
        "M": "Month",
        "D": "Day",
        "GYROSCOPE_MAGNITUDE": "Gyroscope Magnitude",
        "acceleration_magnitude_roll": "Acceleration Magnitude Roll",
        "speed_roll": "Speed Roll",
        "odometer_change": "Odometer Change",
        "altitude_change": "Altitude Change",
        "total_seconds": "Total Seconds",
    }
    if name in conversion:
        return conversion[name]
    return name.replace("_", " ").title()

#Error evaluation calculations
def rmse_mae_avg_signed_error_calculations(y_true, y_pred):
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    bias = float(np.mean(y_pred - y_true))
    return {"Root Mean Squared Error": rmse, "Mean Absolute Error": mae, "Average Signed Error": bias}


def journey_statistics(journey_csv_path, save_outputs: bool = True):
    journeys = pd.read_csv(Path(journey_csv_path))
    if "trip_energy_Wh" not in journeys.columns or "trip_distance_km" not in journeys.columns:
        raise ValueError("The CSV must contain 'trip_energy_Wh' and 'trip_distance_km'")
    journeys = journeys.copy()
    if "wh_per_km_raw" in journeys.columns:
        journeys["wh_per_km_model"] = journeys["wh_per_km_raw"]
    else:
        journeys["wh_per_km_model"] = journeys["trip_energy_Wh"] / journeys["trip_distance_km"]

    df_raw = load_kaggle_dataset()
    if "total_seconds" in df_raw.columns:
        df_raw = df_raw.sort_values(["COND", "total_seconds"]).reset_index(drop=True)

    trips_physics_derived_estimate = (
        df_raw.groupby("COND")
        .agg(trip_energy_physics=("energy_Wh", "sum"),trip_distance_km=("ODO", lambda x: float(x.iloc[-1] - x.iloc[0])),).reset_index())
    trips_physics_derived_estimate = trips_physics_derived_estimate[trips_physics_derived_estimate["trip_distance_km"] >= 0.05].copy()
    trips_physics_derived_estimate["wh_per_km_physics"] = trips_physics_derived_estimate["trip_energy_physics"] / trips_physics_derived_estimate["trip_distance_km"]

    merge_trip_tables_together = pd.merge(
        trips_physics_derived_estimate,
        journeys[["COND", "trip_energy_Wh", "trip_distance_km", "wh_per_km_model"]]
        .rename(columns={"trip_energy_Wh": "trip_energy_model", "trip_distance_km": "trip_distance_km_model"}),
        on="COND",
        how="inner",
    )
    report = {
        "n_test_trips": int(len(merge_trip_tables_together)),
        "top_feature_importances": [],
        "lightgbm_model_vs_physics_calculations": rmse_mae_avg_signed_error_calculations(merge_trip_tables_together["wh_per_km_physics"].values, merge_trip_tables_together["wh_per_km_model"].values),
    }

   
    model_path = Path(__file__).parent / "output_files" / "model.pkl"
    feats_path = Path(__file__).parent / "output_files" / "model_features.json"
      
    with open(feats_path, "r") as _f:
        feat_list = json.load(_f)
    _model = _joblib.load(model_path)
    feature_importance = getattr(_model, "feature_importances_", None)
    if feature_importance is not None and feat_list is not None and len(feature_importance) == len(feat_list):
        top = sorted(list(zip(feat_list, feature_importance)), key=lambda x: -x[1])
        report["top_feature_importances"] = [{"feature": full_feature_name(f), "importance": int(v)} for f, v in top]
        
#Show ffeature importance bar chart.
    if save_outputs:
        with open(OUTPUT_DIR / "model_evaluation_report.json", "w") as fh:
            json.dump(report, fh, indent=2)

        top_feats = report["top_feature_importances"][:40]
        feat_names = [d["feature"] for d in top_feats]
        feat_vals = [d["importance"] for d in top_feats]
        height = max(3, 0.25 * len(feat_names))
        fig, ax = plt.subplots(figsize=(8, height))
        ax.barh(feat_names[::-1], feat_vals[::-1], color="C0")
        ax.set_xlabel("Importance", fontsize=12)
        ax.set_ylabel("Feature", fontsize=12)
        ax.set_title("Energy Consumption Predictions — Top Feature Importance", fontsize=14)
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "feature_importances.png", dpi=150)
        plt.close()
            

        comparison = report.get("lightgbm_model_vs_physics_calculations") or {}
        summary_lines = []
        if comparison:
            rmse_val = comparison.get("rmse")
            mae_val = comparison.get("mae")
            if rmse_val is not None:
                summary_lines.append(f"Root mean squared error: {rmse_val:.3f}")
            if mae_val is not None:
                summary_lines.append(f"Mean absolute error: {mae_val:.3f}")
        else:
            summary_lines.append("No trip-level comparison available")

    print(json.dumps(report, indent=2))

def main(journey_csv: str | None = None, save_outputs: bool = True):
    journey_csv = OUTPUT_DIR / "journey_energy.csv"    
    journey_statistics(journey_csv, save_outputs=save_outputs)
   
if __name__ == "__main__":
    main()
