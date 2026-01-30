import networkx as nx
import matplotlib.pyplot as plt
import requests
import os
from pathlib import Path

# lazily import osmnx (may not be installed in all environments). Use
# ensure_osmnx() before calling functions that need it.
ox = None


def ensure_osmnx():
    global ox
    if ox is None:
        try:
            import osmnx as _ox
        except Exception:
            raise RuntimeError(
                "osmnx is not installed or failed to import. "
                "Install osmnx or place a cached graph at data/processed/west_midlands_20km.graphml"
            )
        # Try to help pyproj/PROJ find its data directory. On some conda
        # installations pyproj ships PROJ data under the pyproj package and
        # the PROJ_LIB env var or pyproj.datadir isn't set automatically; this
        # causes errors like "proj_create: no database context specified" when
        # geopandas/osmnx try to construct CRS objects. Attempt to set the
        # datadir and PROJ_LIB from pyproj if available.
        try:
            import pyproj
            data_dir = None
            try:
                data_dir = pyproj.datadir.get_data_dir()
            except Exception:
                data_dir = None

            if data_dir:
                # export PROJ_LIB for subprocesses and native libs
                os.environ.setdefault("PROJ_LIB", data_dir)
                try:
                    # set_data_dir is a runtime configuration that helps
                    # pyproj locate the PROJ database in-process.
                    pyproj.datadir.set_data_dir(data_dir)
                    print(f"Configured pyproj PROJ data dir: {data_dir}")
                except Exception as _e:
                    # Not fatal; we'll let downstream code surface errors if any.
                    print(f"Warning: could not set pyproj datadir: {_e}")
            else:
                # best-effort: if PROJ_LIB already set, show it for diagnostics
                if os.environ.get("PROJ_LIB"):
                    print(f"PROJ_LIB already set: {os.environ.get('PROJ_LIB')}")
                else:
                    print("Warning: pyproj.datadir.get_data_dir() returned empty; if you see proj_create errors, install proj/proj-data from conda-forge.")
        except Exception:
            # pyproj not installed or failed; that's okay here — graph download
            # will either succeed or the earlier build_graph() handler will
            # provide guidance.
            pass

        ox = _ox


PLACE = "West Midlands, England, UK"

CENTER_LAT = 52.48
CENTER_LON = -1.90
RADIUS_KM = 80
MAX_RESULTS = 500

OCM_API_KEY = "bc0fb54f-d673-4829-9bbb-f2abac2c11f8"  # your key


def build_graph():
    """Build or load a graph.

    This function prefers a cached graph at data/processed/west_midlands_20km.graphml.
    If not present it will download a smaller point-based graph (dev) unless
    the environment variable FULL_GRAPH is set, in which case it will download
    the full place graph (this can be slow and memory intensive).
    """
    project_root = Path(__file__).resolve().parents[2]
    cache_dir = project_root / "data" / "processed"
    cache_file = cache_dir / "west_midlands_20km.graphml"

    if cache_file.exists():
        try:
            ensure_osmnx()
            print(f"Loading cached graph: {cache_file}")
            return ox.load_graphml(str(cache_file))
        except Exception:
            # If osmnx/import issues prevent loading, fall back to cache-less handling below
            print("Warning: osmnx failed while trying to load cached graph; will attempt fallback.")

    # Try to initialize osmnx; if it fails (ImportError / pyproj issues),
    # optionally fall back to a small in-memory mock graph so the CLI can run
    try:
        ensure_osmnx()
    except Exception as exc:
        # If user explicitly requested a mock graph, return it; otherwise
        # prefer to use cache if available, else fall back to mock with a warning.
        if os.environ.get("MOCK_GRAPH") in ("1", "true", "True"):
            print("osmnx unavailable — using MOCK_GRAPH in-memory graph for dev/testing.")
            return _make_mock_graph()

        if cache_file.exists():
            print(f"osmnx import failed ({exc}); attempting to load cached graph via networkx: {cache_file}")
            try:
                import networkx as _nx

                return _nx.read_graphml(str(cache_file))
            except Exception:
                print("Warning: failed to load cached graph via networkx; falling back to mock graph.")
                return _make_mock_graph()

        print("osmnx import failed and no cached graph available; falling back to MOCK in-memory graph.")
        print("To fix permanently, install the geospatial stack via conda-forge: conda install -c conda-forge proj proj-data pyproj osmnx geopandas")
        return _make_mock_graph()

    # Choose full place graph only when explicitly requested
    # Attempt download, but be defensive: on pyproj/PROJ errors (common when
    # PROJ database isn't installed or pyproj can't find it) surface a helpful
    # message and fall back to using a cached graph if present.
    try:
        if os.environ.get("FULL_GRAPH") in ("1", "true", "True"):
            print(f"Downloading full graph for: {PLACE} (this may take a long time)")
            G = ox.graph_from_place(PLACE, network_type="drive")
        else:
            print(f"Downloading small point graph around center (dev) ...")
            G = ox.graph_from_point((CENTER_LAT, CENTER_LON), dist=20000, network_type="drive")
    except Exception as exc:
        # Try to detect pyproj CRS errors to give targeted guidance
        try:
            import pyproj
            from pyproj.exceptions import CRSError
            is_crs_error = isinstance(exc, CRSError) or (hasattr(exc, "__cause__") and isinstance(exc.__cause__, CRSError))
        except Exception:
            is_crs_error = False

        if is_crs_error:
            print("\nError: pyproj/PROJ database not available or could not be initialized.")
            print("This commonly happens when the PROJ data files are not installed in the Python environment.")
            print("If you are using conda, the easiest fix is to install the geospatial stack from conda-forge:")
            print("  conda install -c conda-forge proj proj-data pyproj osmnx geopandas rtree fiona shapely")
            print("After installing, restart your Python process and try again.\n")

            # If a cache exists, use it; otherwise re-raise with context so the caller can handle it.
            if cache_file.exists():
                print(f"Found cached graph at {cache_file}; loading cached graph instead of downloading.")
                return ox.load_graphml(str(cache_file))
            else:
                raise RuntimeError(
                    "pyproj/PROJ not initialized and no cached graph available. "
                    "Install PROJ (see message above) or place a graphml file at data/processed/west_midlands_20km.graphml"
                ) from exc
        else:
            # Non-pyproj error: if cache exists, use it; otherwise re-raise original exception.
            if cache_file.exists():
                print(f"Download failed ({exc}); loading cached graph: {cache_file}")
                return ox.load_graphml(str(cache_file))
            raise

    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        ox.save_graphml(G, str(cache_file))
        print(f"Saved graph to {cache_file}")
    except Exception:
        print("Warning: failed to save cached graph")

    return G


def _make_mock_graph():
    """Create a tiny in-memory graph useful for development and testing.

    The graph uses NetworkX with node attributes 'x' (lon) and 'y' (lat) and
    edge attribute 'length' (meters) so routing functions can operate.
    """
    import networkx as _nx

    G = _nx.DiGraph()
    # Create a small 4-node line: A -- B -- C -- D (coords roughly UK)
    nodes = [
        (1, {"y": 52.48, "x": -1.90}),
        (2, {"y": 53.00, "x": -1.50}),
        (3, {"y": 54.00, "x": -1.40}),
        (4, {"y": 56.00, "x": -1.30}),
    ]
    for n, attrs in nodes:
        G.add_node(n, **attrs)

    # Add bi-directional edges with approximate distances (meters)
    edges = [
        (1, 2, 60000.0),
        (2, 3, 110000.0),
        (3, 4, 220000.0),
    ]
    for u, v, length in edges:
        G.add_edge(u, v, length=length)
        G.add_edge(v, u, length=length)

    # Mark node 2 as a charger for testing
    G.nodes[2]["is_charger"] = True
    G.nodes[2]["charger_name"] = "Mock Charger"
    G.nodes[2]["ocm_id"] = 9999
    G.nodes[2]["max_power_kw"] = 50

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
    # Prefer osmnx nearest_nodes when available, but fall back to a simple
    # node-coordinate nearest search so this function works with the mock graph.
    use_osmnx = False
    try:
        if ox is not None:
            # verify the API exists
            _ = ox.distance.nearest_nodes
            use_osmnx = True
    except Exception:
        use_osmnx = False

    if use_osmnx:
        for ch in chargers:
            node = ox.distance.nearest_nodes(G, ch["lon"], ch["lat"])  # lon, lat
            snapped.append({**ch, "node": node})
        return snapped

    # Manual nearest-node search (lat/lon) — expects node attrs 'y'/'x' or 'lat'/'lon'.
    def _haversine_km(lat1, lon1, lat2, lon2):
        from math import radians, sin, cos, asin, sqrt

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return 2 * 6371.0 * asin(sqrt(a))

    for ch in chargers:
        best = None
        best_d = float("inf")
        for n, data in G.nodes(data=True):
            nlat = data.get("y") or data.get("lat") or data.get("latitude")
            nlon = data.get("x") or data.get("lon") or data.get("longitude")
            if nlat is None or nlon is None:
                continue
            try:
                d = _haversine_km(ch["lat"], ch["lon"], float(nlat), float(nlon))
            except Exception:
                continue
            if d < best_d:
                best_d = d
                best = n
        if best is not None:
            snapped.append({**ch, "node": best})
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
    # If osmnx plotting is available, prefer it; otherwise use a simple
    # networkx/matplotlib fallback so plotting works with the mock graph.
    try:
        if ox is not None:
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
            return
    except Exception:
        pass

    # Fallback: simple networkx draw
    fig, ax = plt.subplots(figsize=(8, 6))
    # draw edges
    for u, v in G.edges():
        a = G.nodes[u]
        b = G.nodes[v]
        if all(k in a for k in ("x", "y")) and all(k in b for k in ("x", "y")):
            ax.plot([a["x"], b["x"]], [a["y"], b["y"]], color="gray", linewidth=0.8)

    # draw chargers
    if snapped_chargers:
        xs, ys = [], []
        for ch in snapped_chargers:
            n = ch["node"]
            nx = G.nodes[n].get("x") or G.nodes[n].get("lon")
            ny = G.nodes[n].get("y") or G.nodes[n].get("lat")
            if nx is not None and ny is not None:
                xs.append(nx)
                ys.append(ny)
        ax.scatter(xs, ys, c="red", s=20, label="OCM chargers")
        ax.legend()

    ax.set_xlabel("lon")
    ax.set_ylabel("lat")
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