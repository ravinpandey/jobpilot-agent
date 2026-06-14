"""Shared configuration for the agent layer.

Uses AWS Bedrock as the model provider (this EC2 instance already has IAM
access to Bedrock  models), so no separate ANTHROPIC_API_KEY is needed.
"""

import os

os.environ.setdefault("_CODE_USE_BEDROCK", "1")
os.environ.setdefault("AWS_REGION", "us-east-1")

HAIKU_MODEL = "us.anthropic.-haiku-4-5-20251001-v1:0"
SONNET_MODEL = "us.anthropic.-sonnet-4-5-20250929-v1:0"

# Simpler/structured tasks -> Haiku, more nuanced writing/reasoning -> Sonnet.
DISCOVERY_MODEL = HAIKU_MODEL
FEEDBACK_MODEL = HAIKU_MODEL
SCORING_MODEL = SONNET_MODEL
RESUME_MODEL = SONNET_MODEL
ORCHESTRATOR_MODEL = SONNET_MODEL

# Common options to strip the default  Code preset (full tool set,
# project settings/memory, etc.) so each agent only pays for its own
# system prompt + the tools it actually needs.
BASE_AGENT_KWARGS = {
    "setting_sources": [],
    "tools": [],
}
