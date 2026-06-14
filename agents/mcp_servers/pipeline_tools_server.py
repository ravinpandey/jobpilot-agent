"""In-process MCP server wrapping the existing deterministic pipeline.

Every tool here is a thin wrapper around app/*.py functions -- the
collector, TF-IDF/skill-overlap scoring, feedback/weight-learning, and resume
parsing logic are untouched. This is the shared "backend" that every
specialized agent connects to.
"""

import json

from _agent_sdk import create_sdk_mcp_server, tool

from app import schemas
from app.collector import collect_jobs
from app.db import Feedback, Job, Match, Profile, SessionLocal, init_db
from app.feedback import record_feedback as _record_feedback
from app.matcher import score_job
from app.pipeline import upsert_jobs_and_score
from app.resume_parser import parse_resume
from app.search_planner import build_queries

init_db()


def _text(payload: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


def _get_profile_or_error(db, user_id: int):
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        return None
    return profile


def _job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "source": job.source,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description,
        "url": job.url,
        "posted_at": job.posted_at,
        "dedupe_key": job.dedupe_key,
    }


@tool("get_profile", "Get a user's career profile (target roles, skills, preferences, resume text, skill weights).", {"user_id": int})
async def get_profile(args: dict) -> dict:
    db = SessionLocal()
    try:
        profile = _get_profile_or_error(db, args["user_id"])
        if not profile:
            return _text({"error": "profile not found"})
        data = schemas.ProfileOut.model_validate(profile).model_dump()
        data["resume_text"] = profile.resume_text or ""
        return _text(data)
    finally:
        db.close()


@tool(
    "update_profile",
    "Update fields on a user's profile. `fields_json` is a JSON object with any of: "
    "target_roles, domains, core_skills, avoid_skills, preferred_locations, "
    "preferred_companies, excluded_companies, min_salary, work_mode, seniority.",
    {"user_id": int, "fields_json": str},
)
async def update_profile(args: dict) -> dict:
    db = SessionLocal()
    try:
        profile = _get_profile_or_error(db, args["user_id"])
        if not profile:
            return _text({"error": "profile not found"})

        fields = json.loads(args["fields_json"])
        update = schemas.ProfileUpdate(**fields)
        for field, value in update.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)

        db.commit()
        db.refresh(profile)
        return _text(schemas.ProfileOut.model_validate(profile).model_dump())
    finally:
        db.close()


@tool("build_search_queries", "Generate the deterministic search query list for a user's profile (target roles x core skills).", {"user_id": int})
async def build_search_queries_tool(args: dict) -> dict:
    db = SessionLocal()
    try:
        profile = _get_profile_or_error(db, args["user_id"])
        if not profile:
            return _text({"error": "profile not found"})
        return _text({"queries": build_queries(profile)})
    finally:
        db.close()


@tool("collect_jobs_for_user", "Run the job collector across all free sources for a user's profile, persist new jobs, and score them. Returns the newly collected jobs with scores.", {"user_id": int})
async def collect_jobs_for_user(args: dict) -> dict:
    db = SessionLocal()
    try:
        profile = _get_profile_or_error(db, args["user_id"])
        if not profile:
            return _text({"error": "profile not found"})
        if not profile.target_roles:
            return _text({"error": "profile has no target_roles set"})

        collected = collect_jobs(profile)
        results = upsert_jobs_and_score(db, args["user_id"], profile, collected)

        return _text(
            {
                "new_jobs_count": len(results),
                "jobs": [
                    {
                        "job_id": job.id,
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "source": job.source,
                        "score": match.score,
                        "matched_skills": (match.score_breakdown or {}).get("matched_skills", []),
                    }
                    for job, match in results
                ],
            }
        )
    finally:
        db.close()


@tool(
    "score_jobs",
    "Re-score jobs for a user against their current profile (useful after profile changes). "
    "`job_ids_json` is a JSON array of job IDs; pass '[]' to re-score every job already matched for this user.",
    {"user_id": int, "job_ids_json": str},
)
async def score_jobs_tool(args: dict) -> dict:
    db = SessionLocal()
    try:
        profile = _get_profile_or_error(db, args["user_id"])
        if not profile:
            return _text({"error": "profile not found"})

        job_ids = json.loads(args["job_ids_json"])
        if job_ids:
            jobs = db.query(Job).filter(Job.id.in_(job_ids)).all()
        else:
            jobs = [m.job for m in db.query(Match).filter(Match.user_id == args["user_id"]).all()]

        output = []
        for job in jobs:
            score, breakdown = score_job(_job_to_dict(job), profile)
            match = db.query(Match).filter(Match.user_id == args["user_id"], Match.job_id == job.id).first()
            if match:
                match.score = score
                match.score_breakdown = breakdown
            else:
                match = Match(user_id=args["user_id"], job_id=job.id, score=score, score_breakdown=breakdown)
                db.add(match)
            db.commit()
            output.append({"job_id": job.id, "title": job.title, "company": job.company, "score": score, "breakdown": breakdown})

        return _text({"scored": output})
    finally:
        db.close()


@tool("list_ranked_jobs", "List a user's jobs ranked by score, optionally filtered by minimum score.", {"user_id": int, "min_score": float})
async def list_ranked_jobs(args: dict) -> dict:
    db = SessionLocal()
    try:
        matches = (
            db.query(Match)
            .filter(Match.user_id == args["user_id"], Match.score >= args["min_score"])
            .order_by(Match.score.desc())
            .all()
        )
        return _text(
            {
                "jobs": [
                    {
                        "job_id": m.job.id,
                        "title": m.job.title,
                        "company": m.job.company,
                        "location": m.job.location,
                        "url": m.job.url,
                        "score": m.score,
                        "breakdown": m.score_breakdown or {},
                    }
                    for m in matches
                ]
            }
        )
    finally:
        db.close()


@tool("get_job", "Get full details (including description) for a single job by ID.", {"job_id": int})
async def get_job(args: dict) -> dict:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == args["job_id"]).first()
        if not job:
            return _text({"error": "job not found"})
        return _text(_job_to_dict(job))
    finally:
        db.close()


@tool(
    "record_feedback",
    "Record feedback (applied/shortlisted/skip/rejected_salary/rejected_location/rejected) on a job for a user. "
    "This deterministically nudges skill weights (+/-0.1, clamped 0.1-3.0) for skills matched on that job.",
    {"user_id": int, "job_id": int, "status": str, "note": str},
)
async def record_feedback_tool(args: dict) -> dict:
    db = SessionLocal()
    try:
        feedback = _record_feedback(db, args["user_id"], args["job_id"], args["status"], args["note"] or None)
        return _text({"feedback_id": feedback.id})
    finally:
        db.close()


@tool("get_feedback_history", "Get a user's recent feedback history (status + notes) on jobs.", {"user_id": int, "limit": int})
async def get_feedback_history(args: dict) -> dict:
    db = SessionLocal()
    try:
        feedbacks = (
            db.query(Feedback)
            .filter(Feedback.user_id == args["user_id"])
            .order_by(Feedback.created_at.desc())
            .limit(args["limit"])
            .all()
        )
        return _text(
            {
                "feedback": [
                    {
                        "job_id": fb.job_id,
                        "job_title": db.get(Job, fb.job_id).title if fb.job_id else None,
                        "status": fb.status,
                        "note": fb.note,
                        "created_at": fb.created_at.isoformat() if fb.created_at else None,
                    }
                    for fb in feedbacks
                ]
            }
        )
    finally:
        db.close()


@tool("parse_resume_file", "Parse a resume file (PDF/text) on disk, extract skills, and merge into the user's profile.", {"user_id": int, "file_path": str})
async def parse_resume_file(args: dict) -> dict:
    db = SessionLocal()
    try:
        profile = _get_profile_or_error(db, args["user_id"])
        if not profile:
            return _text({"error": "profile not found"})

        parsed = parse_resume(args["file_path"])
        profile.resume_text = parsed["resume_text"]

        existing_skills = profile.core_skills or []
        merged_skills = list(existing_skills)
        for skill in parsed["extracted_skills"]:
            if skill not in merged_skills:
                merged_skills.append(skill)
        profile.core_skills = merged_skills

        db.commit()
        return _text({"extracted_skills": parsed["extracted_skills"], "core_skills": merged_skills})
    finally:
        db.close()


PIPELINE_TOOLS_SERVER = create_sdk_mcp_server(
    name="pipeline-tools",
    version="1.0.0",
    tools=[
        get_profile,
        update_profile,
        build_search_queries_tool,
        collect_jobs_for_user,
        score_jobs_tool,
        list_ranked_jobs,
        get_job,
        record_feedback_tool,
        get_feedback_history,
        parse_resume_file,
    ],
)
