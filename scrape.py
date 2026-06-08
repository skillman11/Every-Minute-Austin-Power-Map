# scrape.py v2.0
# v1.0 - Initial version, basic state fetch only
# v1.1 - Follows Kubra data paths to get summary outage counts
# v2.0 - Full quadkey tile walking to get individual outage locations with lat/lon
#         Uses mercantile for tile math and polyline for coordinate decoding
#         Outage data now includes latitude, longitude, customers affected, cause, ETR
#         Linked to: scrape.yml (scheduler), viewer.html (map display)

import requests
import json
import os
import mercantile
import polyline as pl
from datetime import datetime, timezone

INSTANCE_ID = "dd9c446f-f6b8-43f9-8f80-83f5245c60a1"
VIEW_ID = "76446308-a901-4fa3-849c-3dd569933a51"
BASE_URL = "https://kubra.io"
MIN_ZOOM = 9
MAX_ZOOM = 14

# Austin Energy approximate service area bounding box
# [west, south, east, north]
AUSTIN_BBOX = [-98.17, 30.02, -97.45, 30.62]

def get(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.ok:
            return resp.json()
    except Exception as e:
        print(f"  Request failed: {url} - {e}")
    return None

def get_quadkey_url(cluster_path, layer_name, quadkey):
    data_path = cluster_path.replace("{qkh}", quadkey[-3:][::-1])
    return f"{BASE_URL}/{data_path}/public/{layer_name}/{quadkey}.json"

def get_neighboring_quadkeys(quadkey):
    tile = mercantile.quadkey_to_tile(quadkey)
    neighbors = []
    for dx, dy in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
        try:
            neighbors.append(mercantile.quadkey(
                mercantile.Tile(x=tile.x+dx, y=tile.y+dy, z=tile.z)
            ))
        except Exception:
            pass
    return neighbors

def get_outage_info(raw_outage, source_url):
    desc = raw_outage.get("desc", {})
    geom = raw_outage.get("geom", {})
    loc = [0.0, 0.0]
    try:
        points = pl.decode(geom["p"][0])
        if points:
            loc = list(points[0])
    except Exception:
        pass

    cause = None
    try:
        cause = desc.get("cause", {}).get("EN-US")
    except Exception:
        pass

    return {
        "id": f"{geom.get('p',[''])[0]}-{desc.get('start_time','')}" if not desc.get("inc_id") else desc.get("inc_id"),
        "latitude": loc[0],
        "longitude": loc[1],
        "custAffected": desc.get("cust_a", {}).get("val", 0) if isinstance(desc.get("cust_a"), dict) else 0,
        "numberOut": desc.get("n_out", 0),
        "cluster": desc.get("cluster", False),
        "cause": cause,
        "etr": desc.get("etr"),
        "crewStatus": desc.get("crew_status"),
        "startTime": desc.get("start_time"),
        "source": source_url
    }

def fetch_outages(cluster_path, layer_name):
    outages = {}
    already_seen = set()

    # Start with service area quadkeys at MIN_ZOOM
    start_tiles = list(mercantile.tiles(*AUSTIN_BBOX, zooms=[MIN_ZOOM]))
    queue = [(mercantile.quadkey(t), MIN_ZOOM) for t in start_tiles]
    processed = set()

    while queue:
        quadkey, zoom = queue.pop(0)
        if quadkey in processed:
            continue
        processed.add(quadkey)

        url = get_quadkey_url(cluster_path, layer_name, quadkey)
        if url in already_seen:
            continue
        already_seen.add(url)

        data = get(url)
        if not data or "file_data" not in data:
            continue

        for o in data["file_data"]:
            desc = o.get("desc", {})
            is_cluster = desc.get("cluster", False)

            if is_cluster and zoom < MAX_ZOOM:
                # Zoom into cluster
                try:
                    geom = o.get("geom", {})
                    point = pl.decode(geom["p"][0])[0]
                    next_qk = mercantile.quadkey(
                        mercantile.tile(lng=point[1], lat=point[0], zoom=zoom+1)
                    )
                    queue.append((next_qk, zoom+1))
                except Exception:
                    outage_info = get_outage_info(o, url)
                    outages[outage_info["id"]] = outage_info
            else:
                outage_info = get_outage_info(o, url)
                outages[outage_info["id"]] = outage_info
                # Check neighbors at same zoom
                for nq in get_neighboring_quadkeys(quadkey):
                    if nq not in processed:
                        queue.append((nq, zoom))

    return list(outages.values())

def main():
    timestamp = datetime.now(timezone.utc)
    print(f"Scraping at {timestamp.isoformat()}")

    state = get(f"{BASE_URL}/stormcenter/api/v1/stormcenters/{INSTANCE_ID}/views/{VIEW_ID}/currentState?preview=false")
    if not state:
        print("Failed to get current state")
        return

    interval_path = state.get("data", {}).get("interval_generation_data")
    cluster_path = state.get("data", {}).get("cluster_interval_generation_data", "")
    deployment_id = state.get("stormcenterDeploymentId")

    snapshot = {"current_state": state}

    # Get summary counts
    if interval_path:
        summary = get(f"{BASE_URL}/{interval_path}/public/summary-1/data.json")
        if summary:
            snapshot["summary"] = summary
            total = summary.get("summaryFileData", {}).get("totals", [{}])[0]
            expected = total.get("total_outages", 0)
            print(f"Summary: {total.get('total_cust_a',{}).get('val',0)} customers affected, {expected} outages")

            # Only fetch locations if there are actual outages
            if expected > 0 and cluster_path and deployment_id:
                # Get layer name from config
                layer_name = None
                config = get(f"{BASE_URL}/stormcenter/api/v1/stormcenters/{INSTANCE_ID}/views/{VIEW_ID}/configuration/{deployment_id}?preview=false")
                if config:
                    try:
                        layers = config["config"]["layers"]["data"]["interval_generation_data"]
                        layer_name = [l for l in layers if l["type"].startswith("CLUSTER_LAYER")][0]["id"]
                        print(f"Layer name: {layer_name}")
                    except Exception as e:
                        print(f"Could not get layer name: {e}")

                if layer_name:
                    print("Fetching outage locations...")
                    outages = fetch_outages(cluster_path, layer_name)
                    snapshot["outages"] = outages
                    print(f"Found {len(outages)} outage locations")
            else:
                snapshot["outages"] = []
                print("No active outages, skipping location fetch")

    # Save snapshot
    os.makedirs("data", exist_ok=True)
    date_str = timestamp.strftime("%Y-%m-%d")
    filepath = f"data/{date_str}.jsonl"
    with open(filepath, "a") as f:
        f.write(json.dumps({"timestamp": timestamp.isoformat(), "snapshot": snapshot}) + "\n")
    print(f"Saved to {filepath}")

if __name__ == "__main__":
    main()
