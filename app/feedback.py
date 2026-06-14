"""Record user feedback on jobs and update skill weights in their profile."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import Feedback, Match, Profile

POSITIVE_STATUSES = {"applied", "shortlisted"}
NEGATIVE_STATUSES = {"skip", "rejected_salary", "rejected_location", "rejected"}

WEIGHT_STEP = 0.1
WEIGHT_MIN = 0.1
WEIGHT_MAX = 3.0
DEFAULT_WEIGHT = 1.0


def record_feedback(db: Session, user_id: int, job_id: int, status: str, note: str | None = None) -> Feedback:
    feedback = Feedback(user_id=user_id, job_id=job_id, status=status, note=note)
    db.add(feedback)

    _update_skill_weights(db, user_id, job_id, status)

    db.commit()
    db.refresh(feedback)
    return feedback


def _update_skill_weights(db: Session, user_id: int, job_id: int, status: str) -> None:
    if status not in POSITIVE_STATUSES and status not in NEGATIVE_STATUSES:
        return

    match = (
        db.query(Match)
        .filter(Match.user_id == user_id, Match.job_id == job_id)
        .order_by(Match.created_at.desc())
        .first()
    )
    if not match:
        return

    matched_skills = (match.score_breakdown or {}).get("matched_skills", [])
    if not matched_skills:
        return

    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        return

    weights = dict(profile.skill_weights or {})
    direction = 1 if status in POSITIVE_STATUSES else -1

    for skill in matched_skills:
        current = float(weights.get(skill, DEFAULT_WEIGHT))
        updated = current + direction * WEIGHT_STEP
        weights[skill] = max(WEIGHT_MIN, min(WEIGHT_MAX, round(updated, 3)))

    profile.skill_weights = weights
