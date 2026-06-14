"""Run searches across all configured job sources for a given profile."""

from app.db import Profile
from app.dedupe import dedupe_jobs
from app.search_planner import build_queries
from app.sources import adzuna, arbeitnow, company_boards, jobicy, jobtech_se, remoteok, themuse

# Each source is tried for every generated query. Sources that fail
# (network errors, rate limits, missing API keys) are skipped silently.
# adzuna is included but requires an API key (ADZUNA_APP_ID/ADZUNA_APP_KEY);
# without it, adzuna.search() returns [] and is effectively a no-op.
QUERY_SOURCES = [
    remoteok.search,
    jobtech_se.search,
    themuse.search,
    jobicy.search,
    arbeitnow.search,
    adzuna.search,
]

MAX_QUERIES = 6
RESULTS_PER_QUERY = 15


def collect_jobs(profile: Profile) -> list[dict]:
    queries = build_queries(profile)[:MAX_QUERIES]

    all_jobs: list[dict] = []
    for query in queries:
        for source_search in QUERY_SOURCES:
            try:
                all_jobs.extend(source_search(query, limit=RESULTS_PER_QUERY))
            except Exception:
                # never let one bad source break the whole search
                continue

    if profile.preferred_companies:
        try:
            all_jobs.extend(company_boards.search(profile.preferred_companies, limit=RESULTS_PER_QUERY))
        except Exception:
            pass

    return dedupe_jobs(all_jobs)
