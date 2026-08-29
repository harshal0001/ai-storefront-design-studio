"""Z1-06 colour harmony checks after brand-colour applies (CF-05 / docs Z1-06).

Runs on the in-memory token snapshot *before* persisting a Z1 tour choice. When a
combination fails WCAG or primary/background contrast rules, the apply path can block
the save and return plain-language guidance plus up to three fix swatches.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .color_engine import check_contrast_ratio, is_accessible, normalize_hex
from .style_tokens import StyleTokens

# Spec: block combos with contrast < 3:1 between primary and page background.
_MIN_PRIMARY_BG_RATIO = 3.0


@dataclass(frozen=True)
class HarmonyFix:
    """One suggested colour tweak the merchant can pick next."""

    role: str
    hex: str
    label: str


@dataclass
class HarmonyAssessment:
    ok: bool
    message: str = ""
    fixes: list[HarmonyFix] = field(default_factory=list)
    blocked: bool = False


def assess_brand_colours(tokens: StyleTokens) -> HarmonyAssessment:
    """Evaluate global brand colours for clashes and readability (Z1-06)."""
    c = tokens.colors
    primary = normalize_hex(c.primary)
    background = normalize_hex(c.background)
    surface = normalize_hex(c.surface)
    accent = normalize_hex(c.accent)
    text_primary = normalize_hex(c.textPrimary)

    issues: list[str] = []
    fixes: list[HarmonyFix] = []

    primary_bg = check_contrast_ratio(primary, background)
    if primary_bg < _MIN_PRIMARY_BG_RATIO:
        issues.append(
            f"Your brand colour and page background are too close ({primary_bg:.1f}:1). "
            "Aim for at least 3:1 so the storefront feels distinct."
        )
        fixes.append(
            HarmonyFix(
                "background",
                "#F8F4EF",
                "Warm white backdrop",
            )
        )

    if not is_accessible(text_primary, background, "AA"):
        issues.append("Body text may be hard to read on the page background (WCAG AA).")
        fixes.append(
            HarmonyFix(
                "text_primary",
                "#1F2937",
                "Dark grey text",
            )
        )

    if not is_accessible(text_primary, surface, "AA"):
        issues.append("Text contrast on intro panels may be too low (WCAG AA).")
        fixes.append(
            HarmonyFix(
                "surface",
                "#FFFFFF",
                "White panels",
            )
        )

    primary_accent = check_contrast_ratio(primary, accent)
    if primary_accent < 1.8:
        issues.append(
            f"Brand and accent are very similar ({primary_accent:.1f}:1) — "
            "highlights may not stand out."
        )
        fixes.append(
            HarmonyFix(
                "accent",
                accent,
                "Try a fresher accent on refresh",
            )
        )

    if not issues:
        return HarmonyAssessment(ok=True)

    message = " ".join(issues)
    if primary_bg < _MIN_PRIMARY_BG_RATIO or not is_accessible(text_primary, background, "AA"):
        blocked = True
    else:
        blocked = False

    return HarmonyAssessment(
        ok=False,
        message=message,
        fixes=fixes[:3],
        blocked=blocked,
    )


def _assess_z1_accent(tokens: StyleTokens) -> HarmonyAssessment:
    """Accent sub-step (Z1-02): always save; warn about pairing, never block the tour."""
    c = tokens.colors
    primary = normalize_hex(c.primary)
    background = normalize_hex(c.background)
    accent = normalize_hex(c.accent)

    issues: list[str] = []
    accent_bg = check_contrast_ratio(accent, background)
    if accent_bg < _MIN_PRIMARY_BG_RATIO:
        issues.append(
            f"Accent vs page backdrop is {accent_bg:.1f}:1 — buttons may look subtle. "
            "You can fix the **backdrop** on the next step."
        )
    primary_accent = check_contrast_ratio(primary, accent)
    if primary_accent < 1.8:
        issues.append(
            f"Brand and accent are close ({primary_accent:.1f}:1) — try another accent "
            "or refresh options."
        )

    if not issues:
        return HarmonyAssessment(ok=True)
    return HarmonyAssessment(ok=False, message=" ".join(issues), blocked=False)


def _assess_z1_backdrop(tokens: StyleTokens) -> HarmonyAssessment:
    """Backdrop sub-step (Z1-05): always save the merchant's page choice; warn on remaining clashes."""
    c = tokens.colors
    primary = normalize_hex(c.primary)
    background = normalize_hex(c.background)
    accent = normalize_hex(c.accent)
    text_primary = normalize_hex(c.textPrimary)

    issues: list[str] = []
    primary_bg = check_contrast_ratio(primary, background)
    if primary_bg < _MIN_PRIMARY_BG_RATIO:
        issues.append(
            f"Brand vs page backdrop is {primary_bg:.1f}:1 — aim for 3:1 so the storefront feels distinct. "
            "You can refresh **palette** or pick a bolder brand later."
        )
    if not is_accessible(text_primary, background, "AA"):
        issues.append("Body text may be hard to read on this page backdrop (WCAG AA).")
    primary_accent = check_contrast_ratio(primary, accent)
    if primary_accent < 1.8:
        issues.append(
            f"Brand and accent are close ({primary_accent:.1f}:1) — highlights may not stand out."
        )

    if not issues:
        return HarmonyAssessment(ok=True)
    return HarmonyAssessment(ok=False, message=" ".join(issues), blocked=False)


def assess_brand_colours_for_sub_step(sub_step_id: str, tokens: StyleTokens) -> HarmonyAssessment:
    """Z1-06 checks scoped to the active tour sub-step (accent/backdrop must not block the walkthrough)."""
    if sub_step_id == "z1_accent":
        return _assess_z1_accent(tokens)
    if sub_step_id == "z1_backdrop":
        return _assess_z1_backdrop(tokens)
    return assess_brand_colours(tokens)


def format_harmony_appendix(assessment: HarmonyAssessment) -> str:
    """Merchant-facing paragraph to append after an apply confirmation."""
    if assessment.ok:
        return ""
    lines = [f"**Colour check:** {assessment.message}"]
    if assessment.fixes:
        names = ", ".join(f"**{f.label}**" for f in assessment.fixes[:3])
        lines.append(f"Suggested fixes: {names}. Say which you prefer or ask for new swatches.")
    if assessment.blocked:
        lines.append(
            "This combination was **not saved** — pick a suggested fix or choose another option."
        )
    elif not assessment.ok:
        lines.append(
            "Saved to your preview — use the next Brand Colours step if you want to improve contrast."
        )
    return " ".join(lines)
