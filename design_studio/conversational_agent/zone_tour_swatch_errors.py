"""User-facing hints when a tour swatch click could not be resolved."""

from __future__ import annotations

from .zone_tour_types import ZoneSubStep

# Sub-steps that always force-refresh optionCache before resolving a click.
FORCE_REFRESH_SUB_STEPS = frozenset(
    {"z4_prices", "z1_accent", "z1_motion", "z3_text_colour", "z6_cta_colour"}
)


def should_force_refresh_options(sub: ZoneSubStep, option_id: str) -> bool:
    """True when cache is likely stale for this click."""
    if sub.id in FORCE_REFRESH_SUB_STEPS:
        return True
    lower = option_id.lower()
    return lower.startswith("z3_txt_") or lower.startswith("dyn_z6_cta_colour_")


def swatch_failure_hint(option_id: str, sub: ZoneSubStep) -> str:
    """Short message when ``zone option <id>`` did not resolve."""
    oid = (option_id or "").lower()

    if oid.startswith("z1_acc_") and sub.id == "z1_palette":
        return (
            "That accent is for **step 2** — pick a **palette card** first, "
            "or say *skip this step* if your brand colours are already set."
        )
    if sub.id == "z4_prices":
        return (
            "I couldn't apply that swatch — the options may have refreshed. "
            "**Click one of the price display styles** shown now (Bold red, "
            "Accent colour, Understated grey, or Badge pill), or describe what you want."
        )
    if oid.startswith("z1_acc_"):
        return (
            "I couldn't apply that accent — please **click the same swatch again** "
            "(under the latest tour message), or say *more accent options*."
        )
    if oid.startswith("z1_motion_"):
        return (
            "I couldn't apply that transition — click **Fade**, **Slide-tint**, or **None** "
            "under the latest tour message, or say *no page animation*."
        )
    if oid.startswith("z3_txt_"):
        return (
            "I couldn't apply that text colour — use the **latest** heading or body swatches "
            "in chat (after you pick heading colour, new body swatches appear). "
            "Or say *darker* / *warmer* for more options."
        )
    if oid.startswith("dyn_z6_cta_colour_") or sub.id == "z6_cta_colour":
        return (
            "I couldn't apply that CTA colour — click **Sunset**, **Honey**, or another swatch "
            "under the latest tour message, or name a colour (e.g. *berry*, *navy*)."
        )
    return (
        "I couldn't apply that swatch — please **click the same button again** "
        "or describe the colour you want in the box below."
    )
