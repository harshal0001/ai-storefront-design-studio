import base64
import binascii
import io
import re

from PIL import Image, UnidentifiedImageError

from .color_engine import is_valid_color, normalize_hex
from .message_parsers import BRAND_PALETTE_TRIGGER_RE, is_brand_palette_request

__all__ = [
    "MAX_IMAGE_BYTES",
    "PALETTE_SIZE",
    "PaletteError",
    "extract_palette",
    "is_brand_palette_request",
    "parse_brand_palette",
]

MAX_IMAGE_BYTES = 5 * 1024 * 1024

PALETTE_SIZE = 6

_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def parse_brand_palette(text: str) -> list[str] | None:
    """Extract a merchant-supplied brand palette (normalised hex list) from chat (Z1-03).

    Returns the de-duplicated colours when the message names a brand palette and has at
    least one valid hex; otherwise ``None`` so single-colour requests use normal handlers.
    """
    if not text or not BRAND_PALETTE_TRIGGER_RE.search(text):
        return None
    seen: set[str] = set()
    palette: list[str] = []
    for raw in _HEX_RE.findall(text):
        if is_valid_color(raw):
            norm = normalize_hex(raw)
            if norm not in seen:
                seen.add(norm)
                palette.append(norm)
    return palette or None


class PaletteError(ValueError):
    """Raised when an uploaded image can't be decoded or is too large."""


def _strip_data_url(data: str) -> str:
    """Drop a leading 'data:image/png;base64,' prefix if present."""
    if data.startswith("data:") and "," in data:
        return data.split(",", 1)[1]
    return data


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def extract_palette(image_b64: str, palette_size: int = PALETTE_SIZE) -> list[str]:
    """Extract dominant colors from a base64-encoded image.

    Args:
        image_b64: Base64 image data, with or without a data-URL prefix.
        palette_size: Max number of dominant colors to return (4-6 per Z1-04).

    Returns:
        Hex color strings ordered most- to least-dominant, e.g. ["#1A2B3C", ...].

    Raises:
        PaletteError: if the payload is too large, not valid base64, or not an image.
    """
    try:
        raw = base64.b64decode(_strip_data_url(image_b64), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PaletteError("Attachment is not valid base64 image data.") from exc

    if not raw:
        raise PaletteError("Attachment is empty.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise PaletteError("Attachment is too large (max 5 MB).")

    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise PaletteError("Attachment could not be read as an image.") from exc

    # Downscale for speed — dominant colors are unaffected by resolution.
    img.thumbnail((200, 200))

    # Median-cut quantization to the requested number of color buckets.
    quantized = img.quantize(colors=palette_size, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()  # flat [r, g, b, r, g, b, ...]

    # Order buckets by pixel count (most dominant first).
    counts = sorted(quantized.getcolors(), key=lambda c: c[0], reverse=True)

    colors: list[str] = []
    seen: set[str] = set()
    for _count, idx in counts:
        rgb = (palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2])
        hex_color = _rgb_to_hex(rgb)
        if hex_color not in seen:
            seen.add(hex_color)
            colors.append(hex_color)

    return colors
