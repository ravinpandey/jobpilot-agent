"""The Muse public job feed (https://www.themuse.com/api/public/jobs).

No API key required. The endpoint doesn't support free-text search, so we
fetch a couple of pages and filter client-side by the query keywords
(same approach as the RemoteOK source).
"""

import requests

API_URL = "https://www.themuse.com/api/public/jobs"
HEADERS = {"User-Agent": "job-agent-mvp/0.1 (personal job search assistant)"}
PAGES_TO_FETCH = 2


def search(query: str, limit: int = 20) -> list[dict]:
    query_terms = [t.lower() for t in query.split() if t]

    results = []
    for page in range(PAGES_TO_FETCH):
        try:
            resp = requests.get(API_URL, headers=HEADERS, params={"page": page}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError):
            continue

        for job in data.get("results", []):
            title = job.get("name", "")
            contents = job.get("contents", "")
            haystack = f"{title} {contents}".lower()

            if query_terms and not all(term in haystack for term in query_terms):
                continue

            company = (job.get("company") or {}).get("name", "")
            locations = job.get("locations") or []
            location = ", ".join(loc.get("name", "") for loc in locations) or "Remote"

            results.append(
                {
                    "source": "themuse",
                    "source_id": str(job.get("id", "")),
                    "title": title,
                    "company": company,
                    "location": location,
                    "description": contents,
                    "url": job.get("refs", {}).get("landing_page", ""),
                    "posted_at": job.get("publication_date", ""),
                }
            )
            if len(results) >= limit:
                return results

    return results
