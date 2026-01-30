import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
import requests


PLACE = "West Midlands, England, UK"

CENTER_LAT = 52.48
CENTER_LON = -1.90
RADIUS_KM = 80
MAX_RESULTS = 500

OCM_API_KEY = "bc0fb54f-d673-4829-9bbb-f2abac2c11f8"  # your key


def build_graph():
    print(f"Downloading graph for: {PLACE}")
    G = ox.graph_from_place(PLACE, network_type="drive")
    return G


def fetch_ocm_chargers():
    """
    Call Open Charge Map API once for chargers around the West Midlands.
    Returns raw JSON list of POIs.
    """
    url = "https://api.openchargemap.io/v3/poi"
    params = {
        "output": "json",
        "latitude": CENTER_LAT,
        "longitude": CENTER_LON,
        "distance": RADIUS_KM,
        "distanceunit": "KM",
        "maxresults": MAX_RESULTS,
        "compact": True,
        "verbose": False,
        "key": OCM_API_KEY,
    }

    headers = {
        "X-API-Key": OCM_API_KEY,
        "X-API-Client": "ev-routing-mvp",
    }

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def flatten_pois_to_chargers(pois):
    """
    Turn OCM POI JSON into a simple list of charger dicts with
    name, lat, lon, optional max_power_kw.
    """
    chargers = []
    for poi in pois:
        addr = poi.get("AddressInfo") or {}
        conns = poi.get("Connections") or []

        max_kw = None
        for c in conns:
            kw = c.get("PowerKW")
            if kw is not None:
                max_kw = kw if max_kw is None else max(max_kw, kw)

        lat = addr.get("Latitude")
        lon = addr.get("Longitude")
        if lat is None or lon is None:
            continue

        chargers.append(
            {
                "ocm_id": poi.get("ID"),
                "name": addr.get("Title"),
                "lat": float(lat),
                "lon": float(lon),
                "max_power_kw": max_kw,
            }
        )

    print(f"Flattened to {len(chargers)} chargers with coordinates")
    return chargers


def snap_chargers_to_graph(G, chargers):
    """
    Given a list of chargers with lat/lon, attach nearest node ID.
    Returns list of chargers with extra 'node' field.
    """
    snapped = []
    for ch in chargers:
        node = ox.distance.nearest_nodes(G, ch["lon"], ch["lat"])  # lon, lat
        snapped.append({**ch, "node": node})
    return snapped


def mark_charger_nodes(G, snapped_chargers):
    """
    Tag charger nodes on the graph, storing name, id, and power (if any).
    """
    if not snapped_chargers:
        return G

    nx.set_node_attributes(G, False, "is_charger")

    for ch in snapped_chargers:
        n = ch["node"]
        G.nodes[n]["is_charger"] = True
        G.nodes[n]["charger_name"] = ch["name"]
        G.nodes[n]["ocm_id"] = ch["ocm_id"]
        if ch["max_power_kw"] is not None:
            G.nodes[n]["max_power_kw"] = ch["max_power_kw"]

    return G


def plot_graph_with_chargers(G, snapped_chargers):
    """
    Plot road graph and overlay charger points as red dots.
    """
    fig, ax = ox.plot_graph(
        G,
        node_size=0,
        edge_linewidth=0.5,
        show=False,
        close=False,
    )

    if snapped_chargers:
        xs, ys = [], []
        for ch in snapped_chargers:
            n = ch["node"]
            xs.append(G.nodes[n]["x"])
            ys.append(G.nodes[n]["y"])
        ax.scatter(xs, ys, c="red", s=8, label="OCM chargers")
        ax.legend()

    plt.show()


def main():
    # 1. Build graph
    G = build_graph()

    # 2. Fetch chargers from OCM
    pois = fetch_ocm_chargers()

    # 3. Flatten POIs -> simple charger dicts
    chargers = flatten_pois_to_chargers(pois)

    # 4. Snap chargers to graph, mark nodes
    snapped_chargers = snap_chargers_to_graph(G, chargers)
    G = mark_charger_nodes(G, snapped_chargers)

    # 5. Plot
    plot_graph_with_chargers(G, snapped_chargers)


if __name__ == "__main__":
    main()
