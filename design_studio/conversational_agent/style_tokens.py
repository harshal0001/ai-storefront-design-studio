"""Style tokens — DynamoDB ``tokens`` blob (see ``DDB_Schema.md``).

Pydantic models mirror the production schema: ``colors``, ``typography``, ``hero``,
``productCards``, ``buttons``, ``geometry``, ``motion``, ``zoneScopes``.

``StyleTokens.from_ddb_map()`` / ``to_ddb_map()`` round-trip DynamoDB attribute shapes.
"""

from typing import Literal, Optional, get_args

from pydantic import BaseModel, Field


class ColorTokens(BaseModel):
    primary: str = "#B63F81"
    accent: str = "#9E3570"
    secondary: str = "#2C2C2C"
    background: str = "#F8F9FA"
    surface: str = "#FFFFFF"
    textPrimary: str = "#3B3B4D"
    textSecondary: str = "#5F6E7D"
    danger: str = "#D72F4D"
    warn: str = "#C34F03"
    success: str = "#0A600A"
    paletteName: str = ""
    harmonyChecked: bool = False
    contrastAA: bool = False


class TypographyTokens(BaseModel):
    headingFont: str = "Montserrat"
    bodyFont: str = "Roboto"
    headingFontFallbackFrom: Optional[str] = None
    scale: Literal["compact", "standard", "generous"] = "standard"
    headingStyle: Literal["normal", "italic"] = "normal"
    bodyStyle: Literal["normal", "italic"] = "normal"
    pairingName: str = ""


class GeometryTokens(BaseModel):
    borderRadiusPreset: Literal["sharp", "soft", "rounded", "pill"] = "rounded"
    spacingPreset: Literal["compact", "normal", "spacious"] = "normal"


VALID_BORDER_RADIUS: set[str] = set(
    get_args(GeometryTokens.model_fields["borderRadiusPreset"].annotation)
)
VALID_SPACING: set[str] = set(get_args(GeometryTokens.model_fields["spacingPreset"].annotation))


class HeroTokens(BaseModel):
    layout: Literal["fullWidth", "splitImageText", "carousel"] = "fullWidth"
    overlay: Literal["none", "lightScrim", "autoScrim", "darkScrim"] = "autoScrim"
    logoPlacement: Literal["left", "center", "right"] = "right"
    taglinePlacement: Literal["none", "center", "bottomLeft", "bottomRight"] = "center"
    storeNameStyle: Literal["subtle", "balanced", "bold"] = "balanced"


class FeaturedProductTokens(BaseModel):
    enabled: bool = False
    style: Literal["largerCard", "differentColor", "badge"] = "largerCard"


class ProductCardTokens(BaseModel):
    shape: Literal["rounded", "sharp", "circularImage"] = "rounded"
    layout: Literal["grid2", "grid3", "list", "featuredPlusGrid"] = "grid2"
    shadow: Literal["flat", "subtle", "elevated", "floating"] = "subtle"
    priceStyle: Literal["boldRed", "accentColor", "understatedGrey", "badgePill"] = "accentColor"
    tapAnimation: Literal["none", "scaleDown", "ripple"] = "scaleDown"
    featured: FeaturedProductTokens = Field(default_factory=FeaturedProductTokens)


class OfferImageBeautification(BaseModel):
    filterPreset: Optional[Literal["warm", "cool", "vivid"]] = "warm"


class OfferCardTokens(BaseModel):
    merchantCanCustomise: bool = False
    imageBeautification: OfferImageBeautification = Field(default_factory=OfferImageBeautification)


class ButtonTokens(BaseModel):
    shape: Literal["sharp", "subtleRounded", "rounded", "pill"] = "rounded"
    style: Literal["filled", "outlined", "soft", "ghost"] = "filled"
    size: Literal["compact", "standard", "large"] = "standard"
    pressAnimation: Literal["none", "darken", "scale", "ripple"] = "scale"


VALID_BUTTON_SHAPE: set[str] = set(get_args(ButtonTokens.model_fields["shape"].annotation))
VALID_BUTTON_STYLE: set[str] = set(get_args(ButtonTokens.model_fields["style"].annotation))
VALID_BUTTON_SIZE: set[str] = set(get_args(ButtonTokens.model_fields["size"].annotation))
VALID_BUTTON_ANIMATION: set[str] = set(
    get_args(ButtonTokens.model_fields["pressAnimation"].annotation)
)


class MotionTokens(BaseModel):
    transition: Literal["none", "fadeTint", "slideTint"] = "fadeTint"


class ZoneColorScope(BaseModel):
    """Optional per-zone colour overrides (section-scoped in preview)."""

    primary: Optional[str] = None
    accent: Optional[str] = None
    background: Optional[str] = None
    surface: Optional[str] = None
    cardFace: Optional[str] = None  # product card faces only (decoupled from section panel)
    textPrimary: Optional[str] = None
    textSecondary: Optional[str] = None


class StyleTokens(BaseModel):
    colors: ColorTokens = Field(default_factory=ColorTokens)
    typography: TypographyTokens = Field(default_factory=TypographyTokens)
    geometry: GeometryTokens = Field(default_factory=GeometryTokens)
    hero: HeroTokens = Field(default_factory=HeroTokens)
    productCards: ProductCardTokens = Field(default_factory=ProductCardTokens)
    offerCards: OfferCardTokens = Field(default_factory=OfferCardTokens)
    buttons: ButtonTokens = Field(default_factory=ButtonTokens)
    motion: MotionTokens = Field(default_factory=MotionTokens)
    zoneScopes: dict[str, ZoneColorScope] = Field(default_factory=dict)

    def to_ddb_map(self) -> dict:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_ddb_map(cls, data: dict | None) -> "StyleTokens":
        if not data:
            return cls()
        return cls.model_validate(data)
