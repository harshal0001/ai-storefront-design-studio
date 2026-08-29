"""Build JSON API payloads for the React UI (shared by server and action handlers).

Avoids circular imports: ``zone_tour_actions`` and ``theme_choice_actions`` import from
here instead of ``server.py``.

Key functions:
  - ``preview_payload()`` — HTML, version index, undo/redo flags
  - ``enrich_with_zone_tour()`` — attach active tour + one step of swatch options
  - ``build_tour_response()`` / ``build_tour_finished_response()`` — tour chat replies
  - ``attach_section_focus()`` — merge focus highlights into preview HTML
"""

from __future__ import annotations

import time
from typing import Any

from .config_manager import ConfigManager
from .preview_html import get_storefront_html
from .section_focus import SectionFocus
from .style_repository import StyleRepository
from .zone_catalog import enrich_color_options, enrich_zone_options
from .zone_tour import ZoneTourManager
from .zone_tour_flow import tour_enrichment_payload


def _repo(merchant_id: str) -> StyleRepository:
    return StyleRepository(shop_uuid=merchant_id)


def version_state(merchant_id: str) -> tuple[int, int]:
    repo = _repo(merchant_id)
    if not repo.enabled:
        cm = ConfigManager(shop_uuid=merchant_id)
        return cm.version_index()
    summaries = repo.list_version_summaries(merchant_id)
    if not summaries:
        return 0, 1
    current_idx = next(
        (i for i, s in enumerate(summaries) if s.get("isCurrent")),
        len(summaries) - 1,
    )
    return current_idx, len(summaries)


def undo_redo_flags(merchant_id: str) -> dict[str, bool]:
    repo = _repo(merchant_id)
    if repo.enabled:
        return {
            "canUndo": repo.can_undo(merchant_id),
            "canRedo": repo.can_redo(merchant_id),
        }
    cm = ConfigManager(shop_uuid=merchant_id)
    return {"canUndo": cm.can_undo(), "canRedo": cm.can_redo()}


def preview_payload(
    merchant_id: str,
    html: str | None = None,
    *,
    focus_zone: str | None = None,
    focus_element_id: str | None = None,
) -> dict[str, Any]:
    """HTML + version index + undo/redo capability flags for the UI."""
    if html is None:
        html = get_storefront_html(
            merchant_id,
            focus_zone=focus_zone,
            focus_element_id=focus_element_id,
        )
    version, total = version_state(merchant_id)
    cm = ConfigManager(shop_uuid=merchant_id)
    cm.reload()
    return {
        "html": html,
        "previewTs": int(time.time() * 1000),
        "themePrimary": cm.tokens.colors.primary,
        "version": version,
        "totalVersions": total,
        **undo_redo_flags(merchant_id),
    }


def enrich_with_zone_tour(resp: dict[str, Any], merchant_id: str) -> dict[str, Any]:
    """Attach live zone tour progress and one chat step of options (CF-05)."""
    mgr = ZoneTourManager(merchant_id)
    progress = mgr.progress_dict()
    if not progress.get("active"):
        return resp

    resp["zone_tour"] = progress
    zone = progress.get("current_zone")
    sub_idx = mgr.get_sub_step_index()

    if progress.get("info_only"):
        from .zone_highlight import SUB_STEP_HIGHLIGHTS

        z5 = SUB_STEP_HIGHLIGHTS["z5_info"]
        progress.update(z5.to_api_dict())
        if progress.get("z5_message") and not resp.get("message"):
            resp["message"] = progress["z5_message"]
        resp["type"] = resp.get("type") or "zone_tour"
        return resp

    flow = tour_enrichment_payload(zone, sub_idx, merchant_id=merchant_id)
    if flow.get("color_options"):
        resp["color_options"] = enrich_color_options(zone, flow["color_options"])
    if flow.get("zone_options"):
        resp["zone_options"] = enrich_zone_options(zone, flow["zone_options"])
    if flow.get("theme_packages"):
        resp["theme_packages"] = flow["theme_packages"]
    if flow.get("color_options") or flow.get("zone_options") or flow.get("theme_packages"):
        if resp.get("type") in (None, "message"):
            resp["type"] = "zone_tour"
        if not resp.get("message") and flow.get("current_prompt"):
            resp["message"] = flow["current_prompt"]
    return resp


def attach_section_focus(
    resp: dict[str, Any],
    merchant_id: str,
    focus: SectionFocus | None,
) -> dict[str, Any]:
    """Merge preview HTML with highlight + section_focus metadata."""
    zone = focus.zone if focus else None
    element_id = focus.element_id if focus else None
    html = get_storefront_html(merchant_id, focus_zone=zone, focus_element_id=element_id)
    resp.update(
        preview_payload(
            merchant_id,
            html=html,
            focus_zone=zone,
            focus_element_id=element_id,
        )
    )
    if focus:
        resp["section_focus"] = focus.to_api_dict()
    return resp


def build_tour_response(merchant_id: str, message: str) -> dict[str, Any]:
    resp: dict[str, Any] = {
        "type": "zone_tour",
        "message": message,
        **preview_payload(merchant_id),
    }
    return enrich_with_zone_tour(resp, merchant_id)


def build_tour_finished_response(
    merchant_id: str,
    message: str,
    *,
    status: str = "completed",
) -> dict[str, Any]:
    """Tour ended — tell the UI to remove the live panel (active: false)."""
    return {
        "type": "message",
        "message": message,
        "zone_tour": {"active": False, "status": status},
        **preview_payload(merchant_id),
    }


def build_applied_response(
    merchant_id: str,
    message: str,
    *,
    response_type: str = "applied",
) -> dict[str, Any]:
    return enrich_with_zone_tour(
        {"type": response_type, "message": message, **preview_payload(merchant_id)},
        merchant_id,
    )


def version_api_payload(summaries: list[dict]) -> dict[str, Any]:
    return {
        "versions": [
            {
                "versionId": s["versionId"],
                "versionSeq": s.get("versionSeq", s["versionId"]),
                "label": s["label"],
                "lastModified": s.get("lastModified"),
                "isCurrent": s["isCurrent"],
            }
            for s in summaries
        ]
    }
