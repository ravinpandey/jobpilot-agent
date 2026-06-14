"""RemoteOK public job feed (https://remoteok.com/api).

No API key required. Returns remote jobs only. We fetch the full feed once
and filter client-side by the query keywords, since RemoteOK's API does not
support server-side search.
"""

import requests

API_URL = "https://remoteok.com/api"
HEADERS = {"User-Agent": "job-agent-mvp/0.1 (personal job search assistant)"}


def search(query: str, limit: int = 20) -> list[dict]:
    try:
        resp = requests.get(API_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    if not isinstance(data, list) or len(data) < 2:
        return []

    # data[0] is a legal/metadata blob, real jobs start at index 1
    jobs = data[1:]
    query_terms = [t.lower() for t in query.split() if t]

    results = []
    for job in jobs:
        haystack = " ".join(
            [
                str(job.get("position", "")),
                str(job.get("description", "")),
                " ".join(job.get("tags", []) or []),
            ]
        ).lower()

        if query_terms and not all(term in haystack for term in query_terms):
            continue

        results.append(
            {
                "source": "remoteok",
                "source_id": str(job.get("id", "")),
                "title": job.get("position", ""),
                "company": job.get("company", ""),
                "location": job.get("location", "Remote") or "Remote",
                "description": job.get("description", ""),
                "url": job.get("url", ""),
                "posted_at": job.get("date", ""),
            }
        )
        if len(results) >= limit:
            break

    return results
