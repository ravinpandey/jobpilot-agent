"""Score a collected job posting against a user's career profile."""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.db import Profile

WEIGHTS = {
    "text_similarity": 0.30,
    "skill_overlap": 0.30,
    "location_match": 0.15,
    "domain_match": 0.10,
    "preferred_company": 0.10,
}
AVOID_PENALTY_WEIGHT = 0.25


def _profile_text(profile: Profile) -> str:
    parts = [
        " ".join(profile.target_roles or []),
        " ".join(profile.core_skills or []),
        " ".join(profile.domains or []),
        profile.resume_text or "",
    ]
    return " ".join(p for p in parts if p)


def _text_similarity(job: dict, profile: Profile) -> float:
    job_text = " ".join([job.get("title", ""), job.get("description", "")])
    profile_text = _profile_text(profile)

    if not job_text.strip() or not profile_text.strip():
        return 0.0

    vectorizer = TfidfVectorizer(stop_words="english", max_features=2000)
    try:
        tfidf = vectorizer.fit_transform([profile_text, job_text])
    except ValueError:
        # empty vocabulary (e.g. all stopwords)
        return 0.0

    sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
    return float(sim)


def _skill_overlap(job: dict, profile: Profile) -> tuple[float, list[str]]:
    core_skills = profile.core_skills or []
    if not core_skills:
        return 0.0, []

    weights = profile.skill_weights or {}
    job_text = " ".join([job.get("title", ""), job.get("description", "")]).lower()

    matched = []
    matched_weight = 0.0
    total_weight = 0.0
    for skill in core_skills:
        w = float(weights.get(skill, 1.0))
        total_weight += w
        if skill.lower() in job_text:
            matched.append(skill)
            matched_weight += w

    if total_weight == 0:
        return 0.0, matched
    return matched_weight / total_weight, matched


def _avoid_penalty(job: dict, profile: Profile) -> float:
    avoid_skills = profile.avoid_skills or []
    if not avoid_skills:
        return 0.0

    job_text = " ".join([job.get("title", ""), job.get("description", "")]).lower()
    hits = sum(1 for skill in avoid_skills if skill.lower() in job_text)
    return hits / len(avoid_skills)


def _location_match(job: dict, profile: Profile) -> float:
    job_location = (job.get("location") or "").lower()

    if (profile.work_mode or "").lower() == "remote" and "remote" in job_location:
        return 1.0

    preferred_locations = profile.preferred_locations or []
    for loc in preferred_locations:
        if loc.lower() in job_location:
            return 1.0

    return 0.0


def _domain_match(job: dict, profile: Profile) -> float:
    domains = profile.domains or []
    if not domains:
        return 0.0

    job_text = " ".join([job.get("title", ""), job.get("description", "")]).lower()
    hits = sum(1 for d in domains if d.lower() in job_text)
    return hits / len(domains)


def score_job(job: dict, profile: Profile) -> tuple[float, dict]:
    """Return (score 0-100, breakdown dict) for a job against a profile.

    Jobs at excluded companies are hard-zeroed.
    """
    company = (job.get("company") or "").strip().lower()
    excluded_companies = [c.lower() for c in (profile.excluded_companies or [])]
    if company and company in excluded_companies:
        return 0.0, {"excluded_company": True}

    text_similarity = _text_similarity(job, profile)
    skill_overlap, matched_skills = _skill_overlap(job, profile)
    avoid_penalty = _avoid_penalty(job, profile)
    location_match = _location_match(job, profile)
    domain_match = _domain_match(job, profile)

    preferred_companies = [c.lower() for c in (profile.preferred_companies or [])]
    preferred_company = 1.0 if company and company in preferred_companies else 0.0

    components = {
        "text_similarity": text_similarity,
        "skill_overlap": skill_overlap,
        "location_match": location_match,
        "domain_match": domain_match,
        "preferred_company": preferred_company,
    }

    raw = sum(WEIGHTS[k] * v for k, v in components.items())
    raw -= AVOID_PENALTY_WEIGHT * avoid_penalty
    raw = max(0.0, min(1.0, raw))

    breakdown = {k: round(v, 3) for k, v in components.items()}
    breakdown["avoid_penalty"] = round(avoid_penalty, 3)
    breakdown["matched_skills"] = matched_skills

    return round(raw * 100, 1), breakdown
