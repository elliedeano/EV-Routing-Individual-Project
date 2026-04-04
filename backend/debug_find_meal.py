import sys
from datetime import datetime
sys.path.insert(0, '.')
from backend.routing.find_meal_based_chargers import find_meal_based_chargers

route = [(51.5, -0.1), (52.0, -0.12)]
car_specs = {"battery_kwh": 50, "wh_per_km": 150}
soc = 50
journey_start = datetime.now()

try:
    chargers = find_meal_based_chargers(route, car_specs, soc, journey_start)
    print('OK', len(chargers))
    print(chargers[:2])
except Exception as e:
    import traceback
    traceback.print_exc()
    print('ERROR', e)
