"""AgentCore Memory integration for the Design Studio conversational agent.

Resolves the shared memory resource dynamically (env → SSM → list → create), then
attaches Strands hooks to retrieve merchant context before each turn and persist
interactions after each response. SSM is an optional cache, not required for dev.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Iterator

import boto3
from botocore.exceptions import ClientError
from strands.hooks import (
    AfterInvocationEvent,
    HookProvider,
    HookRegistry,
    MessageAddedEvent,
)

if TYPE_CHECKING:
    from bedrock_agentcore.memory import MemoryClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MEMORY_REGION = os.environ.get("AGENTCORE_MEMORY_REGION", "eu-north-1")
MEMORY_NAME_BASE = "ConversationalAgentMemory"
ENV_MEMORY_STAGE = "AGENTCORE_MEMORY_STAGE"
ENV_MEMORY_NAME = "AGENTCORE_MEMORY_NAME"
ENV_MEMORY_ID = "AGENTCORE_MEMORY_ID"
MEMORY_EVENT_EXPIRY_DAYS = 90
MEMORY_TOP_K = 3

_memory_persist_enabled: ContextVar[bool] = ContextVar("memory_persist_enabled", default=True)
_memory_merchant_message: ContextVar[str | None] = ContextVar(
    "memory_merchant_message", default=None
)

# Process-level cache — populated on first successful resolution.
_cached_memory_id: str | None = None
_memory_client: MemoryClient | None = None


def _memory_stage() -> str:
    stage = (
        os.environ.get(ENV_MEMORY_STAGE)
        or os.environ.get("ENVIRONMENT")
        or os.environ.get("STAGE")
        or "local"
    ).strip()
    return stage or "local"


def memory_resource_name() -> str:
    """Return the stage-scoped memory resource name for this deployment."""
    explicit = os.environ.get(ENV_MEMORY_NAME, "").strip()
    if explicit:
        return explicit
    return f"{MEMORY_NAME_BASE}-{_memory_stage()}"


def ssm_memory_id_param() -> str:
    """Return the stage-scoped SSM parameter used to cache the resolved memory ID."""
    return f"/app/conversational_agent/{_memory_stage()}/memory_id"


@contextmanager
def memory_persist_context(
    *,
    merchant_message: str | None = None,
    enabled: bool = True,
) -> Iterator[None]:
    """Control AgentCore Memory retrieve/save behaviour for one agent invocation."""
    token_enabled = _memory_persist_enabled.set(enabled)
    token_message = _memory_merchant_message.set(merchant_message)
    try:
        yield
    finally:
        _memory_persist_enabled.reset(token_enabled)
        _memory_merchant_message.reset(token_message)


def reset_memory_cache() -> None:
    """Clear process-level memory resolution cache (tests only)."""
    global _cached_memory_id, _memory_client
    _cached_memory_id = None
    _memory_client = None


# ---------------------------------------------------------------------------
# Strands message helpers
# ---------------------------------------------------------------------------


def _is_tool_result_message(message: dict[str, Any]) -> bool:
    content = message.get("content") or []
    return any(isinstance(block, dict) and "toolResult" in block for block in content)


def _message_text(message: dict[str, Any]) -> str:
    """Extract plain text from a Strands message, including structured tool output."""
    parts: list[str] = []
    for block in message.get("content") or []:
        if not isinstance(block, dict):
            continue
        if "text" in block:
            parts.append(str(block["text"]))
        elif "toolUse" in block:
            tool_input = block["toolUse"].get("input") or {}
            if isinstance(tool_input, dict) and "message" in tool_input:
                parts.append(str(tool_input["message"]))
    return "\n".join(part.strip() for part in parts if part.strip())


def _latest_user_query(messages: list[dict[str, Any]]) -> str | None:
    for message in reversed(messages):
        if message.get("role") != "user" or _is_tool_result_message(message):
            continue
        text = _message_text(message)
        if text:
            return text
    return None


def _assistant_response_text(event: AfterInvocationEvent) -> str | None:
    """Design Studio agents respond via structured AgentResponse, not plain text."""
    result = event.result
    if result and result.structured_output is not None:
        message = getattr(result.structured_output, "message", None)
        if message:
            return str(message).strip()

    for message in reversed(event.agent.messages):
        if message.get("role") != "assistant":
            continue
        text = _message_text(message)
        if text:
            return text
    return None


def _inject_context_prefix(message: dict[str, Any], context_text: str) -> None:
    for block in message.get("content") or []:
        if isinstance(block, dict) and "text" in block:
            block["text"] = f"Merchant Context:\n{context_text}\n\n{block['text']}"
            return


# ---------------------------------------------------------------------------
# Memory resource resolution
# ---------------------------------------------------------------------------


def _memory_record_id(record: dict[str, Any]) -> str | None:
    return record.get("id") or record.get("memoryId")


def _memory_record_name(record: dict[str, Any]) -> str:
    return record.get("name") or record.get("memoryName") or ""


def _memory_exists_error(exc: Exception) -> bool:
    if "already exists" in str(exc).lower() or "alreadyexist" in str(exc).lower():
        return True
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        return code in (
            "ConflictException",
            "ResourceAlreadyExistsException",
            "AlreadyExistsException",
        )
    return False


def _get_memory_client() -> MemoryClient:
    global _memory_client
    if _memory_client is None:
        from bedrock_agentcore.memory import MemoryClient

        _memory_client = MemoryClient(region_name=MEMORY_REGION)
    return _memory_client


def _list_all_memories(client: MemoryClient) -> list[dict[str, Any]]:
    """Return all memory records, with control-plane fallback."""
    records: list[dict[str, Any]] = []

    try:
        listed = client.list_memories()
    except Exception as exc:
        logger.debug("MemoryClient.list_memories failed: %s", exc)
        listed = None

    if listed is not None:
        if isinstance(listed, dict):
            records.extend(listed.get("memories") or listed.get("items") or [])
            next_token = listed.get("nextToken")
            while next_token:
                page = client.list_memories(nextToken=next_token)
                if not isinstance(page, dict):
                    break
                records.extend(page.get("memories") or page.get("items") or [])
                next_token = page.get("nextToken")
        else:
            records.extend(listed)

    if records:
        return records

    try:
        control = boto3.client("bedrock-agentcore-control", region_name=MEMORY_REGION)
        next_token = None
        while True:
            params: dict[str, str] = {}
            if next_token:
                params["nextToken"] = next_token
            response = control.list_memories(**params)
            records.extend(response.get("memories") or [])
            next_token = response.get("nextToken")
            if not next_token:
                break
    except Exception as exc:
        logger.debug("bedrock-agentcore-control list_memories failed: %s", exc)

    return records


def _resolve_memory_reference(client: MemoryClient, reference: str) -> str | None:
    """Resolve a memory ID or resource name to a validated memory ID."""
    ref = reference.strip()
    if not ref:
        return None

    try:
        client.gmcp_client.get_memory(memoryId=ref)
        logger.info("Resolved AgentCore Memory by ID: %s", ref)
        return ref
    except Exception as exc:
        logger.debug("get_memory(%s) failed: %s", ref, exc)

    matches: list[str] = []
    for record in _list_all_memories(client):
        memory_id = _memory_record_id(record)
        if not memory_id:
            continue
        memory_label = _memory_record_name(record)
        if memory_id == ref or memory_label == ref:
            matches.append(memory_id)

    if not matches:
        return None
    if len(matches) > 1:
        logger.error(
            "Ambiguous AgentCore Memory reference %r matched %d resources",
            ref,
            len(matches),
        )
        return None

    logger.info("Resolved AgentCore Memory reference %s -> %s", ref, matches[0])
    return matches[0]


def _try_get_ssm_parameter(name: str) -> str | None:
    try:
        ssm = boto3.client("ssm", region_name=MEMORY_REGION)
        response = ssm.get_parameter(Name=name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code != "AccessDeniedException":
            logger.debug("SSM parameter %s not available: %s", name, exc)
    except Exception as exc:
        logger.debug("SSM lookup failed for %s: %s", name, exc)
    return None


def _try_put_ssm_parameter(name: str, value: str) -> None:
    try:
        ssm = boto3.client("ssm", region_name=MEMORY_REGION)
        ssm.put_parameter(Name=name, Value=value, Type="String", Overwrite=True)
        logger.info("Cached memory ID in SSM: %s", name)
    except Exception as exc:
        logger.debug("Could not cache memory ID in SSM (%s): %s", name, exc)


def _memory_strategies() -> list[dict[str, Any]]:
    from bedrock_agentcore.memory.constants import StrategyType

    return [
        {
            StrategyType.USER_PREFERENCE.value: {
                "name": "ConversationalAgentPreferences",
                "description": "Captures merchant preferences and settings",
                "namespaces": ["support/user/{actorId}/preferences"],
            }
        },
        {
            StrategyType.SEMANTIC.value: {
                "name": "ConversationalAgentSemantic",
                "description": "Stores factual information from conversations",
                "namespaces": ["support/user/{actorId}/semantic"],
            }
        },
    ]


def _create_memory_resource(client: MemoryClient) -> str | None:
    memory_name = memory_resource_name()
    try:
        logger.info(
            "Creating AgentCore Memory resource %s (this can take a couple of minutes)",
            memory_name,
        )
        response = client.create_memory_and_wait(
            name=memory_name,
            description="Conversational agent memory",
            strategies=_memory_strategies(),
            event_expiry_days=MEMORY_EVENT_EXPIRY_DAYS,
        )
        return response["id"]
    except Exception as exc:
        if not _memory_exists_error(exc):
            logger.warning("Failed to create AgentCore Memory resource: %s", exc)
            return None

        logger.info(
            "AgentCore Memory %s already exists — resolving existing resource",
            memory_name,
        )
        existing_id = _resolve_memory_reference(client, memory_name)
        if existing_id:
            return existing_id

        logger.warning(
            "Memory exists but could not be resolved; set %s in example.env",
            ENV_MEMORY_ID,
        )
        return None


def _resolve_shared_memory_id(client: MemoryClient) -> str | None:
    """Resolution chain: env override → SSM cache → list by name → create."""
    env_ref = os.environ.get(ENV_MEMORY_ID, "").strip()
    if env_ref:
        resolved_id = _resolve_memory_reference(client, env_ref)
        if resolved_id:
            logger.info("Using AgentCore Memory from %s", ENV_MEMORY_ID)
            return resolved_id
        logger.error(
            "%s=%s could not be resolved; refusing discovery fallback",
            ENV_MEMORY_ID,
            env_ref,
        )
        return None

    ssm_ref = _try_get_ssm_parameter(ssm_memory_id_param())
    if ssm_ref:
        resolved_id = _resolve_memory_reference(client, ssm_ref)
        if resolved_id:
            logger.info("Using AgentCore Memory from SSM cache")
            return resolved_id

    memory_name = memory_resource_name()
    return _resolve_memory_reference(client, memory_name) or _create_memory_resource(client)


def create_or_get_memory_resource() -> str | None:
    """Return the shared memory ID for this process (resolved once, then cached)."""
    global _cached_memory_id
    if _cached_memory_id:
        return _cached_memory_id

    try:
        client = _get_memory_client()
    except ImportError:
        logger.warning("bedrock-agentcore is not installed; memory hooks disabled")
        return None

    resolved_id = _resolve_shared_memory_id(client)
    if not resolved_id:
        logger.warning("AgentCore Memory unavailable — continuing without memory hooks")
        return None

    _cached_memory_id = resolved_id
    _try_put_ssm_parameter(ssm_memory_id_param(), resolved_id)
    return resolved_id


# ---------------------------------------------------------------------------
# Strands hooks
# ---------------------------------------------------------------------------


def _memory_text(memory: dict[str, Any]) -> str | None:
    content = memory.get("content", {})
    if not isinstance(content, dict):
        return None
    text = content.get("text", "").strip()
    return text or None


def _load_namespaces(client: MemoryClient, memory_id: str) -> dict[str, str]:
    return {
        strategy["type"]: strategy["namespaces"][0]
        for strategy in client.get_memory_strategies(memory_id)
    }


class ConversationalAgentMemoryHooks(HookProvider):
    """Retrieve and persist merchant context via AgentCore Memory."""

    def __init__(
        self,
        memory_id: str,
        client: MemoryClient,
        actor_id: str,
        session_id: str,
    ) -> None:
        self.memory_id = memory_id
        self.client = client
        self.actor_id = actor_id
        self.session_id = session_id
        self.namespaces = _load_namespaces(client, memory_id)
        # Raw user text for save_interaction — set before Merchant Context injection.
        self._pending_user_query: str | None = None
        logger.info(
            "Memory hooks ready memory_id=%s actor_id=%s session_id=%s namespaces=%s",
            memory_id,
            actor_id,
            session_id,
            list(self.namespaces),
        )

    def retrieve_merchant_context(self, event: MessageAddedEvent) -> None:
        if not _memory_persist_enabled.get():
            return

        message = event.message
        if message.get("role") != "user" or _is_tool_result_message(message):
            return

        user_query = _message_text(message)
        if not user_query:
            return

        self._pending_user_query = user_query
        logger.info("Memory retrieve actor=%s session=%s", self.actor_id, self.session_id)
        try:
            context_lines = self._fetch_context_lines(user_query)
            if context_lines:
                _inject_context_prefix(message, "\n".join(context_lines))
                logger.info("Retrieved %d merchant context items", len(context_lines))
            else:
                logger.info("No merchant context memories matched this query")
        except Exception as exc:
            logger.error("Failed to retrieve merchant context: %s", exc)

    def save_interaction(self, event: AfterInvocationEvent) -> None:
        try:
            if not _memory_persist_enabled.get():
                logger.info("Memory save skipped (persistence disabled for this invocation)")
                return

            explicit_message = _memory_merchant_message.get()
            user_query = (
                explicit_message
                or self._pending_user_query
                or _latest_user_query(event.agent.messages)
            )
            assistant_reply = _assistant_response_text(event)
            if not user_query or not assistant_reply:
                logger.info(
                    "Memory save skipped (user_query=%s assistant_response=%s)",
                    bool(user_query),
                    bool(assistant_reply),
                )
                return

            logger.info("Memory save actor=%s session=%s", self.actor_id, self.session_id)
            self.client.create_event(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                messages=[(user_query, "USER"), (assistant_reply, "ASSISTANT")],
            )
            logger.info("Saved design-studio interaction to memory")
        except Exception as exc:
            logger.error("Failed to save interaction to memory: %s", exc)
        finally:
            self._pending_user_query = None

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(MessageAddedEvent, self.retrieve_merchant_context)
        registry.add_callback(AfterInvocationEvent, self.save_interaction)
        logger.info("Conversational agent memory hooks registered")

    def _fetch_context_lines(self, user_query: str) -> list[str]:
        lines: list[str] = []
        for context_type, namespace in self.namespaces.items():
            memories = self.client.retrieve_memories(
                memory_id=self.memory_id,
                namespace=namespace.format(actorId=self.actor_id),
                query=user_query,
                top_k=MEMORY_TOP_K,
            )
            for memory in memories:
                if not isinstance(memory, dict):
                    continue
                text = _memory_text(memory)
                if text:
                    lines.append(f"[{context_type.upper()}] {text}")
        return lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_memory_hooks(
    merchant_id: str,
    session_id: str,
) -> ConversationalAgentMemoryHooks | None:
    """Create memory hooks for a merchant session, or None if memory is unavailable."""
    memory_id = create_or_get_memory_resource()
    if not memory_id:
        return None

    try:
        return ConversationalAgentMemoryHooks(
            memory_id=memory_id,
            client=_get_memory_client(),
            actor_id=merchant_id,
            session_id=session_id,
        )
    except ImportError:
        logger.warning("bedrock-agentcore is not installed; memory hooks disabled")
        return None
    except Exception as exc:
        logger.warning("Failed to initialize memory hooks: %s", exc)
        return None
