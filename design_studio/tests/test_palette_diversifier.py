"""Safety net that keeps theme-package palettes distinct (palette_diversifier)."""

import copy

from conversational_agent.palette_diversifier import (
    diversify_theme_packages,
    palettes_too_similar,
)


def _pkg(name: str, hexes: list[str]) -> dict:
    return {
        "name": name,
        "description": f"{name} description",
        "colors": [{"name": f"{name} {i}", "hex": h} for i, h in enumerate(hexes)],
        "heading_font": "Playfair Display",
        "body_font": "Lato",
        "border_radius": "rounded",
        "spacing": "normal",
    }


_SHARED = ["#C45B28", "#FAF8F5", "#556B2F", "#8B7355", "#E8DCC4"]


def test_identical_palettes_flagged_as_too_similar():
    packages = [_pkg("A", _SHARED), _pkg("B", _SHARED), _pkg("C", _SHARED)]
    assert palettes_too_similar(packages) is True


def test_distinct_palettes_not_flagged():
    packages = [
        _pkg("Dark", ["#3B1F2B", "#1A1014", "#6B2D3C", "#A85666", "#2C1A20"]),
        _pkg("Light", ["#C8A24B", "#FBF6E9", "#E3C879", "#9A7B2E", "#F2E4BD"]),
        _pkg("Jewel", ["#1F4D45", "#0E2622", "#2E7D6B", "#5BB39E", "#143832"]),
    ]
    assert palettes_too_similar(packages) is False


def test_diversify_makes_similar_palettes_distinct():
    packages = [_pkg("A", _SHARED), _pkg("B", _SHARED), _pkg("C", _SHARED)]
    result = diversify_theme_packages(packages)

    assert len(result) == 3
    # After diversifying the palettes should no longer be near-identical.
    assert palettes_too_similar(result) is False
    # First package is left untouched (keeps a fully model-authored palette).
    assert [c["hex"] for c in result[0]["colors"]] == _SHARED
    # Later packages were changed.
    assert [c["hex"] for c in result[1]["colors"]] != _SHARED
    assert [c["hex"] for c in result[2]["colors"]] != _SHARED


def test_diversify_preserves_names_fonts_and_count():
    packages = [_pkg("A", _SHARED), _pkg("B", _SHARED)]
    result = diversify_theme_packages(packages)

    pkg_b = result[1]
    assert pkg_b["heading_font"] == "Playfair Display"
    assert pkg_b["body_font"] == "Lato"
    assert pkg_b["border_radius"] == "rounded"
    assert len(pkg_b["colors"]) == len(_SHARED)
    # Creative colour names are retained, mapped onto the new hexes.
    assert [c["name"] for c in pkg_b["colors"]] == [f"B {i}" for i in range(len(_SHARED))]


def test_diversify_noop_for_already_distinct_palettes():
    packages = [
        _pkg("Dark", ["#3B1F2B", "#1A1014", "#6B2D3C", "#A85666", "#2C1A20"]),
        _pkg("Light", ["#C8A24B", "#FBF6E9", "#E3C879", "#9A7B2E", "#F2E4BD"]),
    ]
    original = copy.deepcopy(packages)
    result = diversify_theme_packages(packages)
    assert result == original


def test_diversify_noop_for_single_package():
    packages = [_pkg("Solo", _SHARED)]
    original = copy.deepcopy(packages)
    assert diversify_theme_packages(packages) == original
