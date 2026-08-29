"""Direct-style phrase parsing for Phase 4 zone additions (Z3-02, Z3-03, Z6-04, Z6-05)."""

from conversational_agent.config_manager import ConfigManager
from conversational_agent.direct_style import (
    apply_direct_style_updates,
    parse_direct_style_updates,
)


def test_button_size_phrases():
    assert parse_direct_style_updates("make the buttons bigger")["button_size"] == "large"
    assert parse_direct_style_updates("smaller buttons please")["button_size"] == "compact"
    assert parse_direct_style_updates("use standard buttons")["button_size"] == "standard"


def test_button_press_phrases():
    assert (
        parse_direct_style_updates("buttons darken on press")["button_press_animation"] == "darken"
    )
    assert (
        parse_direct_style_updates("make buttons scale on tap")["button_press_animation"] == "scale"
    )
    assert (
        parse_direct_style_updates("no button press animation")["button_press_animation"] == "none"
    )


def test_font_scale_phrases():
    assert parse_direct_style_updates("make the text bigger")["font_scale"] == "generous"
    assert parse_direct_style_updates("smaller font please")["font_scale"] == "compact"
    assert parse_direct_style_updates("standard text size")["font_scale"] == "standard"


def test_text_colour_phrases():
    assert parse_direct_style_updates("I want dark text")["text_color"] == "#1a1a1a"
    assert parse_direct_style_updates("use white text")["text_color"] == "#ffffff"
    # Explicit hex wins and is captured verbatim (normalised on apply)
    assert parse_direct_style_updates("text colour #2B2B2B")["text_color"] == "#2B2B2B"


def test_unrelated_message_yields_no_updates():
    assert parse_direct_style_updates("hello there, how are you?") == {}


def test_apply_button_size_and_text_colour_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.setenv("DESIGN_STUDIO_DATA_DIR", str(tmp_path))
    shop = "z4-direct-test"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="T")

    applied, _, updates = apply_direct_style_updates(
        "make the buttons bigger and use dark text", shop_uuid=shop
    )
    assert applied
    assert updates["button_size"] == "large"
    assert updates["text_color"] == "#1a1a1a"

    reloaded = ConfigManager(shop_uuid=shop)
    reloaded.reload()
    assert reloaded.tokens.buttons.size == "large"
    assert reloaded.tokens.colors.textPrimary == "#1a1a1a"
