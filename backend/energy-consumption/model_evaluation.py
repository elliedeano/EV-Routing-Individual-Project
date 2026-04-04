import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error
import lightgbm as lgb

from load_data import load_ev_data
import matplotlib.pyplot as plt
import seaborn as sns
from contextlib import redirect_stdout, redirect_stderr


OUTPUT_DIR = Path(__file__).parent / "output_files"
OUTPUT_DIR.mkdir(exist_ok=True)


def aggregate_trip_whpk(df, energy_col="energy_Wh"):
    agg = (
        df.groupby("COND")
        .agg(
            trip_energy_Wh=(energy_col, "sum"),
            trip_distance_km=("ODO", lambda x: float(x.iloc[-1] - x.iloc[0])),
        )
        .reset_index()
    )
    agg = agg[agg["trip_distance_km"] >= 0.05].copy()
    agg["wh_per_km"] = agg["trip_energy_Wh"] / agg["trip_distance_km"]
    return agg.set_index("COND")


def rmse_mae_bias(y_true, y_pred):
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    bias = float(np.mean(y_pred - y_true))
    return {"rmse": rmse, "mae": mae, "bias": bias}


def make_model():
    # simple default LightGBM regressor
    return lgb.LGBMRegressor(verbose=-1)


def main(save_outputs: bool = True):
    df = load_ev_data()

    target = "energy_Wh"
    drop_cols = ["id", "COND", "H", "MIN", "SEC", "power", "VOL", "CUR", "time_difference"]
    
    exclude_more = []
    features = [c for c in df.columns if c not in drop_cols + [target] + exclude_more]

    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    groups = df["COND"].values
    train_idx, test_idx = next(gss.split(df, groups=groups))
    train_df = df.iloc[train_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)


    model_full = make_model()
    train_log_path = OUTPUT_DIR / "training_log.txt"
    # capture LightGBM training output to a log file and suppress console noise
    with open(train_log_path, "w") as logf:
        with redirect_stdout(logf), redirect_stderr(logf):
            model_full.fit(train_df[features], train_df[target])

    importances = sorted(list(zip(features, model_full.feature_importances_)), key=lambda x: -x[1])
    # include all features in the importance list (sorted by importance)
    top_features = importances
    test_df = test_df.copy()
    test_df["pred_full_Wh"] = model_full.predict(test_df[features]).clip(min=0)

    trips_physics = aggregate_trip_whpk(test_df, energy_col="energy_Wh")
    trips_model_full = aggregate_trip_whpk(test_df, energy_col="pred_full_Wh")
    merged_full = trips_physics.join(trips_model_full, how="inner", lsuffix="_physics", rsuffix="_model")
    stats_full = None
    if not merged_full.empty:
        stats_full = rmse_mae_bias(merged_full["wh_per_km_physics"].values, merged_full["wh_per_km_model"].values)

   

    report = {
        "n_test_trips": int(len(trips_physics)),
        "top_feature_importances": [{"feature": f, "importance": int(v)} for f, v in top_features],
        "model_vs_physics": stats_full,
    }

    if save_outputs:
        with open(OUTPUT_DIR / "model_evaluation_report.json", "w") as fh:
            json.dump(report, fh, indent=2)

        comp = pd.DataFrame(index=trips_physics.index)
        comp["trip_energy_physics"] = trips_physics["trip_energy_Wh"]
        comp["trip_distance_km"] = trips_physics["trip_distance_km"]
        comp["wh_per_km_physics"] = trips_physics["wh_per_km"]
        comp["trip_energy_model"] = trips_model_full["trip_energy_Wh"]
        comp["wh_per_km_model"] = trips_model_full["wh_per_km"]
        comp["delta_model_minus_physics"] = comp["wh_per_km_model"] - comp["wh_per_km_physics"]
        comp.reset_index().to_csv(OUTPUT_DIR / "trip_level_comparison.csv", index=False)

        # Parity plot: predicted vs actual (wh/km)
        if not merged_full.empty:
            x = merged_full["wh_per_km_physics"]
            y = merged_full["wh_per_km_model"]
            plt.figure(figsize=(6,6))
            sns.scatterplot(x=x, y=y, alpha=0.6)
            mn, mx = min(x.min(), y.min()), max(x.max(), y.max())
            plt.plot([mn, mx], [mn, mx], "k--")
            plt.xlabel("Actual wh/km")
            plt.ylabel("Predicted wh/km")
            plt.title("Predicted vs Actual (wh/km)")
            plt.tight_layout()
            plt.savefig(OUTPUT_DIR / "pred_vs_actual_whpk.png", dpi=150)
            plt.close()

        # Residual vs trip distance: check distance-dependent bias or heteroskedasticity
        if not comp.empty:
            res = comp["delta_model_minus_physics"]
            plt.figure(figsize=(6,4))
            sns.scatterplot(x=comp["trip_distance_km"], y=res, alpha=0.6)
            plt.axhline(0, color="k", linewidth=0.8)
            plt.xlabel("Trip distance (km)")
            plt.ylabel("Residual (pred - actual) wh/km")
            plt.title("Residual vs Trip Distance")
            plt.tight_layout()
            plt.savefig(OUTPUT_DIR / "residual_vs_distance.png", dpi=150)
            plt.close()

        # Row-level diagnostics (many datapoints even for one trip)
        if not test_df.empty:
            df_rows = test_df.copy()
            df_rows["residual_Wh"] = df_rows["pred_full_Wh"] - df_rows["energy_Wh"]

            # Predicted vs actual (row-level) — convert to kWh and zoom to central range
            df_x = df_rows["energy_Wh"] / 1000.0
            df_y = df_rows["pred_full_Wh"] / 1000.0
            plt.figure(figsize=(6,6))
            sns.scatterplot(x=df_x, y=df_y, alpha=0.4, s=10)
            # robust limits (1st-99th percentile) to avoid extreme outliers stretching axes
            low = min(df_x.quantile(0.01), df_y.quantile(0.01))
            high = max(df_x.quantile(0.99), df_y.quantile(0.99))
            padding = (high - low) * 0.05 if high > low else 0.01
            mn_row = low - padding
            mx_row = high + padding
            plt.plot([mn_row, mx_row], [mn_row, mx_row], "k--")
            plt.xlim(mn_row, mx_row)
            plt.ylim(mn_row, mx_row)
            plt.xlabel("Actual energy (kWh)")
            plt.ylabel("Predicted energy (kWh)")
            plt.title("Predicted vs Actual (row-level, kWh)")
            plt.tight_layout()
            plt.savefig(OUTPUT_DIR / "pred_vs_actual_rowlevel.png", dpi=150)
            plt.close()

            # Residual histogram (row-level)
            plt.figure(figsize=(6,4))
            sns.histplot(df_rows["residual_Wh"], kde=True)
            plt.axvline(df_rows["residual_Wh"].mean(), color="k", linestyle="--", linewidth=0.8)
            plt.xlabel("Residual (pred - actual) Wh")
            plt.title("Residual distribution (row-level)")
            plt.tight_layout()
            plt.savefig(OUTPUT_DIR / "residual_hist_rowlevel.png", dpi=150)
            plt.close()

            # Save per-row predictions and compute row-level RMSE/MAE (Wh)
            try:
                row_res = df_rows["pred_full_Wh"] - df_rows["energy_Wh"]
                row_rmse = float(np.sqrt((row_res ** 2).mean()))
                row_mae = float(np.mean(np.abs(row_res)))
                row_metrics = {"row_rmse_Wh": row_rmse, "row_mae_Wh": row_mae}
                # save per-row CSV for diagnostics
                df_rows.to_csv(OUTPUT_DIR / "row_level_predictions.csv", index=False)
                with open(OUTPUT_DIR / "row_level_metrics.json", "w") as _rf:
                    json.dump(row_metrics, _rf, indent=2)
                # attach to report for convenience (will rewrite report file)
                report["row_level"] = row_metrics
                with open(OUTPUT_DIR / "model_evaluation_report.json", "w") as fh_upd:
                    json.dump(report, fh_upd, indent=2)
                # append to the plain-text summary
                with open(summary_path, "a") as fh:
                    fh.write(f"- row_level_predictions.csv\n")
                    fh.write(f"- row_level_metrics.json\n")
            except Exception:
                # non-fatal: continue without row-level artifacts
                pass

        # Write a short plain-text summary and reference created files (no terminal print)
        summary_path = OUTPUT_DIR / "model_evaluation_summary.txt"
        with open(summary_path, "w") as fh:
            fh.write("Model evaluation summary\n")
            fh.write("========================\n\n")
            json.dump(report, fh, indent=2)
            fh.write("\n\nFiles written:\n")
            fh.write(f"- model_evaluation_report.json\n")
            fh.write(f"- trip_level_comparison.csv\n")
            fh.write(f"- training_log.txt\n")
            if not merged_full.empty:
                fh.write(f"- pred_vs_actual_whpk.png\n")
            if not comp.empty:
                fh.write(f"- residual_vs_distance.png\n")
            # row-level plots
            fh.write(f"- pred_vs_actual_rowlevel.png\n")
            fh.write(f"- residual_hist_rowlevel.png\n")

        # Combined evaluation diagram: feature importances + key stats
        try:
            raw_feats = [f for f, _ in top_features]
            imps = [int(v) for _, v in top_features]
        except Exception:
            raw_feats = [d["feature"] for d in report.get("top_feature_importances", [])][:20]
            imps = [d["importance"] for d in report.get("top_feature_importances", [])][:20]

        # map short codes to human-friendly names
        def humanize_feature(name: str) -> str:
            mapping = {
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
            }
            if name in mapping:
                return mapping[name]
            # fallback: replace underscores and title-case
            return name.replace("_", " ").title()

        feats = [humanize_feature(f) for f in raw_feats]

        # scale figure height with number of features so all are visible
        n_feats = len(feats) if feats else 1
        height = max(6, 0.25 * n_feats + 2)
        fig, axs = plt.subplots(nrows=2, ncols=1, figsize=(12, height), gridspec_kw={"height_ratios": [3, 1]})
        ax1, ax2 = axs[0], axs[1]

        if feats and imps:
            ax1.barh(feats[::-1], imps[::-1], color="C0")
            ax1.set_xlabel("Importance")
            ax1.set_title("Energy Consumption Predictions — Top Feature Importance")
        else:
            ax1.text(0.5, 0.5, "No feature importances", ha="center", va="center")

        # bottom row: concise error summary (RMSE / MAE / Bias) centered under the chart
        mvp = report.get("model_vs_physics") or {}
        summary_lines = []
        if mvp:
            rmse_val = mvp.get("rmse")
            mae_val = mvp.get("mae")
            if rmse_val is not None:
                summary_lines.append(f"Root mean squared error: {rmse_val:.3f}")
            if mae_val is not None:
                summary_lines.append(f"Mean absolute error: {mae_val:.3f}")
        else:
            summary_lines.append("No trip-level comparison available")

        ax2.axis("off")
        # render a titled, left-aligned metrics block under the bar chart
        header_y = 0.85
        ax2.text(0.02, header_y, "Error Metrics", fontsize=12, weight="bold", ha="left", va="top")
        # metrics start slightly below the header
        metrics_text = "\n".join(summary_lines)
        ax2.text(0.02, header_y - 0.18, metrics_text, fontsize=11, ha="left", va="top")

        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "evaluation_summary.png", dpi=150)
        plt.close()

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
