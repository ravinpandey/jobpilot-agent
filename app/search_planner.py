"""Generate job search queries from a user's career profile."""

from app.db import Profile

MAX_SKILL_COMBOS_PER_ROLE = 2


def build_queries(profile: Profile) -> list[str]:
    """Combine target roles with top core skills to form search queries.

    Example:
        target_roles = ["GenAI Architect", "AI/ML Lead"]
        core_skills  = ["RAG", "AWS", "FastAPI"]

        -> ["GenAI Architect", "GenAI Architect RAG", "GenAI Architect AWS",
            "AI/ML Lead", "AI/ML Lead RAG", "AI/ML Lead AWS"]
    """
    target_roles = profile.target_roles or []
    core_skills = profile.core_skills or []

    queries: list[str] = []
    for role in target_roles:
        queries.append(role)
        for skill in core_skills[:MAX_SKILL_COMBOS_PER_ROLE]:
            queries.append(f"{role} {skill}")

    # de-duplicate while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        key = q.lower().strip()
        if key not in seen:
            seen.add(key)
            unique_queries.append(q)
    return unique_queries
