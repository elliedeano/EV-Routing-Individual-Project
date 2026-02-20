
import json
import re

def parse_price(usage_cost):
    if not usage_cost:
        return float('inf')
    match = re.search(r"[\d.]+", usage_cost)
    return float(match.group()) if match else float('inf')

def extract_charger_features(charger):
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
    traffic_delay = charger.get('traffic_delay', 0) 
    return {
        'price': price,
        'max_power': max_power,
        'is_fast': is_fast,
        'num_points': num_points,
        'status': status,
        'distance': distance,
        'traffic_delay': traffic_delay,
        'raw': charger
    }

def normalize_feature(values, ascendingVsDescending=True):
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        return [1.0 for _ in values]
    if ascendingVsDescending:
        return [(v - min_v) / (max_v - min_v) for v in values]
    else:
        return [(max_v - v) / (max_v - min_v) for v in values]

def rank_and_filter_chargers(chargers, priorities):
    features = [extract_charger_features(c) for c in chargers]
    features = [f for f in features if f['status']]
    if not features:
        return []

    ascendingVsDescending = {
        'price': False,
        'max_power': True,
        'is_fast': True,
        'num_points': True,
        'distance': False,
        'traffic_delay': False
    }

   
    weights = {p: 3-i for i, p in enumerate(priorities)}
    normed = {}
    for p in priorities:
        vals = [f[p] if not isinstance(f[p], bool) else int(f[p]) for f in features]
        normed[p] = normalize_feature(vals, ascendingVsDescending[p])


    for i, f in enumerate(features):
        score = 0
        breakdown = {}
        for p in priorities:
            part = weights[p] * normed[p][i]
            breakdown[p] = {
                'weight': weights[p],
                'normalized': normed[p][i],
                'points': part
            }
            score += part
        f['score'] = score
        f['breakdown'] = breakdown

    features.sort(key=lambda f: f['score'], reverse=True)
    return features

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
        print("No baseline chargers loaded. Please run routing-main.py to generate baseline_chargers.json.")
    else:
        # If traffic_delay is selected, fetch and update traffic delay for each charger
        if 'traffic_delay' in priorities:
            from traffic_filter_calcs import get_traffic_delay_percent
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
