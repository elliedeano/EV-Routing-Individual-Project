import json
from pathlib import Path
import joblib
import pandas as pd
import numpy as np

proj_root = Path(__file__).resolve().parents[1]
ec_dir = proj_root / 'backend' / 'energy-consumption'
meta_path = ec_dir / 'output_files' / 'model_metadata.json'
with open(meta_path) as fh:
    meta = json.load(fh)
model_pickle = Path(meta.get('model_pickle'))
if not model_pickle.exists():
    candidate = ec_dir / model_pickle.name
    if candidate.exists():
        model_pickle = candidate
print('model_pickle:', model_pickle)
model = joblib.load(model_pickle)
features = meta.get('features')
print('num features:', len(features))
# make df
rows = []
for i, odo in enumerate([0,1,2,5], start=1):
    row = {'COND':1, 'id':i, 'ODO':odo}
    for f in features:
        row[f] = 1.0
    rows.append(row)
start = len(rows)+1
for j, odo in enumerate([100,105,110], start=start):
    row = {'COND':2, 'id':j, 'ODO':odo}
    for f in features:
        row[f] = 2.0
    rows.append(row)
df = pd.DataFrame(rows)
print('df shape', df.shape)
print(df[['COND','id','ODO']])
print('missing features:', [f for f in features if f not in df.columns])
X = df[features]
print('X shape', X.shape)
# predict
preds = model.predict(X)
print('preds length', len(preds), 'nan_count', int(np.isnan(preds).sum()))
print('preds sample', preds[:10])
df['predicted_energy_Wh'] = preds
print('df with preds sample:\n', df[['COND','id','ODO','predicted_energy_Wh']].head(10))
# groupby
trip_energy = (
    df.groupby('COND')
    .agg(
        trip_energy_Wh=('predicted_energy_Wh', 'sum'),
        trip_rows=('id', 'count'),
        trip_distance_km=('ODO', lambda x: x.iloc[-1] - x.iloc[0]),
    )
    .reset_index()
)
print('trip_energy before filter:\n', trip_energy)
trip_energy_filtered = trip_energy[trip_energy['trip_distance_km'] >= 0.05]
print('trip_energy after filter:\n', trip_energy_filtered)

# also call original function for sanity
spec_path = ec_dir / 'predict.py'
import importlib.util, sys
spec = importlib.util.spec_from_file_location('predict_mod', str(spec_path))
predict_mod = importlib.util.module_from_spec(spec)
if str(ec_dir) not in sys.path:
    sys.path.insert(0, str(ec_dir))
spec.loader.exec_module(predict_mod)
print('\nCalling predict_mod.predict_trip_energy()...')
res = predict_mod.predict_trip_energy(df, model, features)
print('predict_mod returned:\n', res)
