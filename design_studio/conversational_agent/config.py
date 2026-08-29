"""Agent and environment configuration.

Loads prompts from ``prompts/``, exposes Bedrock model id, DynamoDB table names,
and feature flags. Source ``design_studio/example.env`` before running the dev server
so ``USE_DYNAMODB`` and ``DYNAMODB_ENDPOINT`` point at DynamoDB Local.
"""

import os
from pathlib import Path

# Model configuration
AGENT_MODEL = os.environ.get("AGENT_MODEL", "eu.amazon.nova-pro-v1:0")

# Bedrock Guardrail (set by the AgentCore runtime stack). When both are present the
# agent runs behind the guardrail; otherwise it falls back to the plain model id.
BEDROCK_GUARDRAIL_ID = os.environ.get("BEDROCK_GUARDRAIL_ID")
BEDROCK_GUARDRAIL_VERSION = os.environ.get("BEDROCK_GUARDRAIL_VERSION")


def build_model():
    """Return a guardrailed ``BedrockModel`` when configured, else the model-id string.

    Strands applies the guardrail only when both id and version are set, so an
    un-configured environment (local dev, tests) behaves exactly as before.
    """
    if BEDROCK_GUARDRAIL_ID and BEDROCK_GUARDRAIL_VERSION:
        from strands.models.bedrock import BedrockModel

        return BedrockModel(
            model_id=AGENT_MODEL,
            guardrail_id=BEDROCK_GUARDRAIL_ID,
            guardrail_version=BEDROCK_GUARDRAIL_VERSION,
            guardrail_trace="enabled",
        )
    return AGENT_MODEL


# Paths
CONFIG_DIR = Path(__file__).parent
PROMPTS_DIR = CONFIG_DIR / "prompts"

# Load system prompt from file
SYSTEM_PROMPT_FILE = PROMPTS_DIR / "system_prompt.md"
STOREFRONT_BLUEPRINT_FILE = PROMPTS_DIR / "storefront_blueprint.md"


def load_system_prompt() -> str:
    """Load system prompt plus storefront blueprint (layout, tokens, examples)."""
    if not SYSTEM_PROMPT_FILE.exists():
        raise FileNotFoundError(f"System prompt not found: {SYSTEM_PROMPT_FILE}")
    parts = [SYSTEM_PROMPT_FILE.read_text()]
    if STOREFRONT_BLUEPRINT_FILE.exists():
        parts.append("\n\n---\n\n")
        parts.append(STOREFRONT_BLUEPRINT_FILE.read_text())
    return "".join(parts)


# DynamoDB (local: http://127.0.0.1:8001 — see design_studio/docker-compose.yml)
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
DYNAMODB_STYLE_TABLE = os.environ.get("DYNAMODB_STYLE_TABLE", "StorefrontStyle")
DYNAMODB_THEME_PACKAGE_TABLE = os.environ.get("DYNAMODB_THEME_PACKAGE_TABLE", "ThemePackage")
DEFAULT_SHOP_UUID = os.environ.get("DEFAULT_SHOP_UUID", "demo-merchant")
USE_DYNAMODB = os.environ.get("USE_DYNAMODB", "true").lower() in ("1", "true", "yes")

# Greeting prompt for starting a new session
GREETING_PROMPT = (
    "A new merchant just opened the design studio. "
    "Greet them warmly and ask what their store/business is about. "
    "Don't ask about vibe yet — just learn about their business first."
)
