
import json
import re
import math

def parse_price(usage_cost):
    if usage_cost is None:
        return float('inf')

    if isinstance(usage_cost, (int, float)):
        value = float(usage_cost)
        return value if math.isfinite(value) and value >= 0 else float('inf')

    usage_text = str(usage_cost).strip().lower()
    if not usage_text:
        return float('inf')

    if usage_text in {"free", "no charge", "0", "0.0", "£0", "€0", "$0"}:
        return 0.0

    pence_match = re.search(r"(\d+(?:\.\d+)?)\s*p(?:\s*/\s*kwh)?", usage_text)
    if pence_match and "£" not in usage_text and "gbp" not in usage_text:
        try:
            pence_value = float(pence_match.group(1))
            if math.isfinite(pence_value) and pence_value >= 0:
                return pence_value / 100.0
        except ValueError:
            pass

    match = re.search(r"\d+(?:\.\d+)?", usage_text)
    if match:
        try:
            value = float(match.group())
            if math.isfinite(value) and value >= 0:
                return value
        except ValueError:
            pass
    return float('inf')

def extract_charger_features(charger):
    raw_price = charger.get('price')
    if raw_price is None:
        price = parse_price(charger.get('UsageCost'))
    else:
        if isinstance(raw_price, str):
            stripped = raw_price.strip()
            if stripped:
                try:
                    numeric_price = float(stripped)
                except ValueError:
                    numeric_price = parse_price(stripped)
            else:
                numeric_price = float('inf')
        elif isinstance(raw_price, (int, float)):
            numeric_price = float(raw_price)
        else:
            numeric_price = float('inf')

        if math.isfinite(numeric_price) and numeric_price >= 0:
            price = numeric_price
        else:
            price = parse_price(charger.get('UsageCost'))
    connections = charger.get('Connections', [])
    if connections:
        max_power = max((c.get('PowerKW', 0) or 0) for c in connections)
    else:
        max_power = 0
    is_fast = any(c.get('Level', {}).get('IsFastChargeCapable') for c in connections)
    num_points = charger.get('NumberOfPoints', 1)
    status_type = charger.get('StatusType')
    if status_type is None:
        status = False
    else:
        status = status_type.get('IsOperational', False)
    distance = charger.get('AddressInfo', {}).get('Distance', float('inf'))
    raw_traffic_delay = charger.get('traffic_delay', 0)
    try:
        traffic_delay = float(raw_traffic_delay)
    except (TypeError, ValueError):
        traffic_delay = 0.0
    if not math.isfinite(traffic_delay):
        traffic_delay = 0.0
    if traffic_delay < 0:
        traffic_delay = 0.0
   
    meal_stop = charger.get('meal_stop', False)
    distance_stop = charger.get('distance_stop', False)
    return {
        'price': price,
        'max_power': max_power,
        'is_fast': is_fast,
        'num_points': num_points,
        'status': status,
        'distance': distance,
        'traffic_delay': traffic_delay,
        'meal_stop': meal_stop,
        'distance_stop': distance_stop,
        'raw': charger
    }

def normalize_feature(values, ascendingVsDescending=True):
    numeric_values = []
    for value in values:
        if value is None:
            numeric_values.append(None)
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            numeric_values.append(None)
            continue
        if not math.isfinite(numeric_value):
            numeric_values.append(None)
            continue
        numeric_values.append(numeric_value)

    finite_values = [value for value in numeric_values if value is not None]
    if not finite_values:
        return [0.0 for _ in numeric_values]

    finite_min = min(finite_values)
    finite_max = max(finite_values)
    fallback_value = finite_min if ascendingVsDescending else finite_max
    clean_values = [value if value is not None else fallback_value for value in numeric_values]

    min_v = min(clean_values)
    max_v = max(clean_values)
    if max_v == min_v:
        return [0.0 for _ in clean_values]
    if ascendingVsDescending:
        return [(value - min_v) / (max_v - min_v) for value in clean_values]
    return [(max_v - value) / (max_v - min_v) for value in clean_values]

def rank_and_filter_chargers(chargers, priorities):
    features = [extract_charger_features(c) for c in chargers]
    features = [f for f in features if f['status'] is not False]
    if not features:
        return []

    ascendingVsDescending = {
        'price': False,
        'max_power': True,
        'is_fast': True,
        'num_points': True,
        'distance': False,
        'traffic_delay': False,
        'meal_stop': True,
        'distance_stop': True
    }

   
    weights = {p: 3-i for i, p in enumerate(priorities)}
    normed = {}
    for p in priorities:
        vals = [f[p] if not isinstance(f[p], bool) else int(f[p]) for f in features]
        normed[p] = normalize_feature(vals, ascendingVsDescending[p])


    for i, f in enumerate(features):
        score = 0
        breakdown = {}
        missing_penalty = 0.0
        for p in priorities:
            part = weights[p] * normed[p][i]
            breakdown[p] = {
                'weight': weights[p],
                'normalized': normed[p][i],
                'points': part
            }
            score += part
            raw_value = f.get(p)
            if isinstance(raw_value, bool):
                value_missing = False
            elif raw_value is None:
                value_missing = True
            else:
                try:
                    numeric_value = float(raw_value)
                    value_missing = not math.isfinite(numeric_value)
                except (TypeError, ValueError):
                    value_missing = False
            if value_missing:
                missing_penalty += weights[p] * 1e-6
        if 'price' in priorities and not math.isfinite(float(f.get('price', float('inf')))):
            missing_penalty += 1000.0
        score -= missing_penalty
        f['score'] = score
        f['breakdown'] = breakdown

    if 'price' in priorities:
        def _price_missing(feature):
            raw_price = feature.get('price')
            try:
                return not math.isfinite(float(raw_price))
            except (TypeError, ValueError):
                return True

        def _price_value(feature):
            if _price_missing(feature):
                return float('inf')
            return float(feature.get('price'))
        features.sort(key=lambda f: (_price_missing(f), _price_value(f), -f['score']))
    else:
        features.sort(key=lambda f: f['score'], reverse=True)
    return features[:3]

def get_user_priorities(input_str):
    valid = {'price', 'max_power', 'is_fast', 'num_points', 'distance', 'traffic_delay'}
    return [p.strip() for p in input_str.lower().split(',') if p.strip() in valid][:3]

if __name__ == "__main__":
    import json
    try:
        with open('../output/baseline_chargers.json') as f:
            chargers = json.load(f)
    except Exception:
        chargers = []

    priorities_list = [
        ("price", "Lowest price per kWh"),
        ("max_power", "Highest charging power (kW)"),
        ("is_fast", "Fast charge capable"),
        ("num_points", "Most charging points"),
        ("distance", "Closest distance"),
        ("traffic_delay", "Least traffic delay (% increase)")
    ]
    print("\nSelect your top 3 priorities by number (comma separated):")
    for idx, (key, desc) in enumerate(priorities_list, 1):
        print(f"  {idx}. {key} - {desc}")
    while True:
        user_input = input("Enter 3 numbers (e.g. 1,3,6): ").strip()
        nums = [n.strip() for n in user_input.split(',') if n.strip().isdigit()]
        if len(nums) == 3 and all(1 <= int(n) <= len(priorities_list) for n in nums):
            priorities = [priorities_list[int(n)-1][0] for n in nums]
            break
        else:
            print("Invalid input. Please enter 3 numbers from the list above.")
    if not chargers:
        print("No baseline chargers loaded. Generate baseline_chargers.json before running this ranking script.")
    else:
        if 'traffic_delay' in priorities:
            from backend.routing.traffic_calculations import get_traffic_delay_percent
            start_lat = input("Enter your trip start latitude: ")
            start_lon = input("Enter your trip start longitude: ")
            start_coords = (float(start_lat), float(start_lon))
            for c in chargers:
                addr = c.get('AddressInfo', {})
                charger_coords = (addr.get('Latitude'), addr.get('Longitude'))
                if charger_coords[0] is not None and charger_coords[1] is not None:
                    c['traffic_delay'] = get_traffic_delay_percent(start_coords, charger_coords)
                else:
                    c['traffic_delay'] = 0.0
        ranked = rank_and_filter_chargers(chargers, priorities)
        print("\nTop Charger Recommendations:")
        for i, c in enumerate(ranked[:5], 1):
            addr = c['raw'].get('AddressInfo', {}).get('Title', 'Unknown')
            print(f"{i}. {addr} | Price: {c['price']} | Power: {c['max_power']} kW | Fast: {c['is_fast']} | Points: {c['num_points']} | Distance: {c['distance']:.2f} km | Traffic Delay: {c['traffic_delay']:.1f}%")
            if i == 1:
                print("  --- Breakdown for top charger ---")
                for p in priorities:
                    b = c['breakdown'][p]
                    print(f"    {p}: weight={b['weight']}, normalized={b['normalized']:.2f}, points={b['points']:.2f}")
                print(f"    Total score: {c['score']:.2f}")
