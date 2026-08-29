"""Tests for DynamoDB-first persistence and JSON fallback isolation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from conversational_agent.config_manager import ConfigManager, default_config_path
from conversational_agent.server import _require_dynamodb_persistence
from conversational_agent.style_tokens import StyleTokens
from conversational_agent.zone_tour import ZoneTourManager


def test_default_config_path_honors_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DESIGN_STUDIO_DATA_DIR", str(tmp_path))
    assert default_config_path() == tmp_path / "storefront_config.json"


def test_config_manager_defaults_to_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DESIGN_STUDIO_DATA_DIR", str(tmp_path))
    cm = ConfigManager(shop_uuid="data-dir-shop")
    assert cm.config_path == tmp_path / "storefront_config.json"


def test_save_tokens_writes_under_data_dir_not_cwd(tmp_path, monkeypatch):
    monkeypatch.setenv("DESIGN_STUDIO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.chdir(tmp_path)

    shop = "history-under-data-dir"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Snapshot")

    history_path = tmp_path / f"storefront_history_{shop}.json"
    tokens_path = tmp_path / f"storefront_tokens_{shop}.json"
    assert history_path.exists()
    assert tokens_path.exists()

    history = json.loads(history_path.read_text())
    assert len(history.get("undoStack") or []) == 1

    repo_root = Path(__file__).resolve().parents[1]
    assert not list(repo_root.glob(f"storefront_history_{shop}.json"))
    assert not list(repo_root.glob(f"storefront_tokens_{shop}.json"))


@pytest.mark.parametrize(
    "writer",
    [
        lambda cm: cm._save_history({"undoStack": [], "redoStack": [], "currentIndex": -1}),
        lambda cm: cm._save_tokens_file(StyleTokens()),
    ],
)
def test_refuses_json_writes_when_dynamodb_enabled(tmp_path, monkeypatch, writer):
    monkeypatch.setenv("USE_DYNAMODB", "true")
    monkeypatch.setenv("DYNAMODB_ENDPOINT", "http://127.0.0.1:8001")
    cm = ConfigManager(shop_uuid="ddb-shop", config_path=tmp_path / "storefront_config.json")
    assert cm.uses_dynamodb
    with pytest.raises(RuntimeError, match="Refusing JSON"):
        writer(cm)


def test_zone_tour_persists_via_dynamodb_not_json(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "true")
    monkeypatch.setenv("DYNAMODB_ENDPOINT", "http://127.0.0.1:8001")
    monkeypatch.setenv("DESIGN_STUDIO_DATA_DIR", str(tmp_path))

    shop = "ddb-tour-shop"
    mgr = ZoneTourManager(shop)
    assert mgr.uses_dynamodb

    mock_repo = MagicMock()
    mgr.repo = mock_repo

    mgr.start()

    mock_repo.put_zone_tour.assert_called_once()
    state = mock_repo.put_zone_tour.call_args.args[1]
    assert state["status"] == "active"
    assert state["currentIndex"] == 0
    assert not (tmp_path / f"storefront_zone_tour_{shop}.json").exists()


def test_require_dynamodb_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)
    _require_dynamodb_persistence()


def test_require_dynamodb_exits_without_endpoint(monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "true")
    monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)
    with pytest.raises(SystemExit, match="DYNAMODB_ENDPOINT"):
        _require_dynamodb_persistence()


def test_require_dynamodb_passes_when_configured(monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "true")
    monkeypatch.setenv("DYNAMODB_ENDPOINT", "http://127.0.0.1:8001")
    _require_dynamodb_persistence()


def test_run_server_validates_before_uvicorn(monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "true")
    monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)

    with patch("uvicorn.run") as mock_run:
        from conversational_agent import server

        with pytest.raises(SystemExit, match="DYNAMODB_ENDPOINT"):
            server.run_server()
        mock_run.assert_not_called()


def test_agent_lock_is_per_merchant():
    from conversational_agent.server import _get_agent_lock

    assert _get_agent_lock("shop-a") is _get_agent_lock("shop-a")
    assert _get_agent_lock("shop-a") is not _get_agent_lock("shop-b")


def test_invoke_agent_serializes_concurrent_calls():
    """RAP-17: overlapping Strands calls on one merchant must not run in parallel."""
    import asyncio
    import time
    from types import SimpleNamespace

    from conversational_agent.response_models import AgentResponse
    from conversational_agent.server import _invoke_agent

    order: list[str] = []

    class SlowAgent:
        def __call__(self, prompt, structured_output_model=None):
            order.append("start")
            time.sleep(0.05)
            order.append("end")
            return SimpleNamespace(
                structured_output=AgentResponse(
                    message="ok",
                    response_type="message",
                )
            )

    async def run_two():
        await asyncio.gather(
            _invoke_agent(SlowAgent(), "serial-shop", "one"),
            _invoke_agent(SlowAgent(), "serial-shop", "two"),
        )

    asyncio.run(run_two())
    assert order == ["start", "end", "start", "end"]


def test_concurrent_empty_greeting_invokes_agent_once(monkeypatch):
    """RAP-17: two racing empty POSTs must not both run GREETING_PROMPT."""
    import asyncio
    from types import SimpleNamespace

    from conversational_agent import server
    from conversational_agent.chat_session import clear_history
    from conversational_agent.response_models import AgentResponse

    calls: list[str] = []

    async def counting_body(agent, merchant_id, prompt, **kwargs):
        calls.append(prompt)
        await asyncio.sleep(0.03)
        return SimpleNamespace(
            structured_output=AgentResponse(
                message="Welcome",
                response_type="greeting",
            )
        )

    monkeypatch.setattr(server, "_invoke_agent_body", counting_body)
    monkeypatch.setattr(server, "create_agent", lambda **kwargs: object())

    shop = "greet-once-shop"
    clear_history(shop)
    server._agent_locks.pop(shop, None)
    server._agents.pop(shop, None)
    server._agent_sessions.pop(shop, None)

    async def race_two_empty_posts():
        await asyncio.gather(
            server.chat(server.ChatRequest(merchantId=shop, message="")),
            server.chat(server.ChatRequest(merchantId=shop, message="")),
        )

    asyncio.run(race_two_empty_posts())
    assert len(calls) == 1
