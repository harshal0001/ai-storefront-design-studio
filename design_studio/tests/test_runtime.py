"""AgentCore runtime contract tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from conversational_agent import runtime
from conversational_agent.response_models import AgentResponse
from conversational_agent.shop_context import get_shop_uuid


def test_invoke_requires_merchant_id():
    with pytest.raises(ValueError, match="merchant_id is required"):
        runtime.invoke("hello", session_id="session-1")


def test_invoke_requires_session_id():
    with pytest.raises(ValueError, match="session_id is required"):
        runtime.invoke("hello", merchant_id="merchant-1")


def test_invoke_creates_scoped_agent_and_binds_shop_context(monkeypatch):
    created_for: list[str | None] = []
    invoked_with_context: list[str] = []

    class FakeAgent:
        def __call__(self, prompt, structured_output_model=None):
            invoked_with_context.append(get_shop_uuid())
            return SimpleNamespace(
                structured_output=AgentResponse(
                    message=f"echo: {prompt}",
                    response_type="message",
                )
            )

    def fake_create_agent(*, merchant_id=None, **kwargs):
        created_for.append(merchant_id)
        return FakeAgent()

    monkeypatch.setattr(runtime, "create_agent", fake_create_agent)

    response = runtime.invoke("make it warmer", session_id="session-1", merchant_id="merchant-1")

    assert created_for == ["merchant-1"]
    assert invoked_with_context == ["merchant-1"]
    assert response == {
        "message": "echo: make it warmer",
        "type": "message",
    }


@pytest.mark.parametrize(
    ("payload_key", "payload_value"),
    [
        ("merchant_id", "merchant-snake"),
        ("merchantId", "merchant-camel"),
    ],
)
def test_handler_accepts_merchant_id_payload_keys(monkeypatch, payload_key, payload_value):
    seen: dict[str, str | None] = {}

    def fake_invoke(message, session_id=None, merchant_id=None):
        seen["message"] = message
        seen["session_id"] = session_id
        seen["merchant_id"] = merchant_id
        return {"message": "ok", "type": "message"}

    monkeypatch.setattr(runtime, "invoke", fake_invoke)

    response = runtime.handler(
        {
            "message": "hello",
            "session_id": "session-1",
            payload_key: payload_value,
        }
    )

    assert response == {"message": "ok", "type": "message"}
    assert seen == {
        "message": "hello",
        "session_id": "session-1",
        "merchant_id": payload_value,
    }
