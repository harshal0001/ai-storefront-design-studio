"""Tests for the Bedrock-free @tool functions.

Tools that mutate ConfigManager state (`save_theme`, `customize_zone`, etc.)
are exercised end-to-end via the agent loop and need AWS credentials — those
belong in an integration-test layer, not here.
"""

from conversational_agent.constants import GOOGLE_FONTS_BY_CATEGORY
from conversational_agent.tools import (
    check_color_accessibility,
    get_available_fonts,
    get_harmony_types,
    list_theme_packages,
    rank_packages_by_mood,
    validate_color_and_get_info,
    validate_font,
)


class TestRankPackagesByMood:
    def test_orders_by_mood_overlap(self):
        packages = [
            {"packageId": "a", "moodMatch": ["sleek", "modern"]},
            {"packageId": "b", "moodMatch": ["warm", "rustic", "artisan"]},
            {"packageId": "c", "moodMatch": []},
        ]
        ranked = rank_packages_by_mood(packages, ["Warm", "Artisan"])
        assert [p["packageId"] for p in ranked] == ["b", "a", "c"]

    def test_ties_keep_original_order(self):
        packages = [
            {"packageId": "a", "moodMatch": ["warm"]},
            {"packageId": "b", "moodMatch": ["warm"]},
        ]
        ranked = rank_packages_by_mood(packages, ["warm"])
        assert [p["packageId"] for p in ranked] == ["a", "b"]

    def test_no_tags_returns_original_order(self):
        packages = [{"packageId": "a"}, {"packageId": "b"}]
        assert rank_packages_by_mood(packages, []) == packages


class TestValidateColorAndGetInfo:
    def test_valid_color_returns_info(self):
        out = validate_color_and_get_info("#B63F81")
        assert "Valid color" in out
        assert "#b63f81" in out.lower()
        assert "Best text color" in out

    def test_invalid_color_is_flagged(self):
        out = validate_color_and_get_info("not-a-color")
        assert "Invalid" in out


class TestCheckColorAccessibility:
    def test_black_on_white_passes_aa_and_aaa(self):
        out = check_color_accessibility("#000000", "#FFFFFF")
        assert "Pass" in out
        # max contrast is 21:1
        assert "21" in out

    def test_low_contrast_fails_and_suggests_adjustment(self):
        out = check_color_accessibility("#CCCCCC", "#FFFFFF")
        assert "Fail" in out
        assert "Suggested adjustment" in out

    def test_invalid_input_is_rejected(self):
        assert "Invalid" in check_color_accessibility("nope", "#FFFFFF")


class TestGetHarmonyTypes:
    def test_lists_all_known_harmonies(self):
        out = get_harmony_types()
        for harmony in ("analogous", "complement", "triad", "split", "square", "mono"):
            assert harmony in out


class TestGetAvailableFonts:
    """Regression test for the fonts.json wiring fix.

    Before the fix, get_available_fonts returned a hardcoded subset (~20
    fonts in 3 categories). After the fix it should surface everything in
    fonts.json (~83 fonts across 5 categories).
    """

    def test_surfaces_all_fonts_json_categories(self):
        out = get_available_fonts()
        # All five category keys from fonts.json should appear (in either the
        # original "sans-serif" form or the capitalised display form).
        for category in GOOGLE_FONTS_BY_CATEGORY.keys():
            label = category.replace("-", " ").capitalize()
            assert label in out, f"category {category!r} missing from output"

    def test_lists_known_font_from_each_category(self):
        out = get_available_fonts()
        # One representative font from each category that should always be present
        for font in ("Inter", "Merriweather", "Bebas Neue"):
            assert font in out, f"expected font {font!r} not surfaced"


class TestValidateFont:
    def test_accepts_known_font(self):
        out = validate_font("Inter")
        assert "available" in out.lower()

    def test_rejects_unknown_font(self):
        out = validate_font("Definitely-Not-A-Real-Font-XYZ")
        assert "not found" in out.lower()

    def test_suggests_similar_when_close(self):
        # "Roboto" is in the whitelist; partial match should be suggested
        out = validate_font("Robot")
        assert "Roboto" in out


class TestThemePackages:
    def test_disabled_catalogue_message_references_use_dynamodb(self, monkeypatch):
        monkeypatch.setenv("USE_DYNAMODB", "false")

        out = list_theme_packages()

        assert "USE_DYNAMODB=false" in out
        assert "DYNAMODB_ENDPOINT" not in out
