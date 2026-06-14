"""Shared pipeline helpers used by both the REST API and the agent MCP tools."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import Job, Match, Profile
from app.matcher import score_job


def upsert_jobs_and_score(db: Session, user_id: int, profile: Profile, collected_jobs: list[dict]) -> list[tuple[Job, Match]]:
    """Persist newly collected jobs and (re)score them for this user.

    Returns (job, match) pairs sorted by score, descending.
    """
    results = []
    for job_data in collected_jobs:
        job = db.query(Job).filter(Job.dedupe_key == job_data["dedupe_key"]).first()
        if not job:
            job = Job(**job_data)
            db.add(job)
            db.commit()
            db.refresh(job)

        score, breakdown = score_job(job_data, profile)

        match = db.query(Match).filter(Match.user_id == user_id, Match.job_id == job.id).first()
        if match:
            match.score = score
            match.score_breakdown = breakdown
        else:
            match = Match(user_id=user_id, job_id=job.id, score=score, score_breakdown=breakdown)
            db.add(match)
        db.commit()

        results.append((job, match))

    results.sort(key=lambda pair: pair[1].score, reverse=True)
    return results
