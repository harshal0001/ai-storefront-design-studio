"""Shared types for the zone-by-zone customization tour."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StepKind = Literal["colors", "layouts", "palettes"]


@dataclass(frozen=True)
class ZoneSubStep:
    """One question within a tour zone (e.g. Z1 accent, Z3 text colour)."""

    id: str
    prompt: str
    kind: StepKind
    option_ids: tuple[str, ...] = ()
    highlight: str = ""  # preview focus: Z2, Z4S, Z4C, Z1, …
