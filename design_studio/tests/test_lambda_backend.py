"""Lambda Function URL backend routing tests."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass

from lambda_backend import handler as api


@dataclass
class _FakeLambdaContext:
    function_name: str = "test-function"
    memory_limit_in_mb: int = 512
    invoked_function_arn: str = "arn:aws:lambda:eu-north-1:123456789012:function:test"
    aws_request_id: str = "test-request-id"


def _ctx():
    return _FakeLambdaContext()


def _event(method: str, path: str, body: dict | None = None, headers: dict | None = None):
    return {
        "version": "2.0",
        "rawPath": path,
        "headers": {"x-cf-origin-secret": "secret"} if headers is None else headers,
        "requestContext": {"http": {"method": method}},
        "body": json.dumps(body or {}),
        "isBase64Encoded": False,
    }


def test_rejects_missing_origin_secret(monkeypatch):
    monkeypatch.setenv("CF_ORIGIN_SECRET", "secret")

    response = api.handler(_event("GET", "/api/storefront/shop-1", headers={}), _ctx())

    assert response["statusCode"] == 403
    assert response["body"] == "forbidden"


def test_chat_invokes_agentcore_with_merchant_payload(monkeypatch):
    calls = []

    class FakeAgentClient:
        def invoke_agent_runtime(self, **kwargs):
            calls.append(kwargs)
            return {"response": io.BytesIO(b'{"message":"Hi","type":"message"}')}

    monkeypatch.setenv("AGENT_RUNTIME_ARN", "arn:aws:bedrock-agentcore:eu-north-1:123:runtime/demo")
    monkeypatch.setenv("CF_ORIGIN_SECRET", "secret")
    monkeypatch.setattr(api, "_agent_client", lambda: FakeAgentClient())

    response = api.handler(
        _event(
            "POST",
            "/api/chat",
            {"merchantId": "shop-1", "sessionId": "session-1", "message": "hello"},
        ),
        _ctx(),
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"message": "Hi", "type": "message"}
    assert calls[0]["runtimeSessionId"] == "session-1"
    assert json.loads(calls[0]["payload"].decode()) == {
        "message": "hello",
        "session_id": "session-1",
        "merchant_id": "shop-1",
    }


def test_chat_fast_path_short_circuits_agentcore(monkeypatch):
    """A deterministic fast-path hit returns immediately without invoking AgentCore."""
    invoked = []

    class FakeAgentClient:
        def invoke_agent_runtime(self, **kwargs):
            invoked.append(kwargs)
            return {"response": io.BytesIO(b'{"message":"should not run","type":"message"}')}

    monkeypatch.setenv("CF_ORIGIN_SECRET", "secret")
    monkeypatch.setattr(api, "_agent_client", lambda: FakeAgentClient())
    monkeypatch.setattr(
        api,
        "run_fast_path",
        lambda *a, **k: {"type": "applied", "message": "Done", "html": "<html></html>"},
    )

    response = api.handler(
        _event(
            "POST",
            "/api/chat",
            {"merchantId": "shop-1", "sessionId": "s1", "message": 'I choose "Earthy Charm"'},
        ),
        _ctx(),
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["type"] == "applied"
    assert invoked == []  # AgentCore must not be called when the fast path handles it


def test_chat_caches_agent_theme_packages(monkeypatch):
    """Theme cards returned by the agent are cached so a follow-up choice skips Bedrock."""
    cached = []

    class FakeAgentClient:
        def invoke_agent_runtime(self, **kwargs):
            packages = [{"name": "Earthy Charm", "colors": [{"hex": "#A86B3F"}]}]
            body = json.dumps({"message": "Here are some themes", "theme_packages": packages})
            return {"response": io.BytesIO(body.encode())}

    monkeypatch.setenv("AGENT_RUNTIME_ARN", "arn:aws:bedrock-agentcore:eu-north-1:123:runtime/demo")
    monkeypatch.setenv("CF_ORIGIN_SECRET", "secret")
    monkeypatch.setattr(api, "_agent_client", lambda: FakeAgentClient())
    monkeypatch.setattr(api, "run_fast_path", lambda *a, **k: None)
    monkeypatch.setattr(
        api, "store_pending_theme_packages", lambda mid, pkgs: cached.append((mid, pkgs))
    )

    response = api.handler(
        _event(
            "POST",
            "/api/chat",
            {"merchantId": "shop-1", "sessionId": "s1", "message": "I run a coffee shop"},
        ),
        _ctx(),
    )

    assert response["statusCode"] == 200
    assert cached and cached[0][0] == "shop-1"
    assert cached[0][1][0]["name"] == "Earthy Charm"


def test_versions_route_uses_repository_payload(monkeypatch):
    class FakeRepo:
        def list_version_summaries(self, merchant_id):
            assert merchant_id == "shop-1"
            return [
                {
                    "versionId": 0,
                    "versionSeq": 3,
                    "label": "Version 1",
                    "lastModified": "2026-05-26T10:00:00Z",
                    "isCurrent": True,
                }
            ]

    monkeypatch.setenv("CF_ORIGIN_SECRET", "secret")
    monkeypatch.setattr(api, "_repo", lambda merchant_id: FakeRepo())

    response = api.handler(_event("GET", "/api/versions/shop-1"), _ctx())

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["versions"][0]["versionSeq"] == 3


def test_chat_defaults_session_for_compatibility(monkeypatch):
    calls = []

    class FakeAgentClient:
        def invoke_agent_runtime(self, **kwargs):
            calls.append(kwargs)
            return {"response": io.BytesIO(b'{"message":"Welcome","type":"message"}')}

    monkeypatch.setenv("AGENT_RUNTIME_ARN", "arn:aws:bedrock-agentcore:eu-north-1:123:runtime/demo")
    monkeypatch.setenv("CF_ORIGIN_SECRET", "secret")
    monkeypatch.setattr(api, "_agent_client", lambda: FakeAgentClient())

    response = api.handler(
        _event("POST", "/api/chat", {"merchantId": "shop-1", "message": ""}),
        _ctx(),
    )

    assert response["statusCode"] == 200
    assert calls[0]["runtimeSessionId"] == "shop-1-default"


def test_restore_rejects_invalid_version(monkeypatch):
    class FakeRepo:
        def list_version_summaries(self, merchant_id):
            return []

    monkeypatch.setenv("CF_ORIGIN_SECRET", "secret")
    monkeypatch.setattr(api, "_repo", lambda merchant_id: FakeRepo())

    response = api.handler(
        _event("POST", "/api/restore", {"merchantId": "shop-1", "versionId": 0}),
        _ctx(),
    )

    assert response["statusCode"] == 400
    assert json.loads(response["body"]) == {"detail": "Invalid version"}
