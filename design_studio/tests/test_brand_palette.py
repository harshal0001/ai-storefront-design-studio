"""Brand-palette chat input (Z1-03) — parse_brand_palette + update_brand_palette."""

from unittest.mock import MagicMock

from conversational_agent.palette import is_brand_palette_request, parse_brand_palette
from conversational_agent.server import build_brand_palette_prompt
from conversational_agent.style_repository import StyleRepository


def test_is_brand_palette_request_matches_names_and_descriptions_without_hex():
    assert is_brand_palette_request("my brand colours are red and navy")
    assert is_brand_palette_request("use our brand palette please")
    assert not is_brand_palette_request("make the background blue")


def test_build_brand_palette_prompt_covers_acceptance_criteria():
    prompt = build_brand_palette_prompt("my brand red and forest green", ["#C45B28"])
    # any-format colours carried through (names/descriptions + explicit hex)
    assert "my brand red" in prompt
    assert "#C45B28" in prompt
    # role mapping
    assert "primary" in prompt and "accent" in prompt and "background" in prompt
    # 2-3 arrangements
    assert "3 distinct theme package arrangements" in prompt
    # contrast validation + warning
    assert "check_color_accessibility" in prompt and "WCAG AA" in prompt
    # not the Z1-04 photo wording
    assert "photo" not in prompt.lower()


def test_parse_brand_palette_extracts_hexes_with_trigger():
    assert parse_brand_palette("my brand colours are #C45B28 and #1E5F8C") == [
        "#c45b28",
        "#1e5f8c",
    ]


def test_parse_brand_palette_use_these_phrasing():
    assert parse_brand_palette("use these brand colours: #FFFFFF #000000") == [
        "#ffffff",
        "#000000",
    ]


def test_parse_brand_palette_requires_trigger():
    # plain single colour with no brand/palette cue → normal colour handlers, not Z1-03
    assert parse_brand_palette("make it #C45B28") is None


def test_parse_brand_palette_trigger_without_hex_returns_none():
    assert parse_brand_palette("use my brand colours please") is None


def test_parse_brand_palette_dedupes():
    assert parse_brand_palette("our palette: #C45B28 #c45b28 #1E5F8C") == ["#c45b28", "#1e5f8c"]


def test_update_brand_palette_writes_profile(monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "true")
    repo = StyleRepository(shop_uuid="shop-1", style_table="StyleTable")
    table = MagicMock()
    repo._resource = MagicMock()
    repo._resource.Table.return_value = table
    table.get_item.return_value = {}  # no existing profile

    repo.update_brand_palette(["#C45B28", "#1E5F8C"], shop_uuid="shop-1")

    item = table.put_item.call_args.kwargs["Item"]
    assert item["SK"] == "STYLE_PROFILE"
    assert item["brandPaletteInput"] == ["#C45B28", "#1E5F8C"]
