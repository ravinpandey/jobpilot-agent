import os
import shutil
import uuid

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import schemas
from app.agents_api import router as agents_router
from app.collector import collect_jobs
from app.db import Feedback, Job, Match, Profile, User, get_db, init_db
from app.feedback import record_feedback
from app.pipeline import upsert_jobs_and_score
from app.resume_parser import parse_resume

RESUME_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "resumes")
os.makedirs(RESUME_DIR, exist_ok=True)

app = FastAPI(title="Job Agent MVP")
app.include_router(agents_router)


@app.on_event("startup")
def on_startup():
    init_db()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.post("/users", response_model=schemas.UserOut)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    user = User(name=payload.name, email=payload.email)
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = Profile(user_id=user.id)
    db.add(profile)
    db.commit()

    return user


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def _get_profile(db: Session, user_id: int) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="User/profile not found")
    return profile


@app.get("/users/{user_id}/profile", response_model=schemas.ProfileOut)
def get_profile(user_id: int, db: Session = Depends(get_db)):
    return _get_profile(db, user_id)


@app.put("/users/{user_id}/profile", response_model=schemas.ProfileOut)
def update_profile(user_id: int, payload: schemas.ProfileUpdate, db: Session = Depends(get_db)):
    profile = _get_profile(db, user_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile


@app.post("/users/{user_id}/resume", response_model=schemas.ProfileOut)
def upload_resume(user_id: int, file: UploadFile, db: Session = Depends(get_db)):
    profile = _get_profile(db, user_id)

    ext = os.path.splitext(file.filename or "")[1] or ".pdf"
    dest_path = os.path.join(RESUME_DIR, f"{user_id}_{uuid.uuid4().hex}{ext}")
    with open(dest_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    parsed = parse_resume(dest_path)

    profile.resume_text = parsed["resume_text"]

    existing_skills = profile.core_skills or []
    merged_skills = list(existing_skills)
    for skill in parsed["extracted_skills"]:
        if skill not in merged_skills:
            merged_skills.append(skill)
    profile.core_skills = merged_skills

    db.commit()
    db.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# Job search / matching
# ---------------------------------------------------------------------------

@app.post("/users/{user_id}/search", response_model=list[schemas.JobOut])
def run_search(user_id: int, db: Session = Depends(get_db)):
    profile = _get_profile(db, user_id)

    if not profile.target_roles:
        raise HTTPException(status_code=400, detail="Set target_roles in your profile before searching")

    collected = collect_jobs(profile)
    results = upsert_jobs_and_score(db, user_id, profile, collected)
    return _to_job_out(db, results, user_id)


@app.get("/users/{user_id}/jobs", response_model=list[schemas.JobOut])
def list_jobs(user_id: int, min_score: float = 0, db: Session = Depends(get_db)):
    _get_profile(db, user_id)

    matches = (
        db.query(Match)
        .filter(Match.user_id == user_id, Match.score >= min_score)
        .order_by(Match.score.desc())
        .all()
    )
    pairs = [(m.job, m) for m in matches]
    return _to_job_out(db, pairs, user_id)


def _to_job_out(db: Session, pairs, user_id: int) -> list[schemas.JobOut]:
    job_ids = [job.id for job, _ in pairs]
    feedback_by_job = {}
    if job_ids:
        feedbacks = (
            db.query(Feedback)
            .filter(Feedback.user_id == user_id, Feedback.job_id.in_(job_ids))
            .order_by(Feedback.created_at.desc())
            .all()
        )
        for fb in feedbacks:
            feedback_by_job.setdefault(fb.job_id, fb.status)

    output = []
    for job, match in pairs:
        output.append(
            schemas.JobOut(
                id=job.id,
                source=job.source,
                title=job.title,
                company=job.company,
                location=job.location,
                url=job.url,
                posted_at=job.posted_at,
                score=match.score,
                score_breakdown=match.score_breakdown or {},
                feedback_status=feedback_by_job.get(job.id),
            )
        )
    return output


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

@app.post("/users/{user_id}/jobs/{job_id}/feedback")
def give_feedback(user_id: int, job_id: int, payload: schemas.FeedbackIn, db: Session = Depends(get_db)):
    _get_profile(db, user_id)

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    valid_statuses = {"applied", "shortlisted", "skip", "rejected_salary", "rejected_location", "rejected"}
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(valid_statuses)}")

    feedback = record_feedback(db, user_id, job_id, payload.status, payload.note)
    return {"ok": True, "feedback_id": feedback.id}
