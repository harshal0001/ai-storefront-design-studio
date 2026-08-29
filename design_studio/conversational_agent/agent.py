"""Core agent definition — shared between dev (FastAPI) and prod (AgentCore).

``create_agent()`` builds a Strands ``Agent`` with system prompt (``prompts/system_prompt.md``
+ blueprint), ``AGENT_TOOLS`` from ``tools.py``, optional AgentCore Memory hooks when
``merchant_id`` and ``session_id`` are provided, and merchant scoping so tools persist
to the right DynamoDB partition on stateless invocations.
"""

from __future__ import annotations

import logging
from typing import Any

from strands import Agent

from .agent_memory import build_memory_hooks
from .config import AGENT_MODEL, GREETING_PROMPT, build_model, load_system_prompt
from .shop_context import shop_context
from .tools import (
    generate_color_palette,
    validate_color_and_get_info,
    check_color_accessibility,
    get_harmony_types,
    get_available_fonts,
    validate_font,
    save_theme,
    apply_style_tokens,
    get_storefront_page_context,
    get_current_theme,
    list_zones,
    customize_zone,
    reset_zone,
    list_theme_packages,
    apply_theme_package,
    save_mood_tags,
    start_zone_tour,
    get_zone_tour_status,
    refresh_zone_tour_options,
    apply_zone_tour_choice,
    complete_zone_tour_step,
    skip_zone_tour_step,
    skip_zone_tour_sub_step,
    acknowledge_offers_zone,
)

logger = logging.getLogger(__name__)

# All tools available to the agent
# NOTE: reset_all deliberately excluded — available only via /api/reset (direct API).
# reset_zone requires confirmed=True (two-step) to prevent prompt-injection abuse.
AGENT_TOOLS = [
    generate_color_palette,
    validate_color_and_get_info,
    check_color_accessibility,
    get_harmony_types,
    get_available_fonts,
    validate_font,
    save_theme,
    apply_style_tokens,
    get_storefront_page_context,
    get_current_theme,
    list_zones,
    customize_zone,
    reset_zone,
    list_theme_packages,
    apply_theme_package,
    save_mood_tags,
    start_zone_tour,
    get_zone_tour_status,
    refresh_zone_tour_options,
    apply_zone_tour_choice,
    complete_zone_tour_step,
    skip_zone_tour_sub_step,
    skip_zone_tour_step,
    acknowledge_offers_zone,
]


class _MerchantScopedAgent:
    """Small proxy that binds tool calls to one merchant for each agent invocation."""

    def __init__(self, agent: Agent, merchant_id: str):
        self._agent = agent
        self._merchant_id = merchant_id

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        with shop_context(self._merchant_id):
            return self._agent(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._agent, name)


def create_agent(
    merchant_id: str | None = None,
    session_id: str | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
) -> Agent | _MerchantScopedAgent:
    """Create the storefront design agent.

    Args:
        merchant_id: Optional merchant scope for stateless runtimes and memory actor ID.
        session_id: Optional conversation session ID for AgentCore Memory events.
        model: Optional model override. Defaults to AGENT_MODEL from config.
        system_prompt: Optional prompt override. Defaults to prompts/system_prompt.md.

    Returns:
        Configured Strands Agent instance, optionally wrapped for merchant scoping.
    """
    hooks = []
    if merchant_id and session_id:
        memory_hooks = build_memory_hooks(merchant_id, session_id)
        if memory_hooks:
            hooks.append(memory_hooks)
            logger.info(
                "AgentCore Memory enabled for merchant=%s session=%s",
                merchant_id,
                session_id,
            )

    agent = Agent(
        model=model or build_model(),
        system_prompt=system_prompt or load_system_prompt(),
        hooks=hooks or None,
        tools=AGENT_TOOLS,
    )
    normalized_merchant_id = (merchant_id or "").strip()
    if normalized_merchant_id:
        return _MerchantScopedAgent(agent, normalized_merchant_id)
    return agent


# Re-export for convenience
__all__ = ["create_agent", "AGENT_MODEL", "GREETING_PROMPT", "AGENT_TOOLS"]
