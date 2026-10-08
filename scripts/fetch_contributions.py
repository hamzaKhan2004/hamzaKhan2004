from pathlib import Path
import json
import re

import requests
from bs4 import BeautifulSoup


USERNAME = "hamzaKhan2004"
URL = f"https://github.com/users/{USERNAME}/contributions"

OUTPUT = Path("data/contributions.json")


def fetch_contributions():
    print("Fetching GitHub contributions...")

    response = requests.get(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0",
        },
        timeout=20,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    cells = soup.select("td.ContributionCalendar-day[data-date]")

    print(f"Found {len(cells)} contribution days.")

    contributions = []

    for cell in cells:
        date = cell.get("data-date")
        level = cell.get("data-level", "0")

        try:
            level = int(level)
        except ValueError:
            level = 0

        contributions.append({
            "date": date,
            "level": level,
        })

    # GitHub normally returns ~365 days.
    # Keep only valid calendar cells.
    contributions = [
        item
        for item in contributions
        if item["date"] and 0 <= item["level"] <= 4
    ]

    total_active_days = sum(
        1 for item in contributions
        if item["level"] > 0
    )

    highest_level = max(
        (item["level"] for item in contributions),
        default=0,
    )

    print("--------------------------------------")
    print(f"Days              : {len(contributions)}")
    print(f"Active days       : {total_active_days}")
    print(f"Highest level     : {highest_level}")
    print("--------------------------------------")

    print("\nSample contribution data:")
    print("--------------------------------------")

    for item in contributions[:10]:
        print(item)

    print("--------------------------------------")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(
            {
                "username": USERNAME,
                "days": contributions,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nSaved to: {OUTPUT}")


if __name__ == "__main__":
    fetch_contributions()