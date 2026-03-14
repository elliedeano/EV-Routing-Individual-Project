import pandas as pd
from load_data import load_ev_data
from train_model import train_energy_model
from pathlib import Path

def predict_trip_energy(df, model, features):
    df["predicted_energy_Wh"] = model.predict(df[features])
    df["predicted_energy_Wh"] = df["predicted_energy_Wh"].clip(lower=0)

    trip_energy = (
        df.groupby("COND")
        .agg(
            trip_energy_Wh=("predicted_energy_Wh", "sum"),
            trip_rows=("id", "count"),
            trip_distance_km=("ODO", lambda x: x.iloc[-1] - x.iloc[0]),
        )
        .reset_index()
    )

    trip_energy = trip_energy[trip_energy["trip_distance_km"] >= 0.05]

    trip_energy["wh_per_km_raw"] = (
        trip_energy["trip_energy_Wh"] / trip_energy["trip_distance_km"]
    )

    print("Prediction complete. Sample output:")
    print(trip_energy.head())
    output_dir = Path(__file__).parent / "output_files"
    output_dir.mkdir(exist_ok=True)
    trip_energy.to_csv(output_dir / "trip_energy.csv", index=False)
    print(f"trip_energy.csv saved to {output_dir / 'trip_energy.csv'}")
    return trip_energy

def main():
    df = load_ev_data()
    model, features = train_energy_model(df)
    predict_trip_energy(df, model, features)

if __name__ == "__main__":
    main()

