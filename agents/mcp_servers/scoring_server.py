"""Scoring/Ranking agent: explains existing deterministic job scores in
natural language. Exposed as its own MCP server so the orchestrator (or any
other agent) can call it as a tool."""

import json

from _agent_sdk import AgentOptions, create_sdk_mcp_server, tool

from agents import config
from agents.mcp_servers.pipeline_tools_server import PIPELINE_TOOLS_SERVER
from agents.prompts import SCORING_SYSTEM_PROMPT
from agents.runner import parse_json_response, run_single_turn


def _text(payload: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


@tool(
    "score_and_explain",
    "Get a user's jobs ranked by score with natural-language explanations of why each scored as it did. "
    "Does not change the underlying deterministic scores.",
    {"user_id": int, "min_score": float},
)
async def score_and_explain(args: dict) -> dict:
    opts = AgentOptions(
        system_prompt=SCORING_SYSTEM_PROMPT,
        mcp_servers={"pipeline": PIPELINE_TOOLS_SERVER},
        allowed_tools=["mcp__pipeline__list_ranked_jobs"],
        model=config.SCORING_MODEL,
        max_turns=4,
        **config.BASE_AGENT_KWARGS,
    )
    result = await run_single_turn(
        opts,
        f"user_id={args['user_id']}, min_score={args['min_score']}. "
        f"Call list_ranked_jobs and explain the top results.",
    )

    parsed = parse_json_response(result["text"])
    parsed["_cost_usd"] = result["cost_usd"]
    return _text(parsed)


SCORING_AGENT_SERVER = create_sdk_mcp_server(
    name="scoring-agent",
    version="1.0.0",
    tools=[score_and_explain],
)
