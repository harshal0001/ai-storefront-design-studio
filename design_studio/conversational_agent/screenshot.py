"""Render storefront HTML to PNG for local dev preview captures.

Uses Playwright when installed. ``POST /api/screenshot`` in ``server.py`` for manual
preview exports — not used in the main chat loop.
"""

from __future__ import annotations

import time
from typing import Any


def capture_html_png(html: str, *, width: int = 390, height: int = 900) -> tuple[bytes, int]:
    """Return (png_bytes, elapsed_ms). Raises ImportError or RuntimeError on failure."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(
            "Playwright is required for screenshots. "
            "Run: uv sync --extra screenshot && uv run playwright install chromium"
        ) from e

    started = time.perf_counter()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=2,
            )
            page.set_content(html, wait_until="networkidle", timeout=30_000)
            png = page.screenshot(type="png", full_page=False)
        finally:
            browser.close()

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return png, elapsed_ms


def parse_screenshot_request(body: dict[str, Any]) -> tuple[str, int, int]:
    html = body.get("html") or ""
    if not html.strip():
        raise ValueError("html is required")
    viewport = body.get("viewport") or {}
    width = int(viewport.get("width", 390))
    height = int(viewport.get("height", 900))
    return html, width, height
