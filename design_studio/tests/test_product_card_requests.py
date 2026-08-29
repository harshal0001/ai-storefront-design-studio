"""Product card fix parsing and application."""

import pytest

from conversational_agent.config_manager import ConfigManager
from conversational_agent.product_card_requests import (
    apply_product_card_fix,
    is_product_card_fix_request,
    parse_product_card_fix_updates,
)


@pytest.fixture(autouse=True)
def _json_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.setenv("DESIGN_STUDIO_DATA_DIR", str(tmp_path))


def test_detects_catalog_rectangle_request():
    msg = (
        "under the ALL PRODUCTS & SERVICES the product cards are looking very bad, "
        "Update them — must be rectangle"
    )
    assert is_product_card_fix_request(msg)
    updates = parse_product_card_fix_updates(msg)
    assert updates["product_card_shape"] == "rounded"
    assert updates["product_card_layout"] == "grid2"


def test_apply_fixes_circular_image_tokens():
    shop = "pc-fix-shop"
    cm = ConfigManager(shop_uuid=shop)
    tokens = cm.tokens.model_copy(deep=True)
    tokens.productCards = tokens.productCards.model_copy(update={"shape": "circularImage"})
    cm.save_tokens(tokens, theme_name="Test")

    msg = "product cards under All Products & Services look bad, information is hidden, make them rectangular"
    applied, summary, updates = apply_product_card_fix(msg, shop_uuid=shop)
    assert applied
    assert updates["product_card_shape"] == "rounded"

    cm.reload()
    assert cm.tokens.productCards.shape == "rounded"
    assert cm.tokens.productCards.layout == "grid2"
