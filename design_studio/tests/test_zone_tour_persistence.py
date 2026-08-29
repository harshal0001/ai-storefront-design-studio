"""Zone tour state follows the same backend as ConfigManager (DDB vs JSON)."""

import json

from conversational_agent.config_manager import ConfigManager
from conversational_agent.style_repository import StyleRepository
from conversational_agent.zone_tour import ZoneTourManager


def test_zone_tour_uses_json_when_use_dynamodb_false(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.setenv("DYNAMODB_ENDPOINT", "http://127.0.0.1:8001")
    monkeypatch.chdir(tmp_path)

    shop = "json-tour-shop"
    mgr = ZoneTourManager(shop)
    assert not mgr.uses_dynamodb

    mgr.start()
    tour_file = tmp_path / f"storefront_zone_tour_{shop}.json"
    assert tour_file.exists()
    saved = json.loads(tour_file.read_text())
    assert saved["status"] == "active"
    assert saved["currentIndex"] == 0

    mgr.complete_current()
    saved2 = json.loads(tour_file.read_text())
    assert saved2["currentIndex"] == 1

    mgr.cancel()
    assert not tour_file.exists()
    assert not mgr.is_active()


def test_put_zone_tour_fails_fast_without_dynamodb(monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.setenv("DYNAMODB_ENDPOINT", "http://127.0.0.1:8001")
    repo = StyleRepository(shop_uuid="x")
    assert not repo.enabled
    try:
        repo.put_zone_tour("x", {"status": "active"})
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "USE_DYNAMODB" in str(exc)


def test_config_manager_reset_clears_json_zone_tour(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.chdir(tmp_path)
    shop = "reset-tour-shop"
    cm = ConfigManager(shop_uuid=shop, config_path=tmp_path / "storefront_config.json")
    ZoneTourManager(shop, config_path=cm.config_path).start()
    tour_file = tmp_path / f"storefront_zone_tour_{shop}.json"
    assert tour_file.exists()
    cm.reset()
    assert not tour_file.exists()
