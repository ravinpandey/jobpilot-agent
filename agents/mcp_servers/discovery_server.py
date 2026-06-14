"""Search/Discovery agent: runs the deterministic job collector and
summarizes the results. Exposed as its own MCP server."""

from _agent_sdk import AgentOptions, create_sdk_mcp_server, tool

from agents import config
from agents.mcp_servers.pipeline_tools_server import PIPELINE_TOOLS_SERVER
from agents.prompts import DISCOVERY_SYSTEM_PROMPT
from agents.runner import parse_json_response, run_single_turn


def _text(payload: dict) -> dict:
    import json

    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


@tool(
    "run_discovery",
    "Run the job discovery pipeline for a user: collects new jobs from free job-board APIs based "
    "on their profile, persists/dedupes/scores them, and summarizes the results.",
    {"user_id": int},
)
async def run_discovery(args: dict) -> dict:
    opts = AgentOptions(
        system_prompt=DISCOVERY_SYSTEM_PROMPT,
        mcp_servers={"pipeline": PIPELINE_TOOLS_SERVER},
        allowed_tools=["mcp__pipeline__build_search_queries", "mcp__pipeline__collect_jobs_for_user"],
        model=config.DISCOVERY_MODEL,
        max_turns=4,
        **config.BASE_AGENT_KWARGS,
    )
    result = await run_single_turn(
        opts,
        f"user_id={args['user_id']}. Run discovery and summarize the results.",
    )

    parsed = parse_json_response(result["text"])
    parsed["_cost_usd"] = result["cost_usd"]
    return _text(parsed)


DISCOVERY_AGENT_SERVER = create_sdk_mcp_server(
    name="discovery-agent",
    version="1.0.0",
    tools=[run_discovery],
)
