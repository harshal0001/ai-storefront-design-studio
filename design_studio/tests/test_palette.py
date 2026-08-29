"""Photo-to-palette extraction (Z1-04) — palette.extract_palette + build_palette_prompt."""

import base64
import io

import pytest
from PIL import Image

from conversational_agent.palette import PaletteError, extract_palette
from conversational_agent.server import build_palette_prompt


def _png_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_extract_palette_solid_image_returns_that_colour():
    b64 = _png_b64(Image.new("RGB", (40, 40), (26, 43, 60)))  # #1A2B3C
    colors = extract_palette(b64)
    assert colors[0] == "#1A2B3C"


def test_extract_palette_strips_data_url_prefix():
    b64 = _png_b64(Image.new("RGB", (32, 32), (255, 0, 0)))
    colors = extract_palette("data:image/png;base64," + b64)
    assert colors[0] == "#FF0000"


def test_extract_palette_orders_by_dominance():
    img = Image.new("RGB", (40, 40), (255, 255, 255))  # mostly white
    for x in range(10):
        for y in range(10):
            img.putpixel((x, y), (255, 0, 0))  # small red block
    colors = extract_palette(_png_b64(img))
    assert colors[0] == "#FFFFFF"  # white dominates
    assert "#FF0000" in colors


def test_extract_palette_invalid_base64_raises():
    with pytest.raises(PaletteError):
        extract_palette("!!!not-valid-base64!!!")


def test_extract_palette_non_image_bytes_raises():
    not_image = base64.b64encode(b"this is plain text, not an image").decode()
    with pytest.raises(PaletteError):
        extract_palette(not_image)


def test_build_palette_prompt_includes_colours_and_asks_for_packages():
    prompt = build_palette_prompt(["#1A2B3C", "#FFFFFF"], "make it cozy")
    assert "#1A2B3C" in prompt and "#FFFFFF" in prompt
    assert "theme_packages" in prompt
    assert "cozy" in prompt  # merchant message carried into the prompt
