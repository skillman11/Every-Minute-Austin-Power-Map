
# Austin Energy Outage Scraper

Automatically samples Austin Energy's live outage map every 5 minutes and stores the data in this repository. Runs entirely on GitHub's free servers — no computer required.

## What it collects

Each snapshot captures the current outage state from Austin Energy's Kubra-powered outage map, including outage counts and geographic data. Snapshots are stored in the `data/` folder, one file per day, with each 5-minute snapshot on its own line.

## Data format

Files are stored as `.jsonl` (one JSON object per line) in the `data/` folder:

```
data/
  2026-06-04.jsonl
  2026-06-05.jsonl
  ...
```

Each line looks like:
```json
{"timestamp": "2026-06-04T02:35:00+00:00", "snapshot": { ... outage data ... }}
```

## Setup instructions

1. **Fork or clone this repo** into your own GitHub account (skillman11)

2. **Enable GitHub Actions** — go to the Actions tab in your repo and click "I understand my workflows, go ahead and enable them" if prompted

3. **That's it.** The scraper will run automatically every 5 minutes and commit new data files to the `data/` folder

## Running it manually

Go to the Actions tab, click "Scrape Austin Energy Outages", then click "Run workflow" to trigger it immediately without waiting for the schedule.

## Notes

- GitHub's free tier gives you 2,000 Actions minutes/month. Each run takes only a few seconds, so you'll use roughly 150-200 minutes/month — well within the free limit.
- GitHub's scheduler is not exact to the second; runs may be delayed a minute or two during high-traffic periods.
- Data is stored in UTC time.
