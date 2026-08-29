"""CF-03 — the tour "Surprise me" button must re-roll a fresh option set.

The button (ZoneTourChatBlocks) sends a fixed phrase; these tests pin the contract
that the backend recognises it and regenerates differing swatches for the live step.
"""

from conversational_agent.config_manager import ConfigManager
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_flow import current_sub_step, options_for_sub_step
from conversational_agent.zone_tour_intent import user_wants_more_options
from conversational_agent.zone_tour_post_refresh import (
    ensure_tour_options_refreshed_if_requested,
)

# Keep in sync with the button in frontend/src/components/ZoneTourChatBlocks.jsx
SURPRISE_PHRASE = "Surprise me with different options!"


def test_surprise_phrase_is_recognised_as_more_options():
    assert user_wants_more_options(SURPRISE_PHRASE)


def test_surprise_phrase_refreshes_to_a_different_colour_set(monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "cf03-surprise-button"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    cm.reload()

    mgr = ZoneTourManager(shop)
    mgr.start()
    mgr.advance_sub_step()  # Z1 opens on the palette-package step; move to a colour step
    mgr.ensure_current_sub_step_ready()  # warm the option cache like the live flow does
    zone = mgr.current_step().code
    sub = current_sub_step(zone, mgr.get_sub_step_index())
    assert sub.kind == "colors"

    colors_before, _, _ = options_for_sub_step(zone, sub, shop)
    before = [o["hex"] for o in colors_before]
    before_ids = mgr.get_cached_option_ids()
    assert 4 <= len(colors_before) <= 5  # CF-03 colour count

    ensure_tour_options_refreshed_if_requested(
        shop, SURPRISE_PHRASE, {"type": "zone_tour", "message": ""}, option_ids_before=before_ids
    )

    colors_after, _, _ = options_for_sub_step(zone, sub, shop)
    after = [o["hex"] for o in colors_after]
    assert 4 <= len(colors_after) <= 5
    assert before != after  # a genuinely fresh set
