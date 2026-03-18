import json
from pathlib import Path
import joblib
import pandas as pd
import json
from importlib.util import spec_from_file_location, module_from_spec
import sys
import lightgbm as lgb
import sys
from importlib.util import spec_from_file_location, module_from_spec

def test_model_predict_single_row():
    metadata_path = Path("backend") / "energy-consumption" / "output_files" / "model_metadata.json"
    if not metadata_path.exists():
        spec_tm = spec_from_file_location("train_mod", str(Path("backend") / "energy-consumption" / "train_model.py"))
        train_mod = module_from_spec(spec_tm)
        spec_tm.loader.exec_module(train_mod)
        import numpy as np
        n = 20
        df = pd.DataFrame({
            "id": range(n),
            "COND": [1 if i < n/2 else 2 for i in range(n)],
            "H": 0,
            "MIN": 0,
            "SEC": 1,
            "VOL": np.full(n, 120.0),
            "CUR": np.full(n, 10.0),
            "SPD": np.linspace(5, 15, n),
            "AX": np.zeros(n),
            "AY": np.zeros(n),
            "AZ": np.zeros(n),
            "GX": np.zeros(n),
            "GY": np.zeros(n),
            "GZ": np.zeros(n),
            "ALT": np.zeros(n),
            "ODO": np.linspace(0, 10, n),
        })
        df["energy_Wh"] = df["SPD"] * 10.0
        orig_reg = train_mod.lgb.LGBMRegressor

        def small_reg(*args, **kwargs):
            kwargs.setdefault("n_estimators", 10)
            return orig_reg(*args, **kwargs)

        train_mod.lgb.LGBMRegressor = small_reg
        try:
            train_mod.train_energy_model(df)
        finally:
            train_mod.lgb.LGBMRegressor = orig_reg

    metadata = json.loads(metadata_path.read_text())
    model_path = Path(metadata["model_pickle"]).resolve()
    assert model_path.exists(), f"Missing model file at {model_path}"
    model = joblib.load(model_path)
    try:
        feature_names = model.booster_.feature_name()
    except Exception:
        feature_names = metadata.get("features", [])
    row = {f: 0.0 for f in feature_names}
    df = pd.DataFrame([row])

    preds = model.predict(df[feature_names])
    assert len(preds) == 1
    assert pd.notnull(preds).all()


def test_predict_trip_energy_and_scale():
    metadata_path = Path("backend") / "energy-consumption" / "output_files" / "model_metadata.json"
    metadata = json.loads(metadata_path.read_text())
    model = joblib.load(metadata["model_pickle"])
    try:
        feature_names = model.booster_.feature_name()
    except Exception:
        feature_names = metadata.get("features", [])
    rows = []
    idx = 1
    for cond in [1, 2]:
        rows.append({**{f: 0.1 for f in feature_names}, "id": idx, "COND": cond, "ODO": 0.0})
        idx += 1
        rows.append({**{f: 0.1 for f in feature_names}, "id": idx, "COND": cond, "ODO": 1.0})
        idx += 1

    df = pd.DataFrame(rows)
    ec_path = str(Path("backend") / "energy-consumption")
    sys.path.insert(0, ec_path)
    spec = spec_from_file_location("predict_mod", str(Path("backend") / "energy-consumption" / "predict.py"))
    predict_mod = module_from_spec(spec)
    spec.loader.exec_module(predict_mod)
    trip_energy = predict_mod.predict_trip_energy(df, model, feature_names)
    assert "wh_per_km_raw" in trip_energy.columns
    assert (trip_energy["trip_distance_km"] > 0).all()
    spec2 = spec_from_file_location("scale_mod", str(Path("backend") / "energy-consumption" / "scale_energy_consumption.py"))
    scale_mod = module_from_spec(spec2)
    spec2.loader.exec_module(scale_mod)
    scaled = scale_mod.scale_to_other_cars(trip_energy)
    assert set(["COND", "Car Model", "wh_per_km_raw"]).issubset(set(scaled.columns))


def test_load_ev_data(tmp_path):
   
    raw_dir = Path("data") / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    csv_path = raw_dir / "test_small.csv"
    rows = []
    for cond in [1, 2]:
        for odo in [0.0, 1.0, 2.0]:
            rows.append({
                "COND": cond,
                "id": len(rows) + 1,
                "H": 0,
                "MIN": 0,
                "SEC": 1,
                "AX": 0.0,
                "AY": 0.0,
                "AZ": 0.0,
                "GX": 0.0,
                "GY": 0.0,
                "GZ": 0.0,
                "ALT": 0.0,
                "ODO": odo,
                "VOL": 120,
                "CUR": 10,
                "SPD": 5,
            })
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    spec = spec_from_file_location("load_mod", str(Path("backend") / "energy-consumption" / "load_data.py"))
    load_mod = module_from_spec(spec)
    spec.loader.exec_module(load_mod)
    df = load_mod.load_ev_data(filename="test_small.csv")
    for col in ["time_difference", "power", "energy_Wh", "acceleration_magnitude_roll", "speed_roll"]:
        assert col in df.columns


def test_scaling_handles_null():
    spec2 = spec_from_file_location("scale_mod", str(Path("backend") / "energy-consumption" / "scale_energy_consumption.py"))
    scale_mod = module_from_spec(spec2)
    spec2.loader.exec_module(scale_mod)
    empty = pd.DataFrame(columns=["COND", "wh_per_km_raw"])  
    scaled = scale_mod.scale_to_other_cars(empty)
    assert set(["COND", "Car Model", "wh_per_km_raw"]).issubset(set(scaled.columns))


def test_run_pipeline_outputs(monkeypatch, tmp_path):
    import numpy as np
    n = 20
    df = pd.DataFrame({
        "id": range(n),
        "COND": [1 if i < n/2 else 2 for i in range(n)],
        "H": 0,
        "MIN": 0,
        "SEC": 1,
        "VOL": np.full(n, 120.0),
        "CUR": np.full(n, 10.0),
        "SPD": np.linspace(5, 15, n),
        "AX": np.zeros(n),
        "AY": np.zeros(n),
        "AZ": np.zeros(n),
        "GX": np.zeros(n),
        "GY": np.zeros(n),
        "GZ": np.zeros(n),
        "ALT": np.zeros(n),
        "ODO": np.linspace(0, 10, n),
    })
    df["energy_Wh"] = df["SPD"] * 10.0
    spec_rp = spec_from_file_location("run_pipeline_mod", str(Path("run_pipeline.py")))
    rp_mod = module_from_spec(spec_rp)
    spec_rp.loader.exec_module(rp_mod)
    monkeypatch.setattr(rp_mod, "load_ev_data", lambda: df)
    tm = sys.modules.get("train_model")
    if tm is None:
        for k, v in list(sys.modules.items()):
            if k.endswith("train_model"):
                tm = v
                break

    if tm is not None and hasattr(tm, "lgb"):
        orig_reg = tm.lgb.LGBMRegressor
        def small_reg(*args, **kwargs):
            kwargs.setdefault("n_estimators", 10)
            return orig_reg(*args, **kwargs)
        monkeypatch.setattr(tm.lgb, "LGBMRegressor", small_reg)
    rp_mod.main()

    output_dir = Path("backend") / "energy-consumption" / "output_files"
    metadata_path = output_dir / "model_metadata.json"
    model_path = output_dir / "lgbm_ev_energy_model.pkl"
    trip_path = output_dir / "trip_energy.csv"
    scaled_path = output_dir / "scaled_trip_energy.csv"

    assert metadata_path.exists()
    assert model_path.exists()
    assert trip_path.exists()
    assert scaled_path.exists()

    meta = json.loads(metadata_path.read_text())
    assert "features" in meta and isinstance(meta["features"], list)
    assert meta.get("target") == "energy_Wh"

