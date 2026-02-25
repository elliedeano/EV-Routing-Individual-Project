
import lightgbm as lgb
from sklearn.model_selection import train_test_split
import joblib
from datetime import datetime
import json

def train_energy_model(df):
    target = "energy_Wh"
    drop_cols = ["id", "COND", "H", "MIN", "SEC", "power"]
    features = df.columns.difference(drop_cols + [target])

    X = df[features]
    y = df[target]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = lgb.LGBMRegressor(
        objective="regression",
        boosting_type="gbdt",
        learning_rate=0.05,
        num_leaves=31,
        n_estimators=800,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )

    model.fit(X_train, y_train)
    from pathlib import Path
    output_dir = Path(__file__).parent / "output_files"
    output_dir.mkdir(exist_ok=True)
    model_path = output_dir / "lgbm_ev_energy_model.pkl"
    joblib.dump(model, model_path)

    print(f"Model trained and saved to {model_path}")

    metadata = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "model_pickle": str(model_path),
        "features": list(features),
        "target": target,
        "units": "Wh per timestep",
    }

    metadata_path = output_dir / "model_metadata.json"
    with open(metadata_path, "w") as fh:
        json.dump(metadata, fh, indent=2)

    return model, features

