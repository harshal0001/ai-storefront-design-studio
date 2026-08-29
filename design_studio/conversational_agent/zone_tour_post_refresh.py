"""Post-agent safety net when the merchant asked for more options but the cache did not change."""

from __future__ import annotations

from typing import Any

from .zone_dynamic_options import refresh_options_for_current_sub_step
from .zone_tour import ZoneTourManager
from .zone_tour_intent import parse_requested_option_count, user_wants_more_options


def ensure_tour_options_refreshed_if_requested(
    merchant_id: str,
    user_message: str,
    resp: dict[str, Any],
    *,
    option_ids_before: set[str] | None = None,
) -> dict[str, Any]:
    """Refresh swatches when the user asked for more but the agent did not update the cache."""
    if not user_wants_more_options(user_message):
        return resp

    mgr = ZoneTourManager(merchant_id)
    if not mgr.is_active():
        return resp
    step = mgr.current_step()
    if not step or step.info_only:
        return resp

    before_ids = option_ids_before if option_ids_before is not None else mgr.get_cached_option_ids()
    if option_ids_before is not None and mgr.get_cached_option_ids() != before_ids:
        return resp

    requested = parse_requested_option_count(user_message)
    append = requested == 1
    limit = requested if requested is not None else 4

    colors, layouts, packages, lead = refresh_options_for_current_sub_step(
        merchant_id,
        user_message,
        option_limit=limit,
        append=append,
        must_differ_from=before_ids,
    )
    after_ids = mgr.get_cached_option_ids()

    if not (colors or layouts or packages):
        return resp
    if before_ids and after_ids.issubset(before_ids) and len(after_ids) <= len(before_ids):
        return resp

    msg = (resp.get("message") or "").strip()
    if lead and lead not in msg:
        resp["message"] = f"{lead}\n\n{msg}" if msg else lead
    return resp
