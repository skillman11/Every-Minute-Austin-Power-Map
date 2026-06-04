import requests
import json
import os
from datetime import datetime, timezone

# Austin Energy's Kubra API identifiers
INSTANCE_ID = "dd9c446f-f6b8-43f9-8f80-83f5245c60a1"
VIEW_ID = "76446308-a901-4fa3-849c-3dd569933a51"

def get_current_state():
    """Fetch the current state/report IDs from Kubra"""
    url = f"https://kubra.io/stormcenter/api/v1/stormcenters/{INSTANCE_ID}/views/{VIEW_ID}/currentState?preview=false"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()

def get_report_data(report_url):
    """Fetch the actual outage report data"""
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(report_url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()

def save_snapshot(data, timestamp):
    """Save a timestamped snapshot to the data folder"""
    os.makedirs("data", exist_ok=True)
    # One file per day, with each snapshot appended as a line
    date_str = timestamp.strftime("%Y-%m-%d")
    filepath = f"data/{date_str}.jsonl"
    record = {
        "timestamp": timestamp.isoformat(),
        "snapshot": data
    }
    with open(filepath, "a") as f:
        f.write(json.dumps(record) + "\n")
    print(f"Saved snapshot at {timestamp.isoformat()} to {filepath}")

def main():
    timestamp = datetime.now(timezone.utc)
    print(f"Scraping Austin Energy outage data at {timestamp.isoformat()}")

    try:
        state = get_current_state()
        print("Got current state from Kubra")

        # Pull summary-level outage counts if available
        outage_summary = state.get("data", {})

        # Try to get the detailed report URL if present
        report_url = None
        try:
            stormcenter_data = state.get("data", {}).get("interval_generation_data", "")
            if stormcenter_data:
                report_url = f"https://kubra.io/{stormcenter_data}public/summary-1/data.json"
        except Exception:
            pass

        snapshot = {
            "current_state": state,
        }

        if report_url:
            try:
                print(f"Fetching report data from: {report_url}")
                report_data = get_report_data(report_url)
                snapshot["report"] = report_data
                print("Got detailed report data")
            except Exception as e:
                print(f"Could not fetch report data: {e}")

        save_snapshot(snapshot, timestamp)

    except Exception as e:
        print(f"Error during scrape: {e}")
        raise

if __name__ == "__main__":
    main()
