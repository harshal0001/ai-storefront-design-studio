"""Integration regression test for the DynamoDB write path (plan item 1.14).

Reproduces the bug where ``save_tokens_with_history`` handed ``TypeSerializer``-
encoded items to a *resource-owned* client, which serialized them again and made
DynamoDB reject the transaction with
``ValidationException: Invalid attribute value type`` — silently blocking every
style edit.

The unit suite runs with ``USE_DYNAMODB=false`` (see ``conftest.py``), so this test
is opt-in: it runs only when DynamoDB Local is reachable on :8001 with the tables
created (``scripts/dynamodb-local-create-tables.sh``); otherwise it skips.
"""

import socket

import pytest

from conversational_agent import style_repository as sr
from conversational_agent.style_tokens import StyleTokens

_ENDPOINT = "http://127.0.0.1:8001"
_SHOP = "pytest-ddb-write-probe"


def _ddb_local_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8001), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.fixture
def ddb_repo(monkeypatch):
    """Point a repository at DynamoDB Local; skip if it (or the table) is absent."""
    if not _ddb_local_reachable():
        pytest.skip("DynamoDB Local not running on :8001")
    monkeypatch.setenv("USE_DYNAMODB", "true")
    monkeypatch.setenv("DYNAMODB_ENDPOINT", _ENDPOINT)
    monkeypatch.setenv("DYNAMODB_ACCESS_KEY_ID", "local")
    monkeypatch.setenv("DYNAMODB_SECRET_ACCESS_KEY", "local")
    repo = sr.StyleRepository(shop_uuid=_SHOP)
    try:
        repo.client.describe_table(TableName=repo.style_table_name)
    except Exception:
        pytest.skip("StorefrontStyle table not created on DynamoDB Local")
    _purge(repo)
    yield repo
    _purge(repo)


def _purge(repo):
    client = repo.client
    resp = client.query(
        TableName=repo.style_table_name,
        KeyConditionExpression="PK = :p",
        ExpressionAttributeValues={":p": {"S": f"MERCHANT#{_SHOP}"}},
    )
    for item in resp.get("Items", []):
        client.delete_item(
            TableName=repo.style_table_name,
            Key={"PK": item["PK"], "SK": item["SK"]},
        )


def test_save_tokens_with_history_writes_to_dynamodb(ddb_repo):
    """A transactional save must succeed and increment the version sequence."""
    v1 = ddb_repo.save_tokens_with_history(
        StyleTokens(),
        shop_uuid=_SHOP,
        change_summary={"zonesTouched": ["Z6"], "humanSummary": "regression probe"},
    )
    assert v1 == 1

    # Second write exercises the undo-stack ConditionExpression branch too.
    v2 = ddb_repo.save_tokens_with_history(StyleTokens(), shop_uuid=_SHOP)
    assert v2 == 2

    draft = ddb_repo.get_draft(_SHOP)
    assert draft is not None
    assert draft["version"] == 2
