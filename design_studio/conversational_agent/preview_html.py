"""Render the mobile preview iframe HTML from ``storefront.html`` + draft tokens.

``get_storefront_html()`` loads the template, injects ``storeInfo.theme`` at the boot
marker, then optionally injects a post-render script to outline/scroll tour or focus
selectors (``.sf-tour-highlight``).

Used by ``api_response.preview_payload()`` and publish/restore endpoints.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .config_manager import ConfigManager
from .section_focus import highlight_selectors_for_focus
from .style_repository import StyleRepository
from .token_mapper import tokens_to_preview_theme
from .zone_tour import ZoneTourManager

STOREFRONT_PATH = Path(__file__).parent.parent / "storefront.html"

_THEME_BOOT_MARKER = "/* __SF_THEME_BOOT__ */"
_RENDER_BOOT = "render(storeInfo);"
_TOUR_HIGHLIGHT_MARKER = "/* __SF_TOUR_HIGHLIGHT__ */"


def inject_tour_highlight(
    html: str,
    selectors: list[str],
    *,
    scroll_selector: str | None = None,
) -> str:
    """Outline and scroll to the area being edited in the mobile preview (after render)."""
    if not selectors:
        marker_at = html.find(_TOUR_HIGHLIGHT_MARKER)
        if marker_at >= 0:
            end = html.find(_RENDER_BOOT, marker_at)
            if end >= 0:
                return html[:marker_at] + html[end:]
        return html

    sel_js = json.dumps(selectors)
    scroll_js = json.dumps(scroll_selector or selectors[0] if selectors else None)
    block = (
        f"\n  {_TOUR_HIGHLIGHT_MARKER}\n"
        f"  (function() {{\n"
        f"    document.querySelectorAll('.sf-tour-highlight').forEach((el) => "
        f"el.classList.remove('sf-tour-highlight'));\n"
        f"    document.getElementById('sf-root')?.classList.remove('sf-tour-highlight--page');\n"
        f"    const sels = {sel_js};\n"
        f"    const scrollSel = {scroll_js};\n"
        f"    let scrollTarget = null;\n"
        f"    sels.forEach((sel) => {{\n"
        f"      document.querySelectorAll(sel).forEach((el) => {{\n"
        f"        el.classList.add('sf-tour-highlight');\n"
        f"      }});\n"
        f"    }});\n"
        f"    if (scrollSel) scrollTarget = document.querySelector(scrollSel);\n"
        f"    if (!scrollTarget) {{\n"
        f"      for (const sel of sels) {{\n"
        f"        scrollTarget = document.querySelector(sel);\n"
        f"        if (scrollTarget) break;\n"
        f"      }}\n"
        f"    }}\n"
        f"    if (scrollTarget) {{\n"
        f"      requestAnimationFrame(() => {{\n"
        f"        scrollTarget.scrollIntoView({{ behavior: 'smooth', block: 'center' }});\n"
        f"      }});\n"
        f"    }}\n"
        f"  }})();\n"
    )
    marker_at = html.find(_TOUR_HIGHLIGHT_MARKER)
    render_at = html.find(_RENDER_BOOT)
    if render_at < 0:
        return html
    insert_at = render_at + len(_RENDER_BOOT)
    if marker_at >= 0:
        end = html.find(_RENDER_BOOT, marker_at + 1)
        if end < 0:
            end = insert_at
        while end < len(html) and html[end] in " \t\n;":
            end += 1
        return html[:marker_at] + block + html[end:]
    return html[:insert_at] + block + html[insert_at:]


def inject_theme_into_html(html: str, theme: dict) -> str:
    """Inject draft tokens at the boot marker without altering storefront markup/CSS."""
    theme_js = f"storeInfo.theme = {json.dumps(theme, ensure_ascii=True)};"
    boot_block = (
        f"{_THEME_BOOT_MARKER}\n"
        f"  /* sf-preview-ts:{int(time.time() * 1000)} */\n"
        f"  {theme_js}\n"
        f"  {_RENDER_BOOT}"
    )
    marker_at = html.find(_THEME_BOOT_MARKER)
    if marker_at >= 0:
        render_at = html.find(_RENDER_BOOT, marker_at)
        if render_at >= 0:
            end = render_at + len(_RENDER_BOOT)
            return html[:marker_at] + boot_block + html[end:]
    render_at = html.find(_RENDER_BOOT)
    if render_at >= 0:
        return html[:render_at] + boot_block + html[render_at + len(_RENDER_BOOT) :]
    return html


def get_storefront_html(
    merchant_id: str,
    *,
    focus_zone: str | None = None,
    focus_element_id: str | None = None,
) -> str:
    with open(STOREFRONT_PATH) as f:
        html = f.read()

    cm = ConfigManager(shop_uuid=merchant_id)
    cm.reload()
    repo = StyleRepository(shop_uuid=merchant_id)
    meta = repo.get_effective_meta(merchant_id) if cm.uses_dynamodb else {}
    theme = tokens_to_preview_theme(
        cm.tokens,
        name=cm.tokens.colors.paletteName or "Default Theme",
        description=meta.get("changeSummary", {}).get("humanSummary", "")
        if isinstance(meta.get("changeSummary"), dict)
        else "",
    )
    html = inject_theme_into_html(html, theme)
    tour = ZoneTourManager(merchant_id).progress_dict()
    if tour.get("active"):
        sels = tour.get("highlight_selectors") or []
        scroll_sel = tour.get("highlight_scroll_selector")
    elif focus_zone or focus_element_id:
        sels = highlight_selectors_for_focus(zone=focus_zone, element_id=focus_element_id)
        scroll_sel = sels[0] if sels else None
    else:
        sels = []
        scroll_sel = None
    if sels:
        html = inject_tour_highlight(html, sels, scroll_selector=scroll_sel)
    else:
        html = inject_tour_highlight(html, [])
    return html
