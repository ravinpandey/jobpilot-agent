"""Feedback/Learning agent: records feedback (deterministic skill-weight
update) and analyzes free-text notes for profile-adjustment suggestions.
Exposed as its own MCP server."""

import json

from _agent_sdk import AgentOptions, create_sdk_mcp_server, tool

from agents import config
from agents.mcp_servers.pipeline_tools_server import PIPELINE_TOOLS_SERVER
from agents.prompts import FEEDBACK_SYSTEM_PROMPT
from agents.runner import parse_json_response, run_single_turn


def _text(payload: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


@tool(
    "process_feedback",
    "Record feedback on a job (applied/shortlisted/skip/rejected_salary/rejected_location/rejected) "
    "for a user, and suggest profile adjustments based on any free-text note.",
    {"user_id": int, "job_id": int, "status": str, "note": str},
)
async def process_feedback(args: dict) -> dict:
    opts = AgentOptions(
        system_prompt=FEEDBACK_SYSTEM_PROMPT,
        mcp_servers={"pipeline": PIPELINE_TOOLS_SERVER},
        allowed_tools=["mcp__pipeline__record_feedback"],
        model=config.FEEDBACK_MODEL,
        max_turns=4,
        **config.BASE_AGENT_KWARGS,
    )
    result = await run_single_turn(
        opts,
        f"user_id={args['user_id']}, job_id={args['job_id']}, status={args['status']!r}, "
        f"note={args['note']!r}. Record this feedback and suggest any profile adjustments.",
    )

    parsed = parse_json_response(result["text"])
    parsed["_cost_usd"] = result["cost_usd"]
    return _text(parsed)


FEEDBACK_AGENT_SERVER = create_sdk_mcp_server(
    name="feedback-agent",
    version="1.0.0",
    tools=[process_feedback],
)
