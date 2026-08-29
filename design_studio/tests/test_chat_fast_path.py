"""Regression tests for chat_fast_path handler ordering."""

from unittest.mock import MagicMock

from conversational_agent import chat_fast_path
from conversational_agent.chat_fast_path import record_vibe_selection, run_fast_path
from conversational_agent.config_manager import ConfigManager
from conversational_agent.style_repository import StyleRepository
from conversational_agent.message_parsers import parse_vibe_message
from conversational_agent.section_focus import merge_focus
from conversational_agent.zone_tour import ZoneTourManager


def test_parse_vibe_message_extracts_name():
    assert parse_vibe_message("I'm going for a Modern & minimal vibe") == "Modern & minimal"
    assert parse_vibe_message("im going for an Earthy vibe") == "Earthy"
    assert parse_vibe_message("make buttons pill") is None


def test_vibe_pill_saves_mood_tag_then_defers_to_agent(monkeypatch):
    """A vibe-pill message persists the tag, then returns None so the agent offers themes."""
    monkeypatch.setenv("USE_DYNAMODB", "false")
    captured = {}

    def fake_record(merchant_id, vibe):
        captured["merchant"] = merchant_id
        captured["vibe"] = vibe
        return True

    monkeypatch.setattr(chat_fast_path, "record_vibe_selection", fake_record)

    resp = run_fast_path("vibe-shop", "I'm going for a Warm & cozy vibe", focus=None)

    assert resp is None
    assert captured == {"merchant": "vibe-shop", "vibe": "Warm & cozy"}


def test_record_vibe_selection_merges_and_dedupes(monkeypatch):
    repo = MagicMock()
    repo.enabled = True
    repo.get_style_profile.return_value = {"moodTags": ["rustic", "Warm & cozy"]}
    monkeypatch.setattr(chat_fast_path, "StyleRepository", lambda shop_uuid: repo)

    assert record_vibe_selection("shop-1", "warm & cozy") is True  # case-insensitive dedupe
    merged = repo.update_mood_tags.call_args.args[0]
    assert merged == ["rustic", "Warm & cozy"]
    assert repo.update_mood_tags.call_args.kwargs["shop_uuid"] == "shop-1"


def test_record_vibe_selection_appends_new_tag(monkeypatch):
    repo = MagicMock()
    repo.enabled = True
    repo.get_style_profile.return_value = {"moodTags": ["rustic"]}
    monkeypatch.setattr(chat_fast_path, "StyleRepository", lambda shop_uuid: repo)

    record_vibe_selection("shop-1", "Bold & playful")
    assert repo.update_mood_tags.call_args.args[0] == ["rustic", "Bold & playful"]


def test_record_vibe_selection_persists_to_json_when_ddb_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.setenv("DESIGN_STUDIO_DATA_DIR", str(tmp_path))
    assert record_vibe_selection("shop-1", "Bold") is True
    profile = StyleRepository(shop_uuid="shop-1").get_style_profile("shop-1")
    assert profile["moodTags"] == ["Bold"]


def test_active_zone_tour_free_text_defers_to_agent(tmp_path, monkeypatch):
    """During an active tour, free-text (hex, descriptions) is not applied by fast-path."""
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "fast-path-tour-test"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    cm.reload()

    mgr = ZoneTourManager(shop)
    mgr.start()
    assert mgr.current_step().code == "Z1"

    assert run_fast_path(shop, "#BE185D.", focus=None) is None
    assert run_fast_path(shop, "warm coral for the follow button", focus=None) is None


def test_ui_focus_skips_style_fast_path(tmp_path, monkeypatch):
    """Focused UI edits must reach the agent — not deterministic style parsers."""
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "agent-focus-test"
    cm = ConfigManager(shop_uuid=shop)
    cm.tokens.productCards = cm.tokens.productCards.model_copy(update={"shape": "circularImage"})
    cm.tokens.geometry = cm.tokens.geometry.model_copy(update={"borderRadiusPreset": "pill"})
    cm.save_tokens(cm.tokens, theme_name="Test")
    cm.reload()

    focus = merge_focus(
        focus_zone="Z4C",
        focus_section_id="catalog",
        focus_element_id="catalog_cards",
        message="make the border radius 0",
    )
    resp = run_fast_path(
        shop,
        "make the border radius 0",
        focus,
        style_via_agent=True,
    )
    assert resp is None

    cm2 = ConfigManager(shop_uuid=shop)
    cm2.reload()
    assert cm2.tokens.productCards.shape == "circularImage"
