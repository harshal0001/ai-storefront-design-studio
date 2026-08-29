"""Tests for server-side theme package selection."""

import pytest

from conversational_agent import theme_choice_actions
from conversational_agent.config_manager import ConfigManager
from conversational_agent.style_tokens import StyleTokens
from conversational_agent.theme_choice_actions import (
    _map_colors,
    apply_theme_choice,
    clear_pending_theme_packages,
    store_pending_theme_packages,
    try_handle_theme_choice,
)


@pytest.fixture(autouse=True)
def _json_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.setenv("DESIGN_STUDIO_DATA_DIR", str(tmp_path))


OPULENT = {
    "name": "Opulent Elegance",
    "description": "A luxurious and sophisticated theme with a modern twist.",
    "colors": [
        {"hex": "#4B0082", "name": "Royal Purple"},
        {"hex": "#2B4100", "name": "Emerald Green"},
        {"hex": "#743DB3", "name": "Midnight Lavender"},
        {"hex": "#526B30", "name": "Olive Grove"},
    ],
    "heading_font": "Playfair Display",
    "body_font": "Montserrat",
    "border_radius": "rounded",
    "spacing": "spacious",
}


def test_map_colors_four_swatches():
    mapped = _map_colors(OPULENT["colors"])
    assert mapped["primary_color"] == "#4B0082"
    assert mapped["secondary_color"] == "#2B4100"
    assert mapped["accent_color"] == "#743DB3"
    assert mapped["background_color"] == "#526B30"
    assert mapped["surface_color"] == "#526B30"


def test_apply_pending_theme_choice():
    shop = "theme-choice-shop"
    clear_pending_theme_packages(shop)
    store_pending_theme_packages(shop, [OPULENT])

    name = apply_theme_choice(shop, "Opulent Elegance")
    assert name == "Opulent Elegance"

    cm = ConfigManager(shop_uuid=shop)
    cm.reload()
    assert cm.tokens.colors.primary.lower() == "#4b0082"
    assert cm.tokens.typography.headingFont == "Playfair Display"
    assert cm.tokens.geometry.spacingPreset == "spacious"


def test_try_handle_theme_choice_blocked_during_active_tour(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "theme-blocked-tour"
    from conversational_agent.config_manager import ConfigManager
    from conversational_agent.zone_tour import ZoneTourManager

    ConfigManager(shop_uuid=shop).save_tokens(
        ConfigManager(shop_uuid=shop).tokens, theme_name="Test"
    )
    store_pending_theme_packages(shop, [OPULENT])
    ZoneTourManager(shop).start()

    assert try_handle_theme_choice(shop, 'I choose "Opulent Elegance"') is None


def test_try_handle_theme_choice_message():
    shop = "theme-msg-shop"
    clear_pending_theme_packages(shop)
    store_pending_theme_packages(shop, [OPULENT])

    resp = try_handle_theme_choice(shop, 'I choose "Opulent Elegance"')
    assert resp is not None
    assert resp["type"] == "applied"
    assert "Opulent Elegance" in resp["message"]


def test_try_handle_returns_none_for_unrelated_message():
    assert try_handle_theme_choice("x", "make buttons pill") is None


def test_unknown_theme_returns_helpful_message():
    shop = "theme-unknown-shop"
    clear_pending_theme_packages(shop)
    resp = try_handle_theme_choice(shop, 'I choose "Missing Theme"')
    assert resp["type"] == "message"
    assert "No theme" in resp["message"]


class _RecordingCM:
    """ConfigManager stand-in that captures the kwargs of the last save_tokens call."""

    last_kwargs: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    def save_tokens(self, tokens, **kwargs):
        _RecordingCM.last_kwargs = dict(kwargs)

    def reload(self):
        pass


def test_apply_catalog_package_stamps_based_on_package_id(monkeypatch):
    """Catalogue packages must record basedOnPackageId on the saved draft (CF-02 / 3.4)."""

    class _FakeRepo:
        def __init__(self, *args, **kwargs):
            pass

        def get_theme_package_tokens(self, package_id):
            return StyleTokens()

    _RecordingCM.last_kwargs = {}
    monkeypatch.setattr(theme_choice_actions, "StyleRepository", _FakeRepo)
    monkeypatch.setattr(theme_choice_actions, "ConfigManager", _RecordingCM)

    pkg = {"packageId": "tuscan_workshop", "displayName": "Tuscan Workshop"}
    name = theme_choice_actions._apply_catalog_package(
        "shop-1", pkg, mood_summary="warm and rustic"
    )

    assert name == "Tuscan Workshop"
    assert _RecordingCM.last_kwargs["based_on_package_id"] == "tuscan_workshop"
    assert _RecordingCM.last_kwargs["theme_name"] == "Tuscan Workshop"
    assert _RecordingCM.last_kwargs["mood_summary"] == "warm and rustic"


def test_apply_custom_package_omits_based_on_package_id(monkeypatch):
    """Custom (LLM-generated) packages have no source id, so basedOnPackageId stays unset (CF-02)."""
    _RecordingCM.last_kwargs = {}
    monkeypatch.setattr(theme_choice_actions, "ConfigManager", _RecordingCM)

    name = theme_choice_actions._apply_custom_package("shop-1", OPULENT)

    assert name == "Opulent Elegance"
    assert "based_on_package_id" not in _RecordingCM.last_kwargs
