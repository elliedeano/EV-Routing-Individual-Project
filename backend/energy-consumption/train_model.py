import lightgbm as lgb
from sklearn.model_selection import train_test_split, RandomizedSearchCV
import joblib
from datetime import datetime
import json
from pathlib import Path


def train_energy_model(df):
    target = "energy_Wh"
    drop_cols = ["id", "COND", "H", "MIN", "SEC", "power", "VOL", "CUR", "time_difference"]
    features = [c for c in df.columns if c not in drop_cols + [target]]

    X = df[features]
    y = df[target]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    output_dir = Path(__file__).parent / "output_files"
    output_dir.mkdir(exist_ok=True)

    try:
        param_dist = {
            "learning_rate": [0.01, 0.03, 0.05],
            "num_leaves": [30, 60],
            "n_estimators": [100, 300, 800],
            "subsample": [0.8, 1.0],
            "colsample_bytree": [0.8, 1.0],
            "min_data_in_leaf": [5, 10, 25, 50],   
            "max_depth": [-1, 5, 10], 
        }

        base_est = lgb.LGBMRegressor(objective="regression", random_state=42, n_jobs=-1)
        cv = 5

        search = RandomizedSearchCV(
            estimator=base_est,
            param_distributions=param_dist,
            n_iter=12,
            scoring="neg_mean_squared_error",
            cv=cv,
            random_state=42,
            n_jobs=-1,
            verbose=0,
        )

        search.fit(X_train, y_train)
        best = search.best_params_
        print("Tuning complete — best params:\n", best)
    except Exception as e:
        print(f"Hyperparameter tuning failed, continuing with defaults: {e}")
   
   
    tuned_params = best if 'best' in locals() else {}
    if tuned_params:
        print("Using tuned params for training:", tuned_params)
        model = lgb.LGBMRegressor(**tuned_params)
    else:
        model = lgb.LGBMRegressor()
    model.fit(X_train, y_train)

    
    tuning_used = bool(tuned_params)
    if tuning_used:
        print("Hyperparameter tuning applied successfully and used for final training.")
        print("Selected hyperparameters:", tuned_params)
    else:
        print("Hyperparameter tuning was not applied; training used default parameters.")

    return model, features


if __name__ == "__main__":
    try:
        from load_data import load_ev_data

        print("Loading data...")
        df = load_ev_data()
        print("Starting training...")
        model, features = train_energy_model(df)
        print("Training finished. Model saved and returned.")
        print(f"Features used ({len(features)}):", features)
    except Exception as e:
        print("Error running training from CLI:", e)
