"""Jobicy public remote-jobs feed (https://jobicy.com/api/v2/remote-jobs).

No API key required. Supports a free-text "tag" parameter, which we set to
the search query.
"""

import requests

API_URL = "https://jobicy.com/api/v2/remote-jobs"
HEADERS = {"User-Agent": "job-agent-mvp/0.1 (personal job search assistant)"}


def search(query: str, limit: int = 20) -> list[dict]:
    params = {"count": min(limit, 50), "tag": query}
    try:
        resp = requests.get(API_URL, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    results = []
    for job in data.get("jobs", []):
        results.append(
            {
                "source": "jobicy",
                "source_id": str(job.get("id", "")),
                "title": job.get("jobTitle", ""),
                "company": job.get("companyName", ""),
                "location": job.get("jobGeo", "Remote") or "Remote",
                "description": job.get("jobDescription") or job.get("jobExcerpt", ""),
                "url": job.get("url", ""),
                "posted_at": job.get("pubDate", ""),
            }
        )

    return results
