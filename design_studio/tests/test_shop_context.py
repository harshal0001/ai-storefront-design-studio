"""Merchant scope for agent tools."""

from conversational_agent.config_manager import DEFAULT_SHOP_UUID
from conversational_agent.shop_context import get_shop_uuid, shop_context


def test_shop_context_sets_merchant_for_tools():
    assert get_shop_uuid() == DEFAULT_SHOP_UUID
    with shop_context("coffee-shop-42"):
        assert get_shop_uuid() == "coffee-shop-42"
    assert get_shop_uuid() == DEFAULT_SHOP_UUID


def test_get_config_manager_uses_context(monkeypatch):
    from conversational_agent import tools

    seen: list[str] = []

    class FakeCM:
        def __init__(self, shop_uuid: str):
            seen.append(shop_uuid)

    monkeypatch.setattr(tools, "ConfigManager", FakeCM)

    with shop_context("merchant-xyz"):
        tools._get_config_manager()

    assert seen == ["merchant-xyz"]


def test_create_agent_with_merchant_binds_invocations(monkeypatch):
    from conversational_agent import agent as agent_module

    class FakeAgent:
        def __init__(self, **kwargs):
            pass

        def __call__(self, message):
            return f"{message}:{get_shop_uuid()}"

    monkeypatch.setattr(agent_module, "Agent", FakeAgent)

    scoped_agent = agent_module.create_agent(merchant_id="scoped-shop")

    assert scoped_agent("hello") == "hello:scoped-shop"
    assert get_shop_uuid() == DEFAULT_SHOP_UUID
