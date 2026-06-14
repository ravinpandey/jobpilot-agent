"""Resume Tailoring agent: rewrites a user's resume to emphasize the parts
relevant to a target job, then renders it as a .docx. Exposed as its own MCP
server."""

import json

from _agent_sdk import AgentOptions, create_sdk_mcp_server, tool

from agents import config
from agents.mcp_servers.pipeline_tools_server import PIPELINE_TOOLS_SERVER
from agents.prompts import RESUME_SYSTEM_PROMPT
from agents.resume_builder import build_docx
from agents.runner import parse_json_response, run_single_turn


def _text(payload: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


@tool(
    "tailor_resume",
    "Generate a tailored resume (.docx) for a user, emphasizing the parts of their resume "
    "relevant to a specific job. Truthful-only: never invents experience or skills. "
    "Optionally accepts free-text `instructions` for specific changes the user wants.",
    {"user_id": int, "job_id": int, "instructions": str},
)
async def tailor_resume(args: dict) -> dict:
    opts = AgentOptions(
        system_prompt=RESUME_SYSTEM_PROMPT,
        mcp_servers={"pipeline": PIPELINE_TOOLS_SERVER},
        allowed_tools=["mcp__pipeline__get_profile", "mcp__pipeline__get_job"],
        model=config.RESUME_MODEL,
        max_turns=6,
        **config.BASE_AGENT_KWARGS,
    )

    prompt = (
        f"user_id={args['user_id']}, job_id={args['job_id']}. "
        f"Fetch the profile and job, then produce the tailored resume JSON."
    )
    instructions = (args.get("instructions") or "").strip()
    if instructions:
        prompt += f"\n\nUser's specific instructions for this tailoring: {instructions}"

    result = await run_single_turn(opts, prompt)

    parsed = parse_json_response(result["text"])
    if "raw" in parsed:
        parsed["_cost_usd"] = result["cost_usd"]
        return _text(parsed)

    docx_path = build_docx(parsed, args["user_id"], args["job_id"])
    return _text(
        {
            "tailored_resume_path": docx_path,
            "summary_of_changes": parsed.get("summary_of_changes", ""),
            "preview": parsed,
            "_cost_usd": result["cost_usd"],
        }
    )


RESUME_AGENT_SERVER = create_sdk_mcp_server(
    name="resume-agent",
    version="1.0.0",
    tools=[tailor_resume],
)
