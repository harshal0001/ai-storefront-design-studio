"""AgentCore runtime entrypoint for production deployment.

Thin wrapper: ``invoke()`` / ``handler()`` call the Strands agent with ``shop_context``
and return structured JSON (message, vibe/theme/color options).

**Gap vs dev server:** No ``chat_fast_path``, no preview HTML, no zone-tour enrichment.
Prod needs an API layer (see ``cdk/NEXT_STEPS.md``). ``session_id`` is passed to
AgentCore Memory hooks for conversation persistence.

Deploy: ``bedrock-agentcore deploy`` · Test: ``python -m conversational_agent.runtime``
"""

from .agent import create_agent
from .agent_memory import memory_persist_context
from .config import GREETING_PROMPT
from .observability import MetricUnit, logger, metrics
from .palette_diversifier import diversify_theme_packages
from .response_models import AgentResponse
from .shop_context import shop_context


def _require_merchant_id(merchant_id: str | None) -> str:
    """AgentCore is stateless; every invoke must carry its tenant key."""
    normalized = (merchant_id or "").strip()
    if not normalized:
        raise ValueError("merchant_id is required for AgentCore runtime invocations")
    return normalized


def _require_session_id(session_id: str | None) -> str:
    """Memory events are scoped per conversation; callers must supply a session ID."""
    normalized = (session_id or "").strip()
    if not normalized:
        raise ValueError("session_id is required for AgentCore runtime invocations")
    return normalized


def invoke(
    message: str,
    session_id: str | None = None,
    merchant_id: str | None = None,
) -> dict:
    """Invoke the agent with a message.

    This is the main entry point for AgentCore invocations.

    Args:
        message: The user's message.
        session_id: Required per-conversation session ID for AgentCore Memory events.
        merchant_id: Required merchant ID from the trusted Lambda/API layer.

    Returns:
        Dictionary with response data including message, type, and any structured options.
    """
    shop_uuid = _require_merchant_id(merchant_id)
    logger.append_keys(merchant_id=shop_uuid, session_id=session_id or "unknown")

    memory_session_id = _require_session_id(session_id)
    agent = create_agent(merchant_id=shop_uuid, session_id=memory_session_id)

    is_greeting = not message or not message.strip()
    invoke_message = GREETING_PROMPT if is_greeting else message

    logger.info("Agent invocation started", message_length=len(message))

    # Invoke with structured output (tools read shop_uuid from context)
    with shop_context(shop_uuid):
        with memory_persist_context(
            merchant_message=None if is_greeting else message.strip(),
            enabled=not is_greeting,
        ):
            result = agent(invoke_message, structured_output_model=AgentResponse)
    response: AgentResponse = result.structured_output

    metrics.add_metric(name="AgentInvocation", unit=MetricUnit.Count, value=1)

    # Build response dict
    resp = {
        "message": response.message,
        "type": response.response_type,
    }

    # Include structured options if present
    if response.vibe_options:
        resp["vibe_options"] = [opt.model_dump() for opt in response.vibe_options]
    if response.theme_packages:
        packages = [pkg.model_dump() for pkg in response.theme_packages]
        resp["theme_packages"] = diversify_theme_packages(packages)
    if response.color_options:
        resp["color_options"] = [opt.model_dump() for opt in response.color_options]

    logger.info("Agent invocation completed", response_type=response.response_type)
    return resp


# AgentCore handler - this is what AgentCore calls
def handler(event: dict, context=None) -> dict:
    """AgentCore Lambda-style handler.

    Args:
        event: Event dict with 'message', 'merchant_id', and required 'session_id'.
        context: Lambda context (unused).

    Returns:
        Response dict from invoke().
    """
    message = event.get("message", "")
    session_id = event.get("session_id")
    merchant_id = event.get("merchantId") or event.get("merchant_id")
    try:
        return invoke(message, session_id, merchant_id=merchant_id)
    except Exception:
        metrics.add_metric(name="AgentError", unit=MetricUnit.Count, value=1)
        logger.exception("Agent invocation failed")
        raise


# For direct testing
if __name__ == "__main__":
    print("Testing runtime invoke...")
    response = invoke("", session_id="local-test-session", merchant_id="demo-merchant")
    print(f"Greeting: {response}")
