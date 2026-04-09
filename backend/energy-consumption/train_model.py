import lightgbm as lgb
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from pathlib import Path


#takes in the feature engineered dataset then trains a LightGBM model to predict energy consumption. 
def training_lightgbm(df):
#Define the target feature and drop any features that are used in target feature calculation so there is no data leakage. 
    target_feature = "energy_Wh"
    drop_columns = ["id", "COND", "H", "MIN", "SEC", "power", "VOL", "CUR", "time_difference"]
    features = [c for c in df.columns if c not in drop_columns + [target_feature]]


    X = df[features]
    y = df[target_feature]
#Decide on a train and test split.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    output_directory = Path(__file__).parent / "output_files"
    output_directory.mkdir(exist_ok=True)

#Hyperparameter tuning.
    try:
        parameter_options = {
            "learning_rate": [0.01, 0.03, 0.05],
            "num_leaves": [30, 60],
            "n_estimators": [100, 300, 800],
            "subsample": [0.8, 1.0],
            "colsample_bytree": [0.8, 1.0],
            "min_data_in_leaf": [5, 10, 25, 50],   
            "max_depth": [-1, 5, 10], 
        }

        estimation = lgb.LGBMRegressor(objective="regression", random_state=42, n_jobs=-1)
        cross_validation = 5

        search = RandomizedSearchCV(
            estimator=estimation,
            param_distributions=parameter_options,
            n_iter=12,
            scoring="neg_mean_squared_error",
            cv=cross_validation,
            random_state=42,
            n_jobs=-1,
            verbose=0,
        )

        search.fit(X_train, y_train)
#save the best parameters found.
        best = search.best_params_
    except Exception as e:
        print(f"Hyperparameter tuning error: {e}")
   
   
#Create final model. 
    selected_parameters= best if 'best' in locals() else {}
    if selected_parameters:
        model = lgb.LGBMRegressor(**selected_parameters)
    else:
        model = lgb.LGBMRegressor()
#Train the model on the training data
    model.fit(X_train, y_train)
    return model, features


if __name__ == "__main__":
    try:
        from load_data import load_ev_data
        df = load_ev_data()
        model, features = training_lightgbm(df)
    except Exception as e:
        print("Error")
