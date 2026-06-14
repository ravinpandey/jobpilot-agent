"""Swedish public employment service job feed (JobTech / Arbetsformedlingen).

Public API, no key required: https://jobsearch.api.jobtechdev.se/search
"""

import requests

API_URL = "https://jobsearch.api.jobtechdev.se/search"
HEADERS = {"accept": "application/json", "User-Agent": "job-agent-mvp/0.1"}


def search(query: str, limit: int = 20) -> list[dict]:
    params = {"q": query, "limit": min(limit, 100)}
    try:
        resp = requests.get(API_URL, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    results = []
    for hit in data.get("hits", []):
        employer = hit.get("employer") or {}
        address = hit.get("workplace_address") or {}
        description = hit.get("description") or {}

        location_parts = [p for p in [address.get("municipality"), address.get("region")] if p]
        location = ", ".join(location_parts) or "Sweden"

        results.append(
            {
                "source": "jobtech_se",
                "source_id": str(hit.get("id", "")),
                "title": hit.get("headline", ""),
                "company": employer.get("name", ""),
                "location": location,
                "description": description.get("text", ""),
                "url": hit.get("webpage_url", ""),
                "posted_at": hit.get("publication_date", ""),
            }
        )

    return results
