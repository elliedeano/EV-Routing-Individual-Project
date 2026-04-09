import re
import math

def price_value_to_decimal(usage_cost):
    if usage_cost is None:
        return float('inf')

    if isinstance(usage_cost, (int, float)):
        value = float(usage_cost)
        return value if math.isfinite(value) and value >= 0 else float('inf')

    usage_text = str(usage_cost).strip().lower()
    if not usage_text:
        return float('inf')

    if usage_text in {"0","free", "no charge", "0.0", "£0", "€0", "$0"}:
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

def extract_charger_data(charger):
    price = charger.get('price')
    if price is None:
        price = price_value_to_decimal(charger.get('UsageCost'))
    else:
        if isinstance(price, str):
            stripped = price.strip()
            if stripped:
                try:
                    numeric_price = float(stripped)
                except ValueError:
                    numeric_price = price_value_to_decimal(stripped)
            else:
                numeric_price = float('inf')
        elif isinstance(price, (int, float)):
            numeric_price = float(price)
        else:
            numeric_price = float('inf')

        if math.isfinite(numeric_price) and numeric_price >= 0:
            price = numeric_price
        else:
            price = price_value_to_decimal(charger.get('UsageCost'))
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
    try:
        traffic_delay = float(traffic_delay)
    except (TypeError, ValueError):
        traffic_delay = 0.0
    if not math.isfinite(traffic_delay):
        traffic_delay = 0.0
    if traffic_delay < 0:
        traffic_delay = 0.0
   
    meal_window = charger.get('meal_stop', False)
    distance_stop = charger.get('distance_stop', False)
    return {
        'price': price,
        'max_power': max_power,
        'is_fast': is_fast,
        'num_points': num_points,
        'status': status,
        'distance': distance,
        'traffic_delay': traffic_delay,
        'meal_stop': meal_window,
        'distance_stop': distance_stop,
        'raw': charger
    }

def normalise_feature(values, ascendingVsDescending=True):
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


def compute_users_priorities(priorities):
    return {p: 3 - i for i, p in enumerate(priorities)}


def normalise_each_priority(features, priorities, ascendingVsDescending):
    normalise = {}
    for p in priorities:
        vals = [f[p] if not isinstance(f[p], bool) else int(f[p]) for f in features]
        normalise[p] = normalise_feature(vals, ascendingVsDescending[p])
    return normalise


def charger_scores(features, priorities, weights, normalise):
    for i, f in enumerate(features):
        score = 0
        breakdown = {}
        missing_penalty = 0.0
        for p in priorities:
            part = weights[p] * normalise[p][i]
            breakdown[p] = {
                'weight': weights[p],
                'normalised': normalise[p][i],
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
    return features

def rank_chargers(features, priorities):
    if 'price' in priorities:
        features.sort(
            key=lambda f: (not math.isfinite(float(f.get('price'))) if isinstance(f.get('price'), (int, float, str)) else True,
                float(f.get('price')) if isinstance(f.get('price'), (int, float)) and math.isfinite(float(f.get('price'))) else float('inf'),
                -f['score']))
    else:
        features.sort(key=lambda f: f['score'], reverse=True)

    return features[:3]


def overall_charger_ranking(chargers, priorities):
    features = [extract_charger_data(c) for c in chargers]
    features = [f for f in features if f['status'] is not False]
    if not features:
        return []

    ascVsDesc = {
        'price': False,
        'max_power': True,
        'is_fast': True,
        'num_points': True,
        'distance': False,
        'traffic_delay': False,
        'meal_stop': True,
        'distance_stop': True
    }

    weights = compute_users_priorities(priorities)
    normalise = normalise_each_priority(features, priorities, ascVsDesc)
    features = charger_scores(features, priorities, weights, normalise)
    return rank_chargers(features, priorities)

def user_priorities_to_array(input_str):
    valid = {'price', 'max_power', 'is_fast', 'num_points', 'distance', 'traffic_delay'}
    return [p.strip() for p in input_str.lower().split(',') if p.strip() in valid][:3]


def rank_and_filter_chargers(chargers, priorities):
    ranked = overall_charger_ranking(chargers, priorities)
    output = []
    for feature in ranked:
        if 'meal_stop' not in feature:
            feature['meal_stop'] = feature.pop('meal_window', False) if isinstance(feature, dict) else False
        if 'distance_stop' not in feature:
            feature['distance_stop'] = feature.get('distance_stop', False)
        output.append(feature)
    return output

