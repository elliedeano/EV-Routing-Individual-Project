import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from load_data import load_ev_data
import json
from datetime import datetime
def main():
    
    df = load_ev_data()

    target = 'power'
    features = df.columns.difference(['id', 'COND', target])
    
    X = df[features]
    y = df[target]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    
    model = lgb.LGBMRegressor(
        objective='regression',
        boosting_type='gbdt',
        learning_rate=0.1,
        num_leaves=31,
        n_estimators=500
    )

 
    model.fit(X_train, y_train)
    # y_pred = model.predict(X_test)
    # output = X_test.copy()
    # output['predicted_power'] = y_pred
    # output.to_csv('predicted_power.csv', index=False)
    
    try:
        import joblib
        joblib.dump(model, 'lgbm_ev_model.pkl')
        print('Pickled sklearn wrapper saved as lgbm_ev_model.pkl')
    except Exception:
        print('joblib not available; skipping pickle of sklearn wrapper')

   
    try:
        model.booster_.save_model('lgbm_ev_model.txt')
        print('LightGBM booster saved as lgbm_ev_model.txt')
    except Exception:
        print('Unable to save LightGBM booster to text')


    metadata = {
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'model_file': 'lgbm_ev_model.txt',
        'model_pickle': 'lgbm_ev_model.pkl',
        'features': list(features),
        'target': target
    }
    with open('model_metadata.json', 'w') as fh:
        json.dump(metadata, fh, indent=2)
    print('Model metadata written to model_metadata.json')

if __name__ == "__main__":
    main()
