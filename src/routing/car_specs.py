"""
Get battery size and energy consumption for a car model from a dictionary.
Extendable for more cars later.
"""

CAR_SPECS = {
    "JAC iEV7s": {
        "battery_kwh": 42.8,
        "wh_per_km": 173,
    },
    # Add more car models here as needed
}

def get_car_specs(car_model):
    specs = CAR_SPECS.get(car_model)
    if specs is None:
        raise ValueError(f"Car model '{car_model}' not found in CAR_SPECS.")
    return specs

if __name__ == "__main__":
    car_model = input("Enter your car model: ")
    specs = get_car_specs(car_model)
    print(f"Specs for {car_model}: {specs}")
