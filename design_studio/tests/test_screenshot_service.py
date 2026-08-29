"""Tests for screenshot_service — unified capture + S3 upload."""

import asyncio
import base64
from unittest.mock import patch

import pytest

from conversational_agent.screenshot_service import (
    _build_s3_key,
    capture_and_upload,
)


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch):
    monkeypatch.setenv("USE_AGENTCORE_BROWSER", "false")
    monkeypatch.setenv("SCREENSHOT_BUCKET", "")
    monkeypatch.setenv("SCREENSHOT_URL_EXPIRY", "3600")


FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _run(coro):
    return asyncio.run(coro)


class TestLocalFallback:
    def test_returns_data_url_when_no_bucket(self, monkeypatch):
        monkeypatch.setenv("SCREENSHOT_BUCKET", "")

        with patch(
            "conversational_agent.screenshot.capture_html_png",
            return_value=(FAKE_PNG, 42),
        ):
            result = _run(capture_and_upload("<html></html>", "shop-1"))

        assert result["url"].startswith("data:image/png;base64,")
        assert result["expiresIn"] is None
        assert result["timeMs"] == 42
        decoded = base64.b64decode(result["url"].split(",")[1])
        assert decoded == FAKE_PNG


class TestS3Upload:
    def test_uploads_and_returns_presigned_url(self, monkeypatch):
        monkeypatch.setenv("SCREENSHOT_BUCKET", "my-bucket")
        monkeypatch.setenv("SCREENSHOT_URL_EXPIRY", "900")

        with patch(
            "conversational_agent.screenshot.capture_html_png",
            return_value=(FAKE_PNG, 55),
        ):
            with patch("conversational_agent.s3_assets.upload_png") as mock_upload:
                with patch(
                    "conversational_agent.s3_assets.generate_share_url",
                    return_value="https://s3.amazonaws.com/my-bucket/screenshots/shop-1/xxx.png?X-Amz-Signature=abc",
                ) as mock_url:
                    result = _run(capture_and_upload("<html></html>", "shop-1"))

        assert result["url"].startswith("https://s3.amazonaws.com/")
        assert result["expiresIn"] == 900
        assert result["timeMs"] == 55
        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        assert call_args[0][0] == "my-bucket"
        assert "screenshots/shop-1/" in call_args[0][1]
        assert call_args[0][2] == FAKE_PNG
        mock_url.assert_called_once_with("my-bucket", call_args[0][1], 900)


class TestS3Key:
    def test_key_contains_merchant_id(self):
        key = _build_s3_key("merchant-abc")
        assert key.startswith("screenshots/merchant-abc/")
        assert key.endswith(".png")

    def test_different_merchants_get_different_prefixes(self):
        key1 = _build_s3_key("shop-1")
        key2 = _build_s3_key("shop-2")
        assert "shop-1" in key1
        assert "shop-2" in key2
        assert key1 != key2
