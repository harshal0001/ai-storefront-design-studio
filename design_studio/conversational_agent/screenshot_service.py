"""Unified screenshot service — dispatches to local Playwright or AgentCore Browser.

Local dev (SCREENSHOT_BUCKET empty): returns base64 data URL, no S3.
Production (USE_AGENTCORE_BROWSER=true): AgentCore Browser + S3 upload + pre-signed URL.
"""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone


def _get_config():
    return {
        "region": os.environ.get("AWS_REGION", "eu-north-1"),
        "use_agentcore_browser": os.environ.get("USE_AGENTCORE_BROWSER", "false").lower() == "true",
        "bucket": os.environ.get("SCREENSHOT_BUCKET", ""),
        "expiry": int(os.environ.get("SCREENSHOT_URL_EXPIRY", "3600")),
    }


async def capture_and_upload(
    html: str,
    merchant_id: str,
    width: int = 390,
    height: int = 900,
) -> dict:
    """Capture storefront screenshot. Upload to S3 if bucket configured, else return data URL."""
    cfg = _get_config()

    if cfg["use_agentcore_browser"]:
        png_bytes, elapsed_ms = await _capture_agentcore(html, width, height, cfg["region"])
    else:
        import asyncio
        from .screenshot import capture_html_png

        loop = asyncio.get_event_loop()
        png_bytes, elapsed_ms = await loop.run_in_executor(
            None, lambda: capture_html_png(html, width=width, height=height)
        )

    if cfg["bucket"]:
        from .s3_assets import generate_share_url, upload_png

        key = _build_s3_key(merchant_id)
        upload_png(cfg["bucket"], key, png_bytes)
        url = generate_share_url(cfg["bucket"], key, cfg["expiry"])
        return {"url": url, "expiresIn": cfg["expiry"], "timeMs": elapsed_ms}

    b64 = base64.b64encode(png_bytes).decode()
    return {"url": f"data:image/png;base64,{b64}", "expiresIn": None, "timeMs": elapsed_ms}


async def _capture_agentcore(html: str, width: int, height: int, region: str) -> tuple[bytes, int]:
    """Render HTML via AgentCore Browser (Playwright over CDP)."""
    import time
    import urllib.parse

    from bedrock_agentcore.tools.browser_client import browser_session
    from playwright.async_api import async_playwright

    started = time.perf_counter()
    with browser_session(region) as client:
        ws_url, headers = client.generate_ws_headers()

        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(ws_url, headers=headers)
            context = browser.contexts[0]
            page = context.pages[0]
            await page.set_viewport_size({"width": width, "height": height})
            data_url = "data:text/html;charset=utf-8," + urllib.parse.quote(html)
            await page.goto(data_url, wait_until="load", timeout=30_000)
            png = await page.screenshot(type="png", full_page=False)
            await browser.close()

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return png, elapsed_ms


def _build_s3_key(merchant_id: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"screenshots/{merchant_id}/{ts}.png"
