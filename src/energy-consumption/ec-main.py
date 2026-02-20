from pathlib import Path
from load_data import load_ev_data
from train_model import train_energy_model
from predict import predict_trip_energy
from scale_vehicles import scale_to_other_cars


def main():
    df = load_ev_data()
    model, features = train_energy_model(df)
    trip_df = predict_trip_energy(df, model, features)
    scaled_df = scale_to_other_cars(trip_df)

    # Save outputs for routing/main.py
    project_root = Path(__file__).resolve().parents[2]
    trip_df.to_csv(project_root / "data" / "raw" / "trip_energy.csv", index=False)
    # Rename column for main.py compatibility
    scaled_df = scaled_df.rename(columns={"wh_per_km": "wh_per_km_raw"})
    scaled_df.to_csv(project_root / "data" / "raw" / "scaled_trip_energy.csv", index=False)

    print("\n✅ PIPELINE COMPLETE — CHECK RANGES ABOVE")


if __name__ == "__main__":
    main()
