"""Versions dropdown API must include parseable lastModified."""

from conversational_agent.config_manager import ConfigManager
from conversational_agent.server import _version_api_payload


def test_version_payload_includes_last_modified():
    summaries = ConfigManager(shop_uuid="versions-test").list_local_version_summaries()
    payload = _version_api_payload(summaries)
    assert payload["versions"]
    for v in payload["versions"]:
        assert v.get("lastModified")
        assert "T" in v["lastModified"]
