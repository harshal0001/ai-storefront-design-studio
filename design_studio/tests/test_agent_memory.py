"""Unit tests for AgentCore memory hooks (no AWS calls)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


from conversational_agent.agent_memory import (
    ConversationalAgentMemoryHooks,
    _assistant_response_text,
    _inject_context_prefix,
    _message_text,
    _resolve_memory_reference,
    _resolve_shared_memory_id,
    memory_persist_context,
    memory_resource_name,
    reset_memory_cache,
    ssm_memory_id_param,
)


def test_message_text_from_tool_use_agent_response():
    message = {
        "role": "assistant",
        "content": [
            {"toolUse": {"input": {"message": "Hello merchant", "response_type": "greeting"}}}
        ],
    }
    assert _message_text(message) == "Hello merchant"


def test_inject_context_prefix_leaves_stashable_raw_query_separate():
    message = {"role": "user", "content": [{"text": "I sell tea"}]}
    raw_query = _message_text(message)
    _inject_context_prefix(message, "[SEMANTIC] Merchant sells tea")
    assert raw_query == "I sell tea"
    assert message["content"][0]["text"].startswith("Merchant Context:")
    assert message["content"][0]["text"].endswith("I sell tea")


def test_save_uses_stashed_query_not_enriched_message():
    client = MagicMock()
    client.get_memory_strategies.return_value = []
    hooks = ConversationalAgentMemoryHooks(
        memory_id="mem-1",
        client=client,
        actor_id="demo-merchant",
        session_id="session-1",
    )
    hooks._pending_user_query = "I sell tea"

    message = {
        "role": "user",
        "content": [{"text": "Merchant Context:\n[SEMANTIC] x\n\nI sell tea"}],
    }
    agent = SimpleNamespace(
        messages=[message, {"role": "assistant", "content": [{"text": "Nice!"}]}]
    )
    result = SimpleNamespace(
        structured_output=SimpleNamespace(message="Nice!", response_type="message")
    )
    event = SimpleNamespace(agent=agent, result=result)

    hooks.save_interaction(event)

    hooks.client.create_event.assert_called_once()
    saved_messages = hooks.client.create_event.call_args.kwargs["messages"]
    assert saved_messages[0] == ("I sell tea", "USER")
    assert saved_messages[1] == ("Nice!", "ASSISTANT")
    assert hooks._pending_user_query is None


def test_assistant_response_text_prefers_structured_output():
    event = SimpleNamespace(
        result=SimpleNamespace(structured_output=SimpleNamespace(message="Structured reply")),
        agent=SimpleNamespace(messages=[]),
    )
    assert _assistant_response_text(event) == "Structured reply"


def test_memory_resource_name_is_stage_scoped(monkeypatch):
    monkeypatch.delenv("AGENTCORE_MEMORY_NAME", raising=False)
    monkeypatch.setenv("AGENTCORE_MEMORY_STAGE", "dev")
    assert memory_resource_name() == "ConversationalAgentMemory-dev"
    assert ssm_memory_id_param() == "/app/conversational_agent/dev/memory_id"


def test_resolve_memory_reference_requires_exact_match():
    client = MagicMock()
    client.gmcp_client.get_memory.side_effect = RuntimeError("not found")
    client.list_memories.return_value = [
        {"id": "mem-abc123", "name": "ConversationalAgentMemory-dev"},
        {"id": "mem-xyz789", "name": "ConversationalAgentMemory-prod"},
    ]

    assert _resolve_memory_reference(client, "abc") is None
    assert _resolve_memory_reference(client, "ConversationalAgentMemory-dev") == "mem-abc123"


def test_resolve_memory_reference_rejects_ambiguous_name_matches():
    client = MagicMock()
    client.gmcp_client.get_memory.side_effect = RuntimeError("not found")
    client.list_memories.return_value = [
        {"id": "mem-1", "name": "shared-name"},
        {"id": "mem-2", "name": "shared-name"},
    ]

    assert _resolve_memory_reference(client, "shared-name") is None


def test_explicit_memory_id_fails_closed(monkeypatch):
    reset_memory_cache()
    monkeypatch.setenv("AGENTCORE_MEMORY_ID", "missing-memory-id")

    client = MagicMock()
    client.gmcp_client.get_memory.side_effect = RuntimeError("not found")
    client.list_memories.return_value = []

    assert _resolve_shared_memory_id(client) is None


def test_save_skipped_when_persistence_disabled():
    client = MagicMock()
    client.get_memory_strategies.return_value = []
    hooks = ConversationalAgentMemoryHooks(
        memory_id="mem-1",
        client=client,
        actor_id="demo-merchant",
        session_id="session-1",
    )
    hooks._pending_user_query = "internal orchestration prompt"
    event = SimpleNamespace(
        agent=SimpleNamespace(messages=[]),
        result=SimpleNamespace(
            structured_output=SimpleNamespace(message="Hello", response_type="message")
        ),
    )

    with memory_persist_context(enabled=False):
        hooks.save_interaction(event)

    client.create_event.assert_not_called()


def test_save_uses_explicit_merchant_message_over_generated_prompt():
    client = MagicMock()
    client.get_memory_strategies.return_value = []
    hooks = ConversationalAgentMemoryHooks(
        memory_id="mem-1",
        client=client,
        actor_id="demo-merchant",
        session_id="session-1",
    )
    hooks._pending_user_query = (
        "The merchant uploaded a photo/logo. These are the dominant colours..."
    )
    event = SimpleNamespace(
        agent=SimpleNamespace(messages=[]),
        result=SimpleNamespace(
            structured_output=SimpleNamespace(message="Here are themes", response_type="message")
        ),
    )

    with memory_persist_context(merchant_message="Make it feel cozy"):
        hooks.save_interaction(event)

    saved_messages = client.create_event.call_args.kwargs["messages"]
    assert saved_messages[0] == ("Make it feel cozy", "USER")
