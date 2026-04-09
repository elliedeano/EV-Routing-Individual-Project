from datetime import datetime
import sys
from contextlib import redirect_stdout, redirect_stderr

from load_data import load_kaggle_dataset
from train_model import training_lightgbm
from predict import predict_energy_consumption
from scale_energy_consumption import scale_for_vehicle_specs

def main():

    df = load_kaggle_dataset()
    model, features = training_lightgbm(df)
    trip_energy = predict_energy_consumption(df, model, features)
    scaled_df = scale_for_vehicle_specs(trip_energy)

    print("\nTrip energy prediction sample:\n", trip_energy.head().to_string())
    print("\nScaled energy sample:\n", scaled_df.head().to_string())
    
if __name__ == "__main__":
    main()
