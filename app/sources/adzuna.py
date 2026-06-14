"""Adzuna job search aggregator (aggregates LinkedIn/Indeed/company postings).

Requires a free API key from https://developer.adzuna.com/ — set these env
vars before starting the API server:

    ADZUNA_APP_ID=...
    ADZUNA_APP_KEY=...
    ADZUNA_COUNTRY=se   # optional, defaults to "se" (Sweden); use country
                        # codes like "gb", "de", "us", etc.

If the keys are not set, this source returns no results (search still works
with the other sources).
"""

import os

import requests

BASE_URL = "https://api.adzuna.com/v1/api/jobs"


def search(query: str, limit: int = 20) -> list[dict]:
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return []

    country = os.environ.get("ADZUNA_COUNTRY", "se")
    url = f"{BASE_URL}/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": query,
        "results_per_page": min(limit, 50),
        "content-type": "application/json",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    results = []
    for item in data.get("results", []):
        company = (item.get("company") or {}).get("display_name", "")
        location = (item.get("location") or {}).get("display_name", "")

        results.append(
            {
                "source": "adzuna",
                "source_id": str(item.get("id", "")),
                "title": item.get("title", ""),
                "company": company,
                "location": location,
                "description": item.get("description", ""),
                "url": item.get("redirect_url", ""),
                "posted_at": item.get("created", ""),
            }
        )

    return results
