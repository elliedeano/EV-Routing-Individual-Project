from pathlib import Path
import sys
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr

# Import your energy and routing modules
sys.path.append(str(Path(__file__).resolve().parent / "backend" / "energy-consumption"))

from load_data import load_ev_data
from train_model import train_energy_model
from predict import predict_trip_energy
from scale_energy_consumption import scale_to_other_cars

class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)

    def flush(self):
        for stream in self.streams:
            stream.flush()

def main():
    output_dir = Path(__file__).resolve().parent / "backend" / "energy-consumption" / "output_files"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = output_dir / f"training_{run_stamp}.log"

    with open(log_path, "w") as log_file:
        tee_stdout = _Tee(sys.stdout, log_file)
        tee_stderr = _Tee(sys.stderr, log_file)
        with redirect_stdout(tee_stdout), redirect_stderr(tee_stderr):
            print(f"Training run started at {datetime.now().isoformat()}")
            print(f"Writing log to {log_path}")

            df = load_ev_data()
            model, features = train_energy_model(df)
            print("\nModel training complete.\n")

            trip_energy = predict_trip_energy(df, model, features)
            print("\nTrip energy prediction sample:\n", trip_energy.head())

            scaled_df = scale_to_other_cars(trip_energy)
            print("\nScaled energy sample:\n", scaled_df.head())
            print("\nEnergy modeling complete. Scaled results ready for routing.\n")

            print(f"Training run finished at {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()
