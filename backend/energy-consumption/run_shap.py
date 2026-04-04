import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import GroupShuffleSplit
import lightgbm as lgb

from load_data import load_ev_data

OUTPUT_DIR = Path(__file__).parent / "output_files"
OUTPUT_DIR.mkdir(exist_ok=True)


def make_model(params=None):
    default = {
        "objective": "regression",
        "boosting_type": "gbdt",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "n_estimators": 800,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_samples": 20,
        "max_depth": -1,
        "random_state": 42,
        "n_jobs": -1,
    }
    if params:
        default.update(params)
    return lgb.LGBMRegressor(**default)


def main(sample_frac=1.0):
    df = load_ev_data()
    target = "energy_Wh"
    drop_cols = ["id", "COND", "H", "MIN", "SEC", "power"]
    features = [c for c in df.columns if c not in drop_cols + [target]]

    # group split
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    groups = df["COND"].values
    train_idx, test_idx = next(gss.split(df, groups=groups))
    train_df = df.iloc[train_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)

    model = make_model()
    X_train = train_df[features]
    y_train = train_df[target]
    model.fit(X_train, y_train)

    # sample some rows for SHAP (to limit compute)
    if sample_frac < 1.0:
        test_sample = test_df.sample(frac=sample_frac, random_state=42)
    else:
        test_sample = test_df.copy()

    X_sample = test_sample[features]

    try:
        import shap
        import matplotlib.pyplot as plt
    except Exception as e:
        print("Missing dependencies for SHAP. Install with: pip install shap matplotlib")
        raise

    # TreeExplainer for LightGBM
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)

    # shap_values shape: (n_samples, n_features)
    mean_abs_shap = np.mean(np.abs(shap_values), axis=0)
    shap_df = pd.DataFrame({"feature": features, "mean_abs_shap": mean_abs_shap})
    shap_df = shap_df.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)

    shap_csv = OUTPUT_DIR / "shap_summary.csv"
    shap_df.to_csv(shap_csv, index=False)
    print(f"SHAP summary saved to {shap_csv}")

    # bar plot
    plt.figure(figsize=(8, max(4, 0.2 * len(shap_df))))
    plt.barh(shap_df["feature"], shap_df["mean_abs_shap"][::-1])
    plt.xlabel("Mean |SHAP value|")
    plt.title("Feature importance (mean absolute SHAP)")
    plt.tight_layout()
    plot_path = OUTPUT_DIR / "shap_summary.png"
    plt.savefig(plot_path)
    print(f"SHAP bar plot saved to {plot_path}")


if __name__ == "__main__":
    main()
