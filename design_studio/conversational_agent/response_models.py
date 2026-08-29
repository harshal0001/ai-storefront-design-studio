"""Response models for structured agent output.

Pydantic schemas for Strands structured output: ``AgentResponse`` (message + vibe/theme/
color options), ``ZoneTourState``, etc. Used by ``runtime.py`` and optional LLM paths.
Fast-path handlers often return plain dicts via ``api_response`` instead.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class VibeOption(BaseModel):
    """A vibe/mood option for the merchant to choose."""

    name: str = Field(description="Short name like 'Modern & minimal'")
    description: str = Field(description="Brief description of this vibe")


class ThemeColor(BaseModel):
    """A color in a theme package."""

    hex: str = Field(description="Hex color code like #C45B28")
    name: str = Field(description="Creative name like 'Terracotta Sun'")


class ThemePackage(BaseModel):
    """A complete theme package option."""

    name: str = Field(description="Creative theme name like 'Tuscan Workshop'")
    description: str = Field(description="One-line vivid description")
    colors: List[ThemeColor] = Field(description="5 colors for the theme")
    heading_font: str = Field(description="Google Font for headings")
    body_font: str = Field(description="Google Font for body text")
    border_radius: str = Field(description="Shape: sharp, soft, rounded, or pill")
    spacing: str = Field(description="Spacing: compact, normal, or spacious")


class ColorOption(BaseModel):
    """A color option for customizing a zone."""

    name: str = Field(description="Friendly name like 'Sunset Warmth'")
    hex: str = Field(description="Hex color code")
    description: str = Field(description="Brief description")


class ZoneOption(BaseModel):
    """A selectable preset for a zone tour step (non-colour zones)."""

    id: str = Field(description="Stable id e.g. classic_center, soft_grid")
    name: str = Field(description="Friendly label")
    description: str = Field(description="What this option looks like")


class ZoneTourStepState(BaseModel):
    """One step in the zone tour progress bar."""

    code: str = Field(description="Z1 .. Z6")
    name: str = Field(description="Display name")
    info_only: bool = False
    done: bool = False
    skipped: bool = False
    current: bool = False


class ZoneTourProgress(BaseModel):
    """CF-05 zone-by-zone tour state for the UI."""

    active: bool = False
    current_zone: Optional[str] = None
    current_zone_name: Optional[str] = None
    current_headline: Optional[str] = None
    step_index: int = 0
    total_steps: int = 6
    editable_total: int = 5
    editable_completed: int = 0
    can_skip: bool = True
    info_only: bool = False
    z5_message: Optional[str] = None
    steps: Optional[list[ZoneTourStepState]] = None


class AgentResponse(BaseModel):
    """Structured response from the design agent.

    This model is used with Strands' structured_output_model to ensure
    the agent returns properly formatted responses with optional clickable options.
    """

    message: str = Field(description="The conversational message to show the user")
    response_type: str = Field(
        description=(
            "Type: greeting, question, vibe_options, theme_packages, color_options, "
            "zone_tour, applied, or message"
        )
    )
    vibe_options: Optional[List[VibeOption]] = Field(
        default=None, description="Vibe options when asking about mood"
    )
    theme_packages: Optional[List[ThemePackage]] = Field(
        default=None, description="Theme packages to choose from"
    )
    color_options: Optional[List[ColorOption]] = Field(
        default=None, description="Color options for zone customization (Z1 or per-zone accents)"
    )
    # zone_options are injected by the API during CF-05 tour — do not set in LLM output
    zone_tour: Optional[ZoneTourProgress] = Field(
        default=None, description="Zone tour progress when CF-05 walkthrough is active"
    )
