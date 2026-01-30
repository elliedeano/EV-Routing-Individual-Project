from car_specs import get_car_specs

def load_and_estimate_range(car_model, soc_percent):
    try:
        specs = get_car_specs(car_model)
        battery_kwh = specs["battery_kwh"]
        wh_per_km = specs["wh_per_km"]
        soc = soc_percent / 100.0
        usable_battery_wh = battery_kwh * 1000 * soc  
        est_range_km = usable_battery_wh / wh_per_km
        print(f"Loaded car: {car_model}")
        print(f"Battery: {battery_kwh:.1f} kWh, Usable: {usable_battery_wh/1000:.1f} kWh")
        print(f"Average consumption: {wh_per_km:.1f} Wh/km")
        print(f"Estimated range: {est_range_km:.1f} km")
        return {
            "car_model": car_model,
            "battery_kwh": battery_kwh,
            "wh_per_km": wh_per_km,
            "usable_battery_wh": usable_battery_wh,
            "est_range_km": est_range_km,
        }
    except Exception as e:
        print(f"Error loading car model: {e}")
        return None

if __name__ == "__main__":
    car_model = input("Enter your car model: ")
    soc = input("Enter initial state of charge (SOC) as percent (default 80): ")
    soc = float(soc) if soc else 80.0
    load_and_estimate_range(car_model, soc)

from car_specs import get_car_specs

def load_and_estimate_range(car_model, soc_percent):
    try:
        specs = get_car_specs(car_model)
        battery_kwh = specs["battery_kwh"]
        wh_per_km = specs["wh_per_km"]
        soc = soc_percent / 100.0
        usable_battery_wh = battery_kwh * 1000 * soc  
        est_range_km = usable_battery_wh / wh_per_km
        print(f"Loaded car: {car_model}")
        print(f"Battery: {battery_kwh:.1f} kWh, Usable: {usable_battery_wh/1000:.1f} kWh")
        print(f"Average consumption: {wh_per_km:.1f} Wh/km")
        print(f"Estimated range: {est_range_km:.1f} km")
        return {
            "car_model": car_model,
            "battery_kwh": battery_kwh,
            "wh_per_km": wh_per_km,
            "usable_battery_wh": usable_battery_wh,
            "est_range_km": est_range_km,
        }
    except Exception as e:
        print(f"Error loading car model: {e}")
        return None

if __name__ == "__main__":
    car_model = input("Enter your car model: ")
    soc = input("Enter initial state of charge (SOC) as percent (default 80): ")
    soc = float(soc) if soc else 80.0
    load_and_estimate_range(car_model, soc)
