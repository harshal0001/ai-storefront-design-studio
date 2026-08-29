"""Agent context builder — page map, blueprint, and live token snapshot.

Used when:
  - The agent calls ``get_storefront_page_context`` tool
  - The server injects context before Bedrock for cross-page requests
  - The server prefixes non-cross-page messages with ``look_and_feel_now``

``PAGE_ZONES`` links Z1–Z6 to preview sections, token fields, and which tools to use.
``is_cross_page_style_request()`` detects whole-storefront asks (italic everywhere, etc.).
"""

from __future__ import annotations

import json
import re
from typing import Any

from .config_manager import ConfigManager
from .storefront_blueprint import build_storefront_blueprint
from .zone_tour import ZoneTourManager

# Friendly zone → preview sections → tools the agent should use
PAGE_ZONES: list[dict[str, Any]] = [
    {
        "code": "Z1",
        "name": "Brand Colours",
        "sections": [
            "Follow button & main accent colour",
            "Page backdrop behind offers & products",
            "Store name / tagline / intro panel backgrounds",
        ],
        "tools": ["apply_zone_tour_choice", "save_theme"],
        "token_fields": ["colors.primary", "colors.accent", "colors.background", "colors.surface"],
        "not_here": ["fonts", "italic", "product layout", "button shape"],
    },
    {
        "code": "Z2",
        "name": "Hero & Header",
        "sections": ["Banner photo", "logo placement", "store name weight", "hero band background"],
        "tools": ["apply_zone_tour_choice", "apply_style_tokens"],
        "token_fields": [
            "hero.layout",
            "hero.overlay",
            "hero.logoPlacement",
            "hero.storeNameStyle",
        ],
        "apply_style_tokens": {
            "hero_overlay": "none|lightScrim|autoScrim|darkScrim",
            "logo_placement": "left|center|right",
            "store_name_style": "subtle|balanced|bold",
        },
    },
    {
        "code": "Z3",
        "name": "Typography",
        "sections": [
            "Intro text",
            "Store information",
            "Opening hours",
            "Font pairing, size scale & text colours (WCAG AA)",
        ],
        "tools": ["apply_zone_tour_choice", "apply_style_tokens"],
        "token_fields": [
            "typography.headingFont",
            "typography.bodyFont",
            "typography.scale",
            "typography.headingStyle",
            "typography.bodyStyle",
            "colors.textPrimary",
            "colors.textSecondary",
        ],
        "apply_style_tokens": {
            "heading_font": "Google Font name",
            "body_font": "Google Font name",
            "font_scale": "compact|standard|generous",
            "heading_style": "normal|italic",
            "body_style": "normal|italic",
        },
        "notes": "Page-wide italic/bold body text → heading_style + body_style on apply_style_tokens.",
    },
    {
        "code": "Z4",
        "name": "Product Cards",
        "sections": [
            "Our Products",
            "All Products & Services",
            "card layout",
            "price accent colour",
        ],
        "tools": ["apply_zone_tour_choice", "apply_style_tokens"],
        "token_fields": ["productCards.*", "zoneScopes.Z4S", "zoneScopes.Z4C"],
        "apply_style_tokens": {
            "product_card_layout": "grid2|grid3|list",
            "product_card_shape": "rounded|sharp|circularImage",
            "price_style": "boldRed|accentColor|understatedGrey|badgePill",
        },
    },
    {
        "code": "Z5",
        "name": "Offer Cards",
        "sections": ["Coupon / offer carousel — platform-managed"],
        "tools": ["acknowledge_offers_zone"],
        "notes": "Merchants cannot restyle offer card layout; image filter only via offer_filter_preset.",
    },
    {
        "code": "Z6",
        "name": "Buttons & CTAs",
        "sections": ["Follow", "coupon buttons", "catalogue CTA"],
        "tools": ["apply_zone_tour_choice", "apply_style_tokens"],
        "token_fields": ["buttons.*", "zoneScopes.Z6"],
        "apply_style_tokens": {
            "button_shape": "sharp|subtleRounded|rounded|pill",
            "button_style": "filled|outlined|soft|ghost",
        },
    },
]

_CROSS_PAGE_RE = re.compile(
    # Whole-storefront phrasing — routed to agent with full blueprint, not direct-style.
    r"(?:\b(?:all|entire|whole|complete|every|full)\s+(?:page|storefront|text|site|store)\b"
    r"|\bpage[- ]?wide\b"
    r"|\b(?:make|set|turn)\s+(?:the\s+)?(?:all\s+)?(?:text|words?|copy)\b"
    r"|\b(?:italic|italics|bold|underline)\b.{0,40}\b(?:everywhere|all|page|storefront)\b"
    r"|\b(?:everywhere|all|page|storefront)\b.{0,40}\b(?:italic|italics|bold)\b)",
    re.I,
)


def is_cross_page_style_request(message: str) -> bool:
    """True when the merchant describes a change across the whole storefront, not one swatch."""
    return bool(_CROSS_PAGE_RE.search(message or ""))


def build_page_context_for_agent(shop_uuid: str) -> dict[str, Any]:
    """Structured page + token snapshot for get_storefront_page_context."""
    cm = ConfigManager(shop_uuid=shop_uuid)
    t = cm.tokens
    mgr = ZoneTourManager(shop_uuid)
    tour = mgr.progress_dict() if mgr.is_active() else {"active": False}

    # Saved brand profile so the agent stays mood-aware across sessions (CF-01 / 3.2).
    repo = cm._repo
    profile = repo.get_style_profile(shop_uuid) if getattr(repo, "enabled", False) else None
    profile = profile or {}
    merchant_profile = {
        "moodTags": profile.get("moodTags", []),
        "audienceTags": profile.get("audienceTags", []),
        "merchantCategory": profile.get("merchantCategory", ""),
    }

    blueprint = build_storefront_blueprint()
    return {
        "page_title": "Mobile storefront (fixed layout — style only, no moving sections)",
        "merchant_profile": merchant_profile,
        "blueprint": blueprint,
        "page_layout_scroll_order": blueprint["page_layout_scroll_order"],
        "theme_application_flow": blueprint["theme_application_flow"],
        "token_to_preview_mapping": blueprint["token_to_preview_mapping"],
        "playbook_examples": blueprint["playbook_examples"],
        "tool_selection_guide": blueprint["tool_selection_guide"],
        "zones": PAGE_ZONES,
        "unsupported_do_not_offer": [
            "underline",
            "strikethrough",
            "moving/hiding sections",
            "custom CSS classes",
        ],
        "current_theme": {
            "name": t.colors.paletteName or cm.config.theme_name,
            "colors": t.colors.model_dump(),
            "typography": t.typography.model_dump(),
            "hero": t.hero.model_dump(),
            "productCards": t.productCards.model_dump(),
            "buttons": t.buttons.model_dump(),
        },
        "zone_tour": tour,
        "workflow": blueprint["colour_scoping_rules"]
        + [
            "Call get_storefront_page_context when unsure — read playbook_examples for similar merchant phrases.",
            "Map request → zone(s) in page_layout_scroll_order → tool from tool_selection_guide.",
            "Apply with apply_style_tokens and/or apply_zone_tour_choice; confirm WHERE in preview.",
            "Never invent underline/strikethrough; never claim page background is impossible.",
        ],
        "look_and_feel_now": _describe_current_look(t),
    }


def _describe_current_look(tokens) -> dict[str, str]:
    """Short human-readable snapshot of current preview styling."""
    c = tokens.colors
    ty = tokens.typography
    h = tokens.hero
    b = tokens.buttons
    pc = tokens.productCards
    return {
        "palette": c.paletteName or "Custom",
        "page_backdrop": c.background,
        "panels_surface": c.surface,
        "primary_accent": f"{c.primary} / {c.accent}",
        "fonts": f"{ty.headingFont} + {ty.bodyFont} ({ty.scale}, heading {ty.headingStyle}, body {ty.bodyStyle})",
        "hero": f"scrim={h.overlay}, logo={h.logoPlacement}, store name={h.storeNameStyle}",
        "products": f"layout={pc.layout}, shape={pc.shape}, prices={pc.priceStyle}",
        "buttons": f"shape={b.shape}, style={b.style}",
    }


def format_page_context_message(shop_uuid: str, user_message: str) -> str:
    """Prefix injected before the agent sees a cross-page merchant message."""
    ctx = build_page_context_for_agent(shop_uuid)
    return (
        "[System: Style request needs full page context. Steps: "
        "(1) You already have snapshot below — map merchant ask to page_layout_scroll_order + zones. "
        "(2) Pick tools from tool_selection_guide / playbook_examples. "
        "(3) apply_style_tokens with exact enums; explain WHERE in preview. "
        "Do NOT invent unsupported styles. Do NOT apply unrelated tokens.\n"
        f"{json.dumps(ctx, indent=2)}\n"
        f"Merchant message: {user_message}]"
    )


def has_explicit_ui_focus(
    *,
    focus_zone: str | None,
    focus_section_id: str | None,
    focus_element_id: str | None,
) -> bool:
    """True when the merchant picked a zone/element in the UI (chip or preview click).

    Used by ``server.chat`` to set ``style_via_agent=True`` so fast-path
    phrase parsers do not silently apply the wrong token field.
    """
    return bool(focus_element_id or focus_section_id or focus_zone)


_ZONE_TOUR_AGENT_HINTS: dict[str, str] = {
    "Z1": (
        "Brand Colours — primary (Follow/brand), accent, page backdrop, intro panels. "
        "Tools: apply_zone_tour_choice(zone_code=Z1, primary_color/accent_color/background_color) "
        "or apply_style_tokens; refresh_zone_tour_options for new swatches."
    ),
    "Z2": (
        "Hero & Header — layout preset (classic_center, modern_left, …) and hero band "
        "background only. Tools: apply_zone_tour_choice(zone_code=Z2, option_id=…) or "
        "apply_style_tokens(hero_layout, hero_overlay, logo_placement, background_color, zone_code=Z2)."
    ),
    "Z3": (
        "Typography — font pairing, font scale (compact/standard/generous), then heading & body "
        "text colours (WCAG AA, contrast on swatches). Tools: apply_zone_tour_choice(zone_code=Z3, "
        "option_id=…) or apply_style_tokens(heading_font, body_font, font_scale, text_color)."
    ),
    "Z4": (
        "Product Cards — Our Products background (Z4S), catalogue background (Z4C), card "
        "layout/shadow, price accent. Tools: apply_zone_tour_choice / apply_style_tokens with "
        "zone_code Z4, Z4S, or Z4C; product_card_layout, product_card_shadow, product_card_shape."
    ),
    "Z5": "Offer Cards — info only; use acknowledge_offers_zone() when they say got it.",
    "Z6": (
        "Buttons & CTAs — button shape/style presets and CTA fill colour. Tools: "
        "apply_zone_tour_choice(zone_code=Z6, option_id=…) or apply_style_tokens(button_shape, "
        "button_style, primary_color/accent_color, zone_code=Z6)."
    ),
}


def format_zone_tour_agent_message(shop_uuid: str, user_message: str) -> str:
    """Agent prompt when CF-05 tour is active and input did not match a preset swatch."""
    from .zone_tour import ZoneTourManager
    from .zone_tour_flow import current_sub_step, tour_enrichment_payload

    mgr = ZoneTourManager(shop_uuid)
    progress = mgr.progress_dict()
    zone = progress.get("current_zone") or ""
    sub_idx = mgr.get_sub_step_index()
    sub = current_sub_step(zone, sub_idx)
    from .zone_dynamic_options import summarize_cached_tour_options

    cached_summary = summarize_cached_tour_options(mgr)
    if not cached_summary and sub:
        flow = tour_enrichment_payload(zone, sub_idx, merchant_id=shop_uuid)
        presets = flow.get("color_options") or flow.get("zone_options") or []
        cached_summary = ", ".join(
            f"{p.get('name', p.get('id', ''))} (id={p.get('id', '')})" for p in presets[:8]
        )
    preset_summary = cached_summary
    ctx = build_page_context_for_agent(shop_uuid)
    sub_kind = sub.kind if sub else "unknown"
    return (
        "[System: Active zone-by-zone customization (CF-05). The merchant typed free-form "
        "feedback instead of clicking a swatch. You decide what to do — do not rely on "
        "keyword matching on the server.\n"
        f"Area: {progress.get('current_zone_name')} ({zone}), sub-step {sub_idx + 1}/"
        f"{progress.get('sub_step_total') or 1}, kind={sub_kind}.\n"
        f"Step focus: {progress.get('step_explanation') or ''}\n"
        f"Chat prompt for this step: {progress.get('current_prompt') or ''}\n"
        f"Zone playbook: {_ZONE_TOUR_AGENT_HINTS.get(zone, '')}\n"
        f"Options shown as chat buttons (ONLY mention these names to the merchant): "
        f"{preset_summary or 'none'}.\n"
        "Actions you may take (any zone, any sub-step):\n"
        "- Merchant wants more / different / stylish options (not to apply yet) → "
        "**refresh_zone_tour_options(user_request=..., option_count=0 or 1–4)**. "
        "Set option_count=1 when they ask for a single extra idea. Then response_type "
        "**zone_tour** with a short intro — do NOT claim you already applied a look.\n"
        "- They pick or name a preset → apply_zone_tour_choice(zone_code=..., option_id=...).\n"
        "- Precise one-off tweak → apply_style_tokens (product_card_layout, product_card_shadow, etc.).\n"
        "- Call get_zone_tour_status() if unsure.\n"
        "- Do NOT list hex codes in the merchant-facing message; use colour names.\n"
        "- **Skip this step** / next sub-step → skip_zone_tour_sub_step (same area).\n"
        "- **Skip this area** → skip_zone_tour_step (whole zone).\n"
        "- Do NOT call complete_zone_tour_step unless they clearly want to skip/finish the whole area.\n"
        f"Page context snapshot: {json.dumps(ctx.get('look_and_feel_now', {}))}\n"
        f"Merchant message: {user_message}]"
    )


def format_focused_style_message(
    shop_uuid: str,
    user_message: str,
    focus,
) -> str:
    """Rich agent prompt when the merchant points at a highlighted preview area."""
    from .section_focus import element_for_id

    ctx = build_page_context_for_agent(shop_uuid)
    el = element_for_id(focus.element_id) if focus.element_id else None
    element_hint = (el or {}).get("agent_hint", "")
    highlight = list(focus.selectors)
    element_line = f", element {focus.element_id}" if focus.element_id else ""
    return (
        "[System: The merchant selected a specific area in the live mobile preview. "
        "Do NOT guess — orchestrate the change with tools:\n"
        "1) Call get_storefront_page_context() to load blueprint, token_to_preview_mapping, "
        "and look_and_feel_now.\n"
        f"2) They are pointing at **{focus.display_label}** (zone {focus.zone}{element_line}). "
        f"Preview highlight selectors: {highlight}\n"
        f"3) Scope hint: {element_hint or 'Apply only tokens that affect this highlighted area.'}\n"
        "4) If they ask for **suggestions / more options / ideas** (no specific colour yet), "
        "the server usually returns **color_options swatches** on the fast path — do NOT "
        "reply with a numbered list of hex codes (#RRGGBB). Use colour **names** only if "
        "you must speak; prefer telling them to pick a swatch below.\n"
        "5) Call apply_style_tokens (or apply_zone_tour_choice) when they name a colour "
        "or pick a swatch. For section background/colour, pass zone_code=<their zone> and "
        "background_color or surface_color — never bare background_color (whole page). "
        "Hero store name / tagline plate → zone_code=Z2, surface_color=#hex. "
        "Hero band behind photo → zone_code=Z2, background_color=#hex. "
        "Example: catalog card 'border radius 0' → product_card_shape=sharp AND border_radius=sharp "
        "(global pill corners also round the card container).\n"
        "6) Confirm what changed and WHERE in the preview. response_type=applied.\n"
        f"Quick snapshot: {json.dumps(ctx.get('look_and_feel_now', {}))}\n"
        f"Merchant message: {user_message}]"
    )
