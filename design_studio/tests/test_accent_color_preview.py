"""RAP-46 / Z1-02 — accent colour must drive links, highlights & prices in the preview."""

from pathlib import Path

from conversational_agent.style_tokens import StyleTokens
from conversational_agent.token_mapper import tokens_to_preview_theme


def test_preview_theme_maps_accent_independently_of_primary():
    tokens = StyleTokens()
    tokens.colors.primary = "#A86B3F"
    tokens.colors.accent = "#0D9488"
    theme = tokens_to_preview_theme(tokens)
    assert theme["primaryColor"] == "#A86B3F"
    assert theme["accentColor"] == "#0D9488"


def test_storefront_css_wires_accent_to_ui_elements_not_only_prices():
    html = Path(__file__).resolve().parents[1].joinpath("storefront.html").read_text()
    accent_rules = [
        ".sf-info-value--link",
        ".sf-section-head__link",
        "border-color: var(--sf-color-accent)",
        ".sf-coupon__btn",
        '[data-price-style="accentColor"]',
    ]
    for needle in accent_rules:
        assert needle in html, f"missing accent wiring: {needle}"

    assert "background: var(--color-pink) !important" in html
    assert html.count("--sf-color-accent") >= 15
