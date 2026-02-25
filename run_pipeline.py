from pathlib import Path
import sys

# Import your energy and routing modules
sys.path.append(str(Path(__file__).resolve().parent / "src" / "energy-consumption"))
sys.path.append(str(Path(__file__).resolve().parent / "src" / "routing"))

from load_data import load_ev_data
from train_model import train_energy_model
from predict import predict_trip_energy
from scale_energy_consumption import scale_to_other_cars

# Import routing main
import importlib
routing_main = importlib.import_module("routing_main")

def main():
    # 1. Energy modeling pipeline
    df = load_ev_data()
    model, features = train_energy_model(df)
    print("\nModel training complete.\n")
    trip_energy = predict_trip_energy(df, model, features)
    print("\nTrip energy prediction sample:\n", trip_energy.head())
    scaled_df = scale_to_other_cars(trip_energy)
    print("\nScaled energy sample:\n", scaled_df.head())
    print("\nEnergy modeling complete. Scaled results ready for routing.\n")

    # 2. Routing system (calls routing_main.py's main)
    print("\nStarting routing system...\n")
    routing_main.main()

if __name__ == "__main__":
    main()
