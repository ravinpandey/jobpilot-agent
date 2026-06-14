"""FastAPI router for the agent layer (chat + direct agent triggers)."""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/agents", tags=["agents"])


class ChatRequest(BaseModel):
    user_id: int
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: Optional[str] = None
    cost_usd: float = 0.0


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    from agents.orchestrator import run_chat_turn

    result = await run_chat_turn(payload.user_id, payload.message, payload.session_id)
    return ChatResponse(**result)


@router.post("/discovery/{user_id}")
async def run_discovery_endpoint(user_id: int):
    import json

    from agents.mcp_servers.discovery_server import run_discovery

    result = await run_discovery.handler({"user_id": user_id})
    return json.loads(result["content"][0]["text"])


@router.post("/score/{user_id}")
async def score_and_explain_endpoint(user_id: int, min_score: float = 0):
    import json

    from agents.mcp_servers.scoring_server import score_and_explain

    result = await score_and_explain.handler({"user_id": user_id, "min_score": min_score})
    return json.loads(result["content"][0]["text"])


class TailorResumeRequest(BaseModel):
    instructions: str = ""


@router.post("/tailor-resume/{user_id}/{job_id}")
async def tailor_resume_endpoint(user_id: int, job_id: int, payload: TailorResumeRequest = TailorResumeRequest()):
    import json

    from agents.mcp_servers.resume_server import tailor_resume

    result = await tailor_resume.handler(
        {"user_id": user_id, "job_id": job_id, "instructions": payload.instructions}
    )
    return json.loads(result["content"][0]["text"])


@router.get("/tailored-resume/{user_id}/{job_id}")
async def download_tailored_resume(user_id: int, job_id: int):
    from agents.resume_builder import OUTPUT_DIR

    path = os.path.join(OUTPUT_DIR, f"{user_id}_{job_id}.docx")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Tailored resume not found. Generate it first.")
    return FileResponse(path, filename=f"resume_{user_id}_{job_id}.docx")


@router.post("/feedback/{user_id}/{job_id}")
async def process_feedback_endpoint(user_id: int, job_id: int, status: str, note: str = ""):
    import json

    from agents.mcp_servers.feedback_server import process_feedback

    result = await process_feedback.handler({"user_id": user_id, "job_id": job_id, "status": status, "note": note})
    return json.loads(result["content"][0]["text"])
