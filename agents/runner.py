"""Shared helper for running a single-turn  Agent SDK query and
collecting its final text response + cost."""

import json
import re

from _agent_sdk import AssistantMessage, SDKClient, ResultMessage, TextBlock

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_json_response(text: str) -> dict:
    """Parse a JSON object from agent output, tolerating leading/trailing prose
    and ```json fences anywhere in the text."""
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        pass

    match = _FENCE_RE.search(stripped)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except (json.JSONDecodeError, TypeError):
            pass

    start, end = stripped.find("{"), stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except (json.JSONDecodeError, TypeError):
            pass

    return {"raw": text}


async def run_single_turn(options, prompt: str) -> dict:
    """Run one user turn against an agent and return its final text reply + cost."""
    final_text_parts: list[str] = []
    cost_usd = 0.0

    async with SDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        final_text_parts.append(block.text)
            elif isinstance(msg, ResultMessage):
                cost_usd = msg.total_cost_usd or 0.0

    return {"text": "\n".join(final_text_parts), "cost_usd": cost_usd}
