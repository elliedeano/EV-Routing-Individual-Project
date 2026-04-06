from datetime import datetime
import sys
from contextlib import redirect_stdout, redirect_stderr

from load_data import load_ev_data
from train_model import train_energy_model
from predict import predict_trip_energy
from scale_energy_consumption import scale_to_other_cars

def main():

    df = load_ev_data()
    model, features = train_energy_model(df)
    trip_energy = predict_trip_energy(df, model, features)
    scaled_df = scale_to_other_cars(trip_energy)

    print("\nTrip energy prediction sample:\n", trip_energy.head().to_string())
    print("\nScaled energy sample:\n", scaled_df.head().to_string())
    
if __name__ == "__main__":
    main()
