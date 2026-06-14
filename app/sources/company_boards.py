"""Direct company job boards (Greenhouse / Lever) for a user's preferred companies.

Both Greenhouse and Lever expose free, public, unauthenticated APIs per
company "board token". We guess the board token from the company name
(lowercased, non-alphanumeric stripped) — if a company doesn't use that
ATS or the token guess is wrong, the request 404s and is skipped silently.
"""

import re

import requests

HEADERS = {"User-Agent": "job-agent-mvp/0.1 (personal job search assistant)"}
GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/{token}?mode=json"


def _board_token(company: str) -> str:
    return re.sub(r"[^a-z0-9]", "", company.lower())


def _greenhouse_jobs(company: str, token: str, limit: int) -> list[dict]:
    try:
        resp = requests.get(
            GREENHOUSE_URL.format(token=token), headers=HEADERS, params={"content": "true"}, timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    results = []
    for job in data.get("jobs", [])[:limit]:
        results.append(
            {
                "source": "greenhouse",
                "source_id": str(job.get("id", "")),
                "title": job.get("title", ""),
                "company": company,
                "location": (job.get("location") or {}).get("name", ""),
                "description": job.get("content", ""),
                "url": job.get("absolute_url", ""),
                "posted_at": job.get("updated_at", ""),
            }
        )
    return results


def _lever_jobs(company: str, token: str, limit: int) -> list[dict]:
    try:
        resp = requests.get(LEVER_URL.format(token=token), headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    if not isinstance(data, list):
        return []

    results = []
    for job in data[:limit]:
        categories = job.get("categories") or {}
        results.append(
            {
                "source": "lever",
                "source_id": str(job.get("id", "")),
                "title": job.get("text", ""),
                "company": company,
                "location": categories.get("location", ""),
                "description": job.get("descriptionPlain", ""),
                "url": job.get("hostedUrl", ""),
                "posted_at": str(job.get("createdAt", "")),
            }
        )
    return results


def search(companies: list[str], limit: int = 20) -> list[dict]:
    results = []
    for company in companies:
        token = _board_token(company)
        if not token:
            continue
        results.extend(_greenhouse_jobs(company, token, limit))
        results.extend(_lever_jobs(company, token, limit))
    return results
