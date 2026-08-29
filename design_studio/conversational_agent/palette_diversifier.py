"""Keep theme-package palettes visually distinct while staying on the chosen vibe.

In structured-output mode Nova Pro frequently reuses a single palette across all
theme packages, even though ``system_prompt.md`` asks it to call
``generate_color_palette`` per package with different seeds and harmonies. That
produces the "all three options look the same" problem.

This module is a deterministic safety net. When the palettes the model returned
are near-identical, it regenerates the *later* packages from the first package's
dominant (most chromatic) colour — spreading the hue a little and rotating the
harmony per package. The result reads as the same family/vibe but with clearly
different options. The first package is left untouched so at least one fully
model-authored palette survives, and each package keeps its creative colour
names, fonts, shape and spacing.
"""

from __future__ import annotations

import itertools
import math
from typing import Any

from coloraide import Color

from .color_engine import generate_palette_from_seed

# Per-package recipe (index 0 is left untouched). We deliberately avoid
# complement/triad harmonies here: pulling in the opposite hue (e.g. a blue into a
# warm "luxurious" set) maximises difference but breaks the chosen vibe. Instead we
# stay in the same colour family and separate options by:
#   - hue: a modest shift within the family,
#   - mood: lighter/airier vs darker/moodier (lightness nudge on the seed),
#   - structure: an analogous spread vs a single-hue (mono) ramp.
_HARMONY_CYCLE = ["analogous", "analogous", "mono", "analogous"]

# Hue offsets (degrees) per package — small enough to stay on-vibe, large enough
# that the options are easy to tell apart.
_HUE_OFFSETS = [0.0, 30.0, -30.0, 60.0]

# Lightness nudge per package (OKLCH) — gives each option a distinct light/dark mood.
_LIGHTNESS_MOODS = [0.0, -0.10, 0.10, -0.05]

# Average pairwise swatch distance (CIEDE2000) below which we treat palettes as
# "too similar" and regenerate. ~10 is barely perceptible; >25 is clearly distinct.
_SIMILARITY_THRESHOLD = 14.0


def _hexes(pkg: dict[str, Any]) -> list[str]:
    return [c.get("hex", "") for c in pkg.get("colors", []) if c.get("hex")]


def _safe_oklch(hex_color: str) -> Color | None:
    try:
        return Color(hex_color).convert("oklch")
    except Exception:
        return None


def _dominant_seed(pkg: dict[str, Any]) -> str | None:
    """Pick the most chromatic, mid-lightness colour as the family seed.

    Avoids near-white/near-black neutrals so the regenerated palette is anchored
    on the package's actual brand hue rather than a background swatch.
    """
    best: str | None = None
    best_chroma = -1.0
    for hex_color in _hexes(pkg):
        oklch = _safe_oklch(hex_color)
        if oklch is None:
            continue
        lightness = oklch["lightness"] or 0.0
        chroma = oklch["chroma"] or 0.0
        if 0.12 < lightness < 0.92 and chroma > best_chroma:
            best_chroma = chroma
            best = hex_color
    if best is not None:
        return best
    hexes = _hexes(pkg)
    return hexes[0] if hexes else None


def _color_distance(a: str, b: str) -> float:
    try:
        return Color(a).delta_e(b, method="2000")
    except Exception:
        return 100.0


def _avg_nearest_distance(p1: list[str], p2: list[str]) -> float:
    """Position-agnostic palette distance: mean nearest-swatch CIEDE2000."""
    if not p1 or not p2:
        return 100.0
    return sum(min(_color_distance(c, d) for d in p2) for c in p1) / len(p1)


def palettes_too_similar(
    packages: list[dict[str, Any]],
    threshold: float = _SIMILARITY_THRESHOLD,
) -> bool:
    """True when, on average, theme-package palettes are near-identical."""
    palettes = [p for p in (_hexes(pkg) for pkg in packages) if p]
    if len(palettes) < 2:
        return False
    diffs = [_avg_nearest_distance(p1, p2) for p1, p2 in itertools.combinations(palettes, 2)]
    if not diffs:
        return False
    return (sum(diffs) / len(diffs)) < threshold


def _shift_seed(hex_color: str, degrees: float, lightness_delta: float) -> str:
    """Rotate the seed hue within its family and nudge its light/dark mood."""
    oklch = _safe_oklch(hex_color)
    if oklch is None:
        return hex_color
    hue = oklch["hue"]
    if hue is None or (isinstance(hue, float) and math.isnan(hue)):
        hue = 0.0
    oklch["hue"] = (hue + degrees) % 360
    lightness = oklch["lightness"] or 0.5
    oklch["lightness"] = max(0.18, min(0.85, lightness + lightness_delta))
    return oklch.convert("srgb").clip().to_string(hex=True)


def _pad_palette(hexes: list[str], count: int) -> list[str]:
    """Guarantee exactly ``count`` swatches by adding lightness variants.

    Some harmonies (e.g. complement) yield fewer base colours than requested and
    the engine's expander stops once lightness saturates. We top up by nudging the
    lightness of existing colours so the card always shows a full row of swatches.
    """
    result = list(hexes)
    if not result:
        return result
    i = 0
    while len(result) < count:
        base = hexes[i % len(hexes)]
        oklch = _safe_oklch(base)
        if oklch is None:
            result.append(base)
        else:
            direction = 1 if (len(result) % 2 == 0) else -1
            step = 0.12 * (1 + (len(result) - len(hexes)) // max(1, len(hexes)))
            lightness = oklch["lightness"] or 0.5
            oklch["lightness"] = max(0.08, min(0.95, lightness + direction * step))
            result.append(oklch.convert("srgb").clip().to_string(hex=True))
        i += 1
    return result[:count]


def _remap_names(names: list[str], hexes: list[str]) -> list[dict[str, str]]:
    """Keep the model's evocative colour names, mapped onto the new hexes."""
    out: list[dict[str, str]] = []
    for idx, hex_color in enumerate(hexes):
        name = names[idx] if idx < len(names) and names[idx] else f"Shade {idx + 1}"
        out.append({"name": name, "hex": hex_color})
    return out


def diversify_theme_packages(
    packages: list[dict[str, Any]],
    *,
    threshold: float = _SIMILARITY_THRESHOLD,
) -> list[dict[str, Any]]:
    """Regenerate near-duplicate palettes so options are distinct but on-vibe.

    No-op when fewer than two packages or when the palettes are already
    sufficiently different. Mutates and returns ``packages``.
    """
    if not packages or len(packages) < 2:
        return packages
    if not palettes_too_similar(packages, threshold):
        return packages

    anchor = _dominant_seed(packages[0])
    if not anchor:
        return packages

    for i in range(1, len(packages)):
        pkg = packages[i]
        names = [c.get("name", "") for c in pkg.get("colors", [])]
        count = len(names) if names else 5
        seed = _shift_seed(
            anchor,
            _HUE_OFFSETS[i % len(_HUE_OFFSETS)],
            _LIGHTNESS_MOODS[i % len(_LIGHTNESS_MOODS)],
        )
        harmony = _HARMONY_CYCLE[i % len(_HARMONY_CYCLE)]
        new_hexes = _pad_palette(generate_palette_from_seed(seed, harmony, count), count)
        pkg["colors"] = _remap_names(names, new_hexes)

    return packages
