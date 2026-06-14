"""Deduplication helpers for collected job postings."""

import hashlib
import re


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def dedupe_key(job: dict) -> str:
    """Stable key based on URL if present, else title+company+location."""
    url = _normalize(job.get("url", ""))
    if url:
        basis = url
    else:
        basis = "|".join(
            [_normalize(job.get("title", "")), _normalize(job.get("company", "")), _normalize(job.get("location", ""))]
        )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def dedupe_jobs(jobs: list[dict]) -> list[dict]:
    """Remove duplicates within a single batch, keeping first occurrence."""
    seen = set()
    unique = []
    for job in jobs:
        key = dedupe_key(job)
        if key in seen:
            continue
        seen.add(key)
        job["dedupe_key"] = key
        unique.append(job)
    return unique
