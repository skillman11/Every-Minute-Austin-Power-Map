name: Scrape Austin Energy Outages

on:
  schedule:
    - cron: '*/1 * * * *'
  workflow_dispatch:

jobs:
  scrape:
    runs-on: ubuntu-latest

    permissions:
      contents: write

    steps:
      - name: Check out repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests

      - name: Run scraper
        run: python scrape.py

      - name: Commit and push data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          git diff --cached --quiet || git commit -m "Outage snapshot $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
          git pull --rebase origin main
          git push
