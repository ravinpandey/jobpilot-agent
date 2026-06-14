"""Top-level orchestrator: a chat agent that routes user requests to the
4 specialized agents (each its own MCP server) and replies conversationally."""

from _agent_sdk import AssistantMessage, AgentOptions, SDKClient, ResultMessage, TextBlock

from agents import config
from agents.mcp_servers.discovery_server import DISCOVERY_AGENT_SERVER
from agents.mcp_servers.feedback_server import FEEDBACK_AGENT_SERVER
from agents.mcp_servers.resume_server import RESUME_AGENT_SERVER
from agents.mcp_servers.scoring_server import SCORING_AGENT_SERVER
from agents.prompts import ORCHESTRATOR_SYSTEM_PROMPT

ALLOWED_TOOLS = [
    "mcp__discovery__run_discovery",
    "mcp__scoring__score_and_explain",
    "mcp__resume__tailor_resume",
    "mcp__feedback__process_feedback",
]


async def run_chat_turn(user_id: int, message: str, session_id: str | None = None) -> dict:
    opts = AgentOptions(
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        mcp_servers={
            "discovery": DISCOVERY_AGENT_SERVER,
            "scoring": SCORING_AGENT_SERVER,
            "resume": RESUME_AGENT_SERVER,
            "feedback": FEEDBACK_AGENT_SERVER,
        },
        allowed_tools=ALLOWED_TOOLS,
        model=config.ORCHESTRATOR_MODEL,
        max_turns=8,
        resume=session_id,
        **config.BASE_AGENT_KWARGS,
    )

    final_text_parts: list[str] = []
    cost_usd = 0.0
    new_session_id = session_id

    async with SDKClient(options=opts) as client:
        await client.query(f"[user_id={user_id}] {message}")
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        final_text_parts.append(block.text)
            elif isinstance(msg, ResultMessage):
                cost_usd = msg.total_cost_usd or 0.0
                new_session_id = msg.session_id

    return {"reply": "\n".join(final_text_parts), "session_id": new_session_id, "cost_usd": cost_usd}
