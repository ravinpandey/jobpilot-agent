"""Arbeitnow public job board feed (https://www.arbeitnow.com/api/job-board-api).

No API key required, EU-focused (mostly Germany/remote-Europe). The endpoint
doesn't support free-text search, so we fetch a couple of pages and filter
client-side by the query keywords (same approach as RemoteOK/The Muse).
"""

import requests

API_URL = "https://www.arbeitnow.com/api/job-board-api"
HEADERS = {"User-Agent": "job-agent-mvp/0.1 (personal job search assistant)"}
PAGES_TO_FETCH = 2


def search(query: str, limit: int = 20) -> list[dict]:
    query_terms = [t.lower() for t in query.split() if t]

    results = []
    for page in range(1, PAGES_TO_FETCH + 1):
        try:
            resp = requests.get(API_URL, headers=HEADERS, params={"page": page}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError):
            continue

        for job in data.get("data", []):
            title = job.get("title", "")
            description = job.get("description", "")
            haystack = f"{title} {description}".lower()

            if query_terms and not all(term in haystack for term in query_terms):
                continue

            results.append(
                {
                    "source": "arbeitnow",
                    "source_id": job.get("slug", ""),
                    "title": title,
                    "company": job.get("company_name", ""),
                    "location": job.get("location", "") or ("Remote" if job.get("remote") else ""),
                    "description": description,
                    "url": job.get("url", ""),
                    "posted_at": str(job.get("created_at", "")),
                }
            )
            if len(results) >= limit:
                return results

    return results
