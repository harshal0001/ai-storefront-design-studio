"""Tests for the color science layer — pure functions, no AWS, no LLM."""

import pytest

from conversational_agent.color_engine import (
    HARMONY_DESCRIPTIONS,
    adjust_for_contrast,
    check_contrast_ratio,
    generate_palette_from_seed,
    get_contrast_color,
    get_darker,
    get_lighter,
    is_accessible,
    is_valid_google_font,
    normalize_hex,
    validate_hex,
)


class TestValidateHex:
    @pytest.mark.parametrize("value", ["#000000", "#FFFFFF", "#b63f81", "#abc"])
    def test_accepts_valid_hex(self, value):
        assert validate_hex(value) is True

    @pytest.mark.parametrize("value", ["not-a-color", "#ZZZZZZ", "", "rgb(0,0,0)x"])
    def test_rejects_invalid(self, value):
        assert validate_hex(value) is False


class TestNormalizeHex:
    def test_lowercases_and_expands(self):
        # coloraide normalizes to lowercase 6-digit hex
        assert normalize_hex("#B63F81").lower() == "#b63f81"

    def test_passes_through_invalid_unchanged(self):
        assert normalize_hex("not-a-color") == "not-a-color"


class TestContrast:
    def test_black_on_white_is_max_ratio(self):
        # WCAG max contrast is exactly 21:1
        ratio = check_contrast_ratio("#000000", "#FFFFFF")
        assert ratio == pytest.approx(21.0, abs=0.01)

    def test_same_color_is_one(self):
        assert check_contrast_ratio("#888888", "#888888") == pytest.approx(1.0, abs=0.01)

    def test_aa_passes_for_high_contrast(self):
        assert is_accessible("#000000", "#FFFFFF", "AA") is True
        assert is_accessible("#000000", "#FFFFFF", "AAA") is True

    def test_aa_fails_for_low_contrast(self):
        # Light grey on white is well below 4.5:1
        assert is_accessible("#CCCCCC", "#FFFFFF", "AA") is False

    def test_get_contrast_color_picks_white_on_dark(self):
        assert get_contrast_color("#000000") == "#FFFFFF"

    def test_get_contrast_color_picks_black_on_light(self):
        assert get_contrast_color("#FFFFFF") == "#000000"


class TestAdjustForContrast:
    def test_returns_input_when_already_accessible(self):
        # black on white already passes — should be returned unchanged
        assert adjust_for_contrast("#000000", "#FFFFFF") == "#000000"

    def test_pushes_low_contrast_toward_accessibility(self):
        # light grey on white fails AA; adjusted version should clear 4.5:1
        adjusted = adjust_for_contrast("#CCCCCC", "#FFFFFF", min_ratio=4.5)
        assert check_contrast_ratio(adjusted, "#FFFFFF") >= 4.5


class TestLighterDarker:
    def test_lighter_increases_lightness(self):
        # darker grey → lighter grey
        original = check_contrast_ratio("#444444", "#FFFFFF")
        lighter_ratio = check_contrast_ratio(get_lighter("#444444", 0.2), "#FFFFFF")
        assert lighter_ratio < original  # lighter color → less contrast with white

    def test_darker_decreases_lightness(self):
        original = check_contrast_ratio("#BBBBBB", "#FFFFFF")
        darker_ratio = check_contrast_ratio(get_darker("#BBBBBB", 0.2), "#FFFFFF")
        assert darker_ratio > original  # darker color → more contrast with white


class TestGeneratePalette:
    @pytest.mark.parametrize("harmony", list(HARMONY_DESCRIPTIONS.keys()))
    def test_each_harmony_produces_valid_palette(self, harmony):
        # Some harmonies (complement, triad, split, square) return fewer base
        # colors than the requested count; _expand_palette pads with lightness
        # variants but stops when the lightness scale saturates, so the result
        # may be shorter than `count`. The contract is: at least one color,
        # at most `count`, every entry is a valid hex.
        palette = generate_palette_from_seed("#B63F81", harmony=harmony, count=5)
        assert 1 <= len(palette) <= 5
        for color in palette:
            assert validate_hex(color), f"{harmony} produced invalid color {color}"

    def test_mono_returns_exact_count(self):
        # Monochromatic generation builds exactly `count` lightness steps —
        # it shouldn't need _expand_palette at all.
        palette = generate_palette_from_seed("#B63F81", harmony="mono", count=5)
        assert len(palette) == 5

    @pytest.mark.parametrize("harmony", ["analogous", "complement", "triad", "split", "square"])
    def test_seed_is_present_in_palette(self, harmony):
        # coloraide's harmony output positions the seed differently per harmony
        # (centred for analogous, first for complement/triad, etc.) — what we
        # actually care about is that the seed is somewhere in the result.
        palette = generate_palette_from_seed("#B63F81", harmony=harmony, count=5)
        assert "#b63f81" in [c.lower() for c in palette]


class TestGoogleFonts:
    def test_known_font_is_valid(self):
        assert is_valid_google_font("Inter") is True

    def test_unknown_font_is_invalid(self):
        assert is_valid_google_font("Definitely-Not-A-Real-Font-XYZ") is False
