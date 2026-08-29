"""Publish API behavior (CF-10 / task 3.11)."""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from conversational_agent import server
from conversational_agent.server import MerchantRequest


def test_publish_returns_503_when_ddb_disabled(monkeypatch):
    repo = MagicMock()
    repo.enabled = False
    monkeypatch.setattr(server, "_repo", lambda merchant_id: repo)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(server.publish(MerchantRequest(merchantId="shop-1")))

    assert exc.value.status_code == 503
    repo.publish_draft.assert_not_called()


def test_publish_returns_400_when_no_draft(monkeypatch):
    repo = MagicMock()
    repo.enabled = True
    repo.publish_draft.return_value = None
    monkeypatch.setattr(server, "_repo", lambda merchant_id: repo)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(server.publish(MerchantRequest(merchantId="shop-1")))

    assert exc.value.status_code == 400
    assert exc.value.detail == "No draft to publish"
    repo.publish_draft.assert_called_once_with("shop-1")


def test_publish_returns_summary_rollback_and_html_on_success(monkeypatch):
    repo = MagicMock()
    repo.enabled = True
    repo.publish_draft.return_value = {
        "SK": "STYLE#PUBLISHED",
        "publishedAt": "2026-05-27T10:00:00Z",
        "rollbackUntil": "2026-06-03T10:00:00Z",
        "changeSummary": {"humanSummary": 'Applied theme "Tuscan Workshop".'},
    }
    monkeypatch.setattr(server, "_repo", lambda merchant_id: repo)
    monkeypatch.setattr(server, "get_storefront_html", lambda merchant_id: "<html>live</html>")

    response = asyncio.run(server.publish(MerchantRequest(merchantId="shop-1")))

    assert response["publishedAt"] == "2026-05-27T10:00:00Z"
    assert response["rollbackUntil"] == "2026-06-03T10:00:00Z"
    assert response["changeSummary"] == 'Applied theme "Tuscan Workshop".'
    assert response["html"] == "<html>live</html>"
    assert "published" in response["message"].lower()


def test_publish_change_summary_is_empty_when_draft_has_none(monkeypatch):
    repo = MagicMock()
    repo.enabled = True
    repo.publish_draft.return_value = {
        "SK": "STYLE#PUBLISHED",
        "publishedAt": "2026-05-27T10:00:00Z",
        "rollbackUntil": "2026-06-03T10:00:00Z",
    }
    monkeypatch.setattr(server, "_repo", lambda merchant_id: repo)
    monkeypatch.setattr(server, "get_storefront_html", lambda merchant_id: "<html></html>")

    response = asyncio.run(server.publish(MerchantRequest(merchantId="shop-1")))

    assert response["changeSummary"] == ""
