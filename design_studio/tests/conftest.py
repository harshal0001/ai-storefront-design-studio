"""Shared test fixtures — keep persistence out of the design_studio CWD.

Production uses DynamoDB (``USE_DYNAMODB=true``). Tests disable DDB and redirect all
JSON fallback files to pytest ``tmp_path`` via ``DESIGN_STUDIO_DATA_DIR``.
"""

import pytest


@pytest.fixture(autouse=True)
def isolate_persistence(tmp_path, monkeypatch):
    """JSON fallback (when enabled) writes under tmp_path; runtime uses DynamoDB only."""
    monkeypatch.setenv("DESIGN_STUDIO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)
