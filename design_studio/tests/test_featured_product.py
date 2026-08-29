"""Featured-product toggle (Z4-04) via direct style."""

from conversational_agent.config_manager import ConfigManager
from conversational_agent.direct_style import (
    apply_direct_style_updates,
    parse_direct_style_updates,
)


def test_feature_product_phrases_enable():
    assert parse_direct_style_updates("feature my first product")["featured_enabled"] == "true"
    assert parse_direct_style_updates("highlight a product")["featured_enabled"] == "true"
    assert parse_direct_style_updates("featured product")["featured_enabled"] == "true"


def test_unfeature_phrases_disable():
    assert parse_direct_style_updates("remove featured products")["featured_enabled"] == "false"
    assert parse_direct_style_updates("turn off featured products")["featured_enabled"] == "false"


def test_explicit_featured_style_enum():
    assert parse_direct_style_updates("featured_style=badge")["featured_style"] == "badge"


def test_apply_feature_product_enables_first_card(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.setenv("DESIGN_STUDIO_DATA_DIR", str(tmp_path))
    shop = "z4-featured-test"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="T")

    applied, _, updates = apply_direct_style_updates("feature my first product", shop_uuid=shop)
    assert applied
    assert updates["featured_enabled"] == "true"

    reloaded = ConfigManager(shop_uuid=shop)
    reloaded.reload()
    assert reloaded.tokens.productCards.featured.enabled is True


def test_apply_unfeature_disables(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.setenv("DESIGN_STUDIO_DATA_DIR", str(tmp_path))
    shop = "z4-unfeatured-test"
    cm = ConfigManager(shop_uuid=shop)
    cm.tokens.productCards = cm.tokens.productCards.model_copy(
        update={"featured": cm.tokens.productCards.featured.model_copy(update={"enabled": True})}
    )
    cm.save_tokens(cm.tokens, theme_name="T")

    apply_direct_style_updates("remove featured products", shop_uuid=shop)

    reloaded = ConfigManager(shop_uuid=shop)
    reloaded.reload()
    assert reloaded.tokens.productCards.featured.enabled is False
