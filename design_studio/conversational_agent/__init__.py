"""Storefront Design Agent — conversational theme customisation for merchants.

This package combines a Strands/Bedrock agent with deterministic server-side handlers
(colour science, zone tour, direct style parsing) and DynamoDB-backed style persistence.

Layout (high level):
  agent.py, tools.py     — LLM tools and Strands agent definition
  server.py              — FastAPI dev API (local only; not deployed to prod)
  runtime.py             — AgentCore Lambda-style handler (production)
  chat_fast_path.py      — Server-side edits without Bedrock (tour clicks, NL phrases)
  api_response.py        — Preview HTML payloads + zone tour enrichment for the UI
  preview_html.py        — Inject tokens and highlight scripts into storefront.html
  config_manager.py      — Merchant style read/write (DDB or JSON fallback)
  style_repository.py  — Low-level DynamoDB access (StorefrontStyle)
  style_tokens.py        — Canonical token schema (matches DDB_Schema.md)
  zone_tour*.py          — CF-05 guided walkthrough Z1–Z6
  section_focus.py       — Section/element focus for scoped chat edits
"""

from .models import StorefrontConfig, Zone
from .config_manager import ConfigManager
from .color_engine import (
    generate_palette_from_seed,
    is_valid_color,
    is_hex_format,
    validate_hex,
    is_valid_google_font,
)
from .agent import create_agent, AGENT_TOOLS
from .config import AGENT_MODEL, GREETING_PROMPT, load_system_prompt
from .response_models import AgentResponse, VibeOption, ThemePackage, ColorOption

__all__ = [
    # Core
    "create_agent",
    "AGENT_MODEL",
    "AGENT_TOOLS",
    "GREETING_PROMPT",
    "load_system_prompt",
    # Response models
    "AgentResponse",
    "VibeOption",
    "ThemePackage",
    "ColorOption",
    # Config
    "StorefrontConfig",
    "Zone",
    "ConfigManager",
    # Color utilities
    "generate_palette_from_seed",
    "is_valid_color",
    "is_hex_format",
    "validate_hex",
    "is_valid_google_font",
]
