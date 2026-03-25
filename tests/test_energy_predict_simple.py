import importlib.util
import sys
from pathlib import Path
import pandas as pd
import numpy as np


proj_root = Path(__file__).resolve().parents[1]
ec_dir = proj_root / "backend" / "energy-consumption"
spec = importlib.util.spec_from_file_location("predict_mod", str(ec_dir / "predict.py"))
predict_mod = importlib.util.module_from_spec(spec)
if str(ec_dir) not in sys.path:
    sys.path.insert(0, str(ec_dir))
spec.loader.exec_module(predict_mod)


def test_predict_simple_dummy_model():
    # Minimal feature set and two trips (simple increasing ODO per trip)
    features = ["f1", "f2", "ODO"]
    rows = []
    for i, odo in enumerate([0, 1, 2, 5], start=1):
        row = {"COND": 1, "id": i, "ODO": odo, "f1": 1.0, "f2": 0.5}
        rows.append(row)
    start = len(rows) + 1
    for j, odo in enumerate([100, 105, 110], start=start):
        row = {"COND": 2, "id": j, "ODO": odo, "f1": 2.0, "f2": 1.0}
        rows.append(row)

    df = pd.DataFrame(rows)

    class DummyModel:
        def predict(self, X):
            # return a positive constant per timestep (no external deps)
            return np.full(len(X), 100.0)

    out = predict_mod.predict_trip_energy(df, DummyModel(), features)

    assert set(out["COND"]) == {1, 2}
    assert (out["trip_energy_Wh"] > 0).all()
    assert np.isfinite(out["wh_per_km_raw"]).all()
