import csv
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_JSON = PROJECT_ROOT / "src" / "output" / "baseline_chargers.json"
CAR_MODELS_CSV = PROJECT_ROOT / "data" / "raw" / "car-energy-database-30.csv"

if str(PROJECT_ROOT / "src") not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _load_car_models() -> List[str]:
	models: List[str] = []
	with open(CAR_MODELS_CSV, newline="") as csvfile:
		reader = csv.DictReader(csvfile)
		for row in reader:
			model = (row.get("Car Model ") or "").strip()
			if model:
				models.append(model)
	seen = set()
	ordered = []
	for model in models:
		if model not in seen:
			ordered.append(model)
			seen.add(model)
	return ordered


def _priority_number_map(umbrella_choice: str) -> Dict[str, str]:
	umbrella_key = "meal_stop" if umbrella_choice == "meal" else "distance_stop"
	ordered = [
		umbrella_key,
		"price",
		"max_power",
		"is_fast",
		"num_points",
		"distance",
		"traffic_delay",
	]
	return {key: str(index + 1) for index, key in enumerate(ordered)}


def _extract_float(pattern: str, text: str) -> Optional[float]:
	match = re.search(pattern, text)
	if not match:
		return None
	try:
		return float(match.group(1))
	except Exception:
		return None


def _strip_ansi(text: str) -> str:
	return re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text or "")


def compute_route_via_cli(
	start_postcode: str,
	end_postcode: str,
	soc: float,
	car_model: Optional[str] = None,
	umbrella_choice: str = "distance",
	meal_window: Optional[str] = None,
	priorities: Optional[List[str]] = None,
	journey_start: Optional[str] = None,
) -> Dict[str, Any]:
	from charger_ranking.rank_chargers import rank_and_filter_chargers

	all_models = _load_car_models()
	selected_model = car_model if car_model in all_models else (all_models[0] if all_models else None)
	if not selected_model:
		raise RuntimeError("No car models available for CLI selection")
	model_number = str(all_models.index(selected_model) + 1)

	umbrella_choice = "meal" if umbrella_choice == "meal" else "distance"
	umbrella_number = "2" if umbrella_choice == "meal" else "1"

	umbrella_key = "meal_stop" if umbrella_choice == "meal" else "distance_stop"
	effective_priorities = priorities or [umbrella_key, "max_power", "is_fast"]
	additional_priorities = [p for p in effective_priorities if p != umbrella_key][:2]
	if len(additional_priorities) < 2:
		fallback = ["max_power", "is_fast"]
		for key in fallback:
			if key not in additional_priorities:
				additional_priorities.append(key)
			if len(additional_priorities) == 2:
				break

	priority_map = _priority_number_map(umbrella_choice)
	prio_numbers = [priority_map.get(p) for p in additional_priorities]
	if any(v is None for v in prio_numbers):
		raise RuntimeError(f"Invalid priorities for CLI mapping: {additional_priorities}")
	priority_input = ",".join(prio_numbers)

	journey_value = journey_start if journey_start else "now"
	cli_input = "\n".join([
		str(journey_value),
		str(start_postcode),
		str(end_postcode),
		str(soc),
		model_number,
		umbrella_number,
		priority_input,
	]) + "\n"

	completed = subprocess.run(
		[
			sys.executable,
			"-c",
			(
				"import sys; "
				"from pathlib import Path; "
				"root=Path.cwd(); "
				"sys.path.insert(0, str(root / 'src' / 'routing')); "
				"import routing_main; "
				"routing_main.main()"
			),
		],
		cwd=str(PROJECT_ROOT),
		input=cli_input,
		text=True,
		capture_output=True,
		timeout=300,
		check=False,
	)

	stdout = completed.stdout or ""
	stderr = completed.stderr or ""
	logs = stdout + ("\n" + stderr if stderr else "")
	clean_stdout = _strip_ansi(stdout)
	if completed.returncode != 0:
		raise RuntimeError(f"CLI route execution failed (exit {completed.returncode})\n{logs}")

	total_km = _extract_float(r"Total distance:\s*([0-9]+(?:\.[0-9]+)?)\s*km", clean_stdout)
	est_range_km = _extract_float(r"Estimated range on current charge:\s*([0-9]+(?:\.[0-9]+)?)\s*km", clean_stdout)

	no_charging_needed = "No charging stops needed" in clean_stdout

	if no_charging_needed:
		return {
			"total_km": total_km if total_km is not None else 0.0,
			"est_range_km": est_range_km if est_range_km is not None else 0.0,
			"start_coords": None,
			"chargers": [],
			"logs": logs,
		}

	if not BASELINE_JSON.exists():
		raise RuntimeError("CLI did not produce baseline_chargers.json")

	import json

	with open(BASELINE_JSON) as f:
		baseline_chargers = json.load(f)

	ranked = rank_and_filter_chargers(baseline_chargers, [umbrella_key, *additional_priorities])

	out_chargers: List[Dict[str, Any]] = []
	for c in ranked:
		raw = c.get("raw", c)
		addr = raw.get("AddressInfo", {})
		out_chargers.append(
			{
				"id": raw.get("ID") or addr.get("ID"),
				"title": addr.get("Title"),
				"max_power": c.get("max_power") if "max_power" in c else raw.get("max_power"),
				"is_fast": c.get("is_fast") if "is_fast" in c else raw.get("is_fast"),
				"route_km": c.get("route_km") if "route_km" in c else raw.get("route_km"),
				"distance": c.get("distance") if "distance" in c else addr.get("Distance"),
				"latitude": addr.get("Latitude"),
				"longitude": addr.get("Longitude"),
				"meal_window": c.get("meal_window") if "meal_window" in c else raw.get("meal_window"),
				"nearby_places": c.get("nearby_places") if "nearby_places" in c else raw.get("nearby_places"),
				"price": c.get("price") if "price" in c else raw.get("price"),
				"num_points": c.get("num_points") if "num_points" in c else raw.get("num_points"),
				"traffic_delay": c.get("traffic_delay") if "traffic_delay" in c else raw.get("traffic_delay"),
				"meal_stop": c.get("meal_stop") if "meal_stop" in c else raw.get("meal_stop", False),
				"score": c.get("score"),
				"breakdown": c.get("breakdown"),
			}
		)

	if umbrella_choice == "meal" and meal_window:
		normalized_window = str(meal_window).strip().lower()
		allowed = {"breakfast", "coffee", "lunch", "dinner"}
		if normalized_window in allowed:
			filtered = [
				charger for charger in out_chargers
				if str(charger.get("meal_window") or "").strip().lower() == normalized_window
			]
			if filtered:
				out_chargers = filtered

	return {
		"total_km": total_km if total_km is not None else 0.0,
		"est_range_km": est_range_km if est_range_km is not None else 0.0,
		"start_coords": None,
		"chargers": out_chargers,
		"logs": logs,
	}
