"""Z4 Product Cards tour — price display styles (Z4-03).

Four presets map to ``productCards.priceStyle`` and ``data-price-style`` in the preview.
Sample prices mirror the storefront mock catalogue (``storefront.html`` products).
"""

from __future__ import annotations

from typing import Any

from .zone_dynamic_options import (
    _moods_from_request,
    _normalize_moods,
    load_mood_tags,
)

# Matches mock ``storeInfo.products`` in storefront.html (preview catalogue).
_CATALOG_SAMPLE_PRODUCTS: tuple[dict[str, Any], ...] = (
    {"name": "Cappuccino", "price": 2.0},
    {"name": "Aperol Spritz", "price": 7.0},
    {"name": "Avocado Toast", "price": 11.0},
)

Z4_PRICE_STYLE_PRESETS: list[dict[str, str]] = [
    {
        "id": "z4_price_bold_red",
        "name": "Bold red",
        "price_style": "boldRed",
        "description": "High-contrast **red** prices — bold and sale-forward on every card.",
    },
    {
        "id": "z4_price_accent",
        "name": "Accent colour",
        "price_style": "accentColor",
        "description": "Prices in your **brand accent** — ties offers and CTAs together.",
    },
    {
        "id": "z4_price_understated",
        "name": "Understated grey",
        "price_style": "understatedGrey",
        "description": "**Soft grey** prices — premium, editorial, lets photography lead.",
    },
    {
        "id": "z4_price_badge_pill",
        "name": "Badge pill",
        "price_style": "badgePill",
        "description": "Prices in a **rounded pill** — compact tags that pop on the card.",
    },
]

# Mood ranking: premium → understated; value/bold → bold red (Z4-03 spec).
_PRICE_STYLE_MOOD_MATCH: dict[str, tuple[str, ...]] = {
    "z4_price_bold_red": ("bold", "playful", "value", "modern"),
    "z4_price_accent": ("warm", "cozy", "artisan", "fresh"),
    "z4_price_understated": ("elegant", "premium", "minimal", "classic"),
    "z4_price_badge_pill": ("stylish", "bold", "playful", "warm"),
}

_STAND_OUT_HINTS = frozenset(
    {
        "stand out",
        "standout",
        "pop",
        "bold price",
        "bolder price",
        "more prominent",
        "eye-catching",
    }
)


def _format_catalog_price(amount: float) -> str:
    if amount == int(amount):
        return f"€{int(amount)}"
    return f"€{amount:.2f}"


def catalog_sample_price_line(*, count: int = 2) -> str:
    """Sample prices from the preview catalogue for option cards."""
    parts: list[str] = []
    for row in _CATALOG_SAMPLE_PRODUCTS[:count]:
        parts.append(f"{row['name']} {_format_catalog_price(float(row['price']))}")
    return " · ".join(parts)


def price_style_for_option_id(option_id: str) -> str | None:
    oid = (option_id or "").strip()
    for preset in Z4_PRICE_STYLE_PRESETS:
        if preset["id"] == oid:
            return preset["price_style"]
    return None


def _preset_row_for_apply(preset: dict[str, str]) -> dict[str, str]:
    samples = catalog_sample_price_line()
    desc = f"{preset['description']} " f"Sample on your catalogue: **{samples}**."
    return {
        **preset,
        "description": desc,
        "applies_to": "Price display on **Our Products** and **All Products & Services** cards.",
        "what_changes": desc,
        "sample_prices": samples,
        "section": "Price display style",
    }


def resolve_z4_price_style_choice(
    merchant_id: str,
    *,
    option_id: str = "",
    name: str = "",
) -> dict[str, str] | None:
    """Resolve a price-style swatch from presets, zone option cache, or legacy colour cache."""
    from .zone_tour import ZoneTourManager

    oid = (option_id or "").strip().lower()
    key = (name or "").strip().lower()

    for preset in Z4_PRICE_STYLE_PRESETS:
        if oid and preset["id"].lower() == oid:
            return _preset_row_for_apply(preset)
        if key and preset["name"].lower() == key:
            return _preset_row_for_apply(preset)

    mgr = ZoneTourManager(merchant_id)
    for o in mgr.get_cached_zone_options():
        row = dict(o)
        rid = (row.get("id") or "").lower()
        if oid and rid == oid:
            return row
        if key and (row.get("name") or "").lower() == key:
            return row

    # Pre–Z4-03 tours cached mood accent hex swatches as dyn_z4_prices_* colour options.
    if oid.startswith("dyn_z4_prices"):
        accent = next(p for p in Z4_PRICE_STYLE_PRESETS if p["id"] == "z4_price_accent")
        return _preset_row_for_apply(accent)

    return None


def _boost_rank_for_request(
    presets: list[dict[str, str]],
    user_request: str,
    mood_tags: list[str],
) -> list[dict[str, str]]:
    """Premium → understated first; value/bold or 'stand out' → bold red / badge pill."""
    lower = (user_request or "").lower()
    moods = _normalize_moods(mood_tags)

    def sort_key(p: dict[str, str]) -> tuple[int, int, str]:
        pid = p.get("id", "")
        tags = set(_PRICE_STYLE_MOOD_MATCH.get(pid, ()))
        mood_score = len(moods & {t.lower() for t in tags})
        boost = 0
        if any(h in lower for h in _STAND_OUT_HINTS) or "stand out" in lower:
            if pid == "z4_price_bold_red":
                boost += 5
            elif pid == "z4_price_badge_pill":
                boost += 2
        if moods & {"premium", "elegant", "minimal", "classic"}:
            if pid == "z4_price_understated":
                boost += 2
        if moods & {"bold", "playful", "value"}:
            if pid == "z4_price_bold_red":
                boost += 2
        if "understated" in lower or "subtle" in lower and "price" in lower:
            if pid == "z4_price_understated":
                boost += 4
        if "badge" in lower or "pill" in lower:
            if pid == "z4_price_badge_pill":
                boost += 4
        if "accent" in lower and "price" in lower:
            if pid == "z4_price_accent":
                boost += 4
        if "bold red" in lower or "red price" in lower:
            if pid == "z4_price_bold_red":
                boost += 4
        return (-boost, -mood_score, p.get("name", ""))

    return sorted(presets, key=sort_key)


def recommend_price_style_id(merchant_id: str, *, user_request: str = "") -> str:
    """Top pick for agent copy — mood-aware (premium→understated, value→bold)."""
    mood_tags = _moods_from_request(user_request, load_mood_tags(merchant_id))
    ranked = _boost_rank_for_request(list(Z4_PRICE_STYLE_PRESETS), user_request, mood_tags)
    return ranked[0]["id"] if ranked else Z4_PRICE_STYLE_PRESETS[0]["id"]


def generate_z4_price_style_options(
    merchant_id: str,
    *,
    user_request: str = "",
    batch: int = 0,
    exclude_ids: set[str] | None = None,
    limit: int = 4,
) -> list[dict[str, str]]:
    """Z4-03: four price display styles with catalogue sample prices."""
    mood_tags = _moods_from_request(user_request, load_mood_tags(merchant_id))
    samples = catalog_sample_price_line()
    pool = list(Z4_PRICE_STYLE_PRESETS)
    ranked = _boost_rank_for_request(pool, user_request, mood_tags)
    exclude = {i.lower() for i in (exclude_ids or set()) if i}
    filtered = [p for p in ranked if p.get("id", "").lower() not in exclude]
    if not filtered:
        filtered = ranked
    start = (batch * limit) % max(1, len(filtered))
    out: list[dict[str, str]] = []
    for i in range(min(limit, len(filtered))):
        preset = filtered[(start + i) % len(filtered)]
        desc = f"{preset['description']} " f"Sample on your catalogue: **{samples}**."
        row = {
            **preset,
            "description": desc,
            "applies_to": (
                "Price display on **Our Products** and **All Products & Services** cards."
            ),
            "what_changes": desc,
            "sample_prices": samples,
            "section": "Price display style",
            "generated": "true",
        }
        out.append(row)
    return out


def price_style_recommendation_note(merchant_id: str, *, user_request: str = "") -> str:
    """Short AI-style tip for the tour banner when on ``z4_prices``."""
    mood_tags = _moods_from_request(user_request, load_mood_tags(merchant_id))
    moods = _normalize_moods(mood_tags)
    rec_id = recommend_price_style_id(merchant_id, user_request=user_request)
    rec = next(p for p in Z4_PRICE_STYLE_PRESETS if p["id"] == rec_id)
    if moods & {"premium", "elegant", "minimal"}:
        return (
            f"For a **premium** feel, **{rec['name']}** keeps prices refined — "
            "or say *make prices stand out more* for bolder options."
        )
    if moods & {"bold", "playful", "value"}:
        return (
            f"For a **value-forward** shop, **{rec['name']}** helps prices pop — "
            "pick a swatch to preview on your catalogue items."
        )
    return (
        f"Based on your brand, try **{rec['name']}** first — "
        "each swatch uses sample prices from your catalogue."
    )
