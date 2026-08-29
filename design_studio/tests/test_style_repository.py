"""Tests for StyleRepository DynamoDB helpers."""

from unittest.mock import MagicMock

import pytest

from conversational_agent.style_repository import StyleRepository
from conversational_agent.style_tokens import StyleTokens


@pytest.fixture(autouse=True)
def _use_dynamodb(monkeypatch):
    """Suite defaults to USE_DYNAMODB=false (conftest); these tests mock the DDB path."""
    monkeypatch.setenv("USE_DYNAMODB", "true")


def _tokens(primary: str = "#B63F81") -> StyleTokens:
    tokens = StyleTokens()
    tokens.colors = tokens.colors.model_copy(update={"primary": primary})
    return tokens


def _mocked_repo(shop_uuid: str = "shop-1") -> tuple[StyleRepository, MagicMock]:
    repo = StyleRepository(shop_uuid=shop_uuid, style_table="StyleTable")
    table = MagicMock()
    repo._resource = MagicMock()
    repo._resource.Table.return_value = table
    # Transactions use the low-level client (NOT resource.meta.client), so it does
    # not get double-serialized — inject a separate mock to capture those calls.
    repo._client = MagicMock()
    return repo, table


def test_enabled_uses_real_aws_when_endpoint_missing(monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "true")
    monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)

    repo = StyleRepository()

    assert repo.enabled
    assert "endpoint_url" not in repo._client_kwargs()


def test_enabled_can_be_disabled_without_endpoint(monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)

    assert not StyleRepository().enabled


def test_reset_shop_paginates_query_results():
    repo = StyleRepository(shop_uuid="shop-1")
    table = MagicMock()
    repo._resource = MagicMock()
    repo._resource.Table.return_value = table

    table.query.side_effect = [
        {
            "Items": [
                {"PK": "MERCHANT#shop-1", "SK": "STYLE#DRAFT"},
                {"PK": "MERCHANT#shop-1", "SK": "STYLE#VERSION#0001"},
            ],
            "LastEvaluatedKey": {"PK": "MERCHANT#shop-1", "SK": "STYLE#VERSION#0001"},
        },
        {
            "Items": [
                {"PK": "MERCHANT#shop-1", "SK": "STYLE#VERSION#0020"},
                {"PK": "MERCHANT#shop-1", "SK": "UNDO_STACK"},
            ],
        },
    ]

    repo.reset_shop("shop-1")

    assert table.query.call_count == 2
    assert table.delete_item.call_count == 4
    second_query = table.query.call_args_list[1].kwargs
    assert second_query["ExclusiveStartKey"] == {
        "PK": "MERCHANT#shop-1",
        "SK": "STYLE#VERSION#0001",
    }


def test_save_tokens_with_history_writes_version_draft_and_stack_transactionally():
    repo = StyleRepository(shop_uuid="shop-1", style_table="StyleTable")
    resource = MagicMock()
    table = MagicMock()
    repo._resource = resource
    repo._client = MagicMock()
    resource.Table.return_value = table
    table.get_item.return_value = {
        "Item": {
            "PK": "MERCHANT#shop-1",
            "SK": "UNDO_STACK",
            "undoStack": [1],
            "redoStack": [9],
            "currentVersion": 1,
        }
    }

    version = repo.save_tokens_with_history(
        StyleTokens(),
        shop_uuid="shop-1",
        change_summary={"humanSummary": "Test change"},
    )

    assert version == 2
    table.put_item.assert_not_called()
    resource.meta.client.transact_write_items.assert_not_called()
    transaction = repo._client.transact_write_items.call_args.kwargs["TransactItems"]
    assert len(transaction) == 3
    assert transaction[0]["Put"]["Item"]["SK"] == {"S": "STYLE#VERSION#0002"}
    assert transaction[1]["Put"]["Item"]["SK"] == {"S": "STYLE#DRAFT"}
    assert transaction[2]["Put"]["Item"]["SK"] == {"S": "UNDO_STACK"}
    assert transaction[2]["Put"]["ConditionExpression"] == "#currentVersion = :previousVersion"
    assert transaction[2]["Put"]["ExpressionAttributeValues"][":previousVersion"] == {"N": "1"}


def test_save_tokens_with_history_evicts_old_versions_in_transaction():
    repo, table = _mocked_repo()
    table.get_item.return_value = {
        "Item": {
            "PK": "MERCHANT#shop-1",
            "SK": "UNDO_STACK",
            "undoStack": list(range(1, 22)),
            "redoStack": [99],
            "currentVersion": 21,
        }
    }

    version = repo.save_tokens_with_history(_tokens("#123456"), shop_uuid="shop-1")

    assert version == 22
    transaction = repo._client.transact_write_items.call_args.kwargs["TransactItems"]
    deletes = [item["Delete"]["Key"]["SK"]["S"] for item in transaction if "Delete" in item]
    assert deletes == ["STYLE#VERSION#0001", "STYLE#VERSION#0002"]
    stack_item = transaction[2]["Put"]["Item"]
    assert stack_item["undoStack"] == {"L": [{"N": str(i)} for i in range(3, 23)]}
    assert stack_item["redoStack"] == {"L": []}


def test_undo_moves_current_version_to_redo_and_restores_previous_draft():
    repo, table = _mocked_repo()
    table.get_item.side_effect = [
        {
            "Item": {
                "PK": "MERCHANT#shop-1",
                "SK": "UNDO_STACK",
                "undoStack": [1, 2],
                "redoStack": [],
                "currentVersion": 2,
            }
        },
        {"Item": {"tokens": _tokens("#112233").to_ddb_map()}},
    ]

    tokens = repo.undo("shop-1")

    assert tokens is not None
    assert tokens.colors.primary == "#112233"
    draft_item = table.put_item.call_args_list[0].kwargs["Item"]
    stack_item = table.put_item.call_args_list[1].kwargs["Item"]
    assert draft_item["SK"] == "STYLE#DRAFT"
    assert draft_item["version"] == 1
    assert stack_item["undoStack"] == [1]
    assert stack_item["redoStack"] == [2]
    assert stack_item["currentVersion"] == 1


def test_redo_moves_redo_version_back_to_undo_and_restores_draft():
    repo, table = _mocked_repo()
    table.get_item.side_effect = [
        {
            "Item": {
                "PK": "MERCHANT#shop-1",
                "SK": "UNDO_STACK",
                "undoStack": [1],
                "redoStack": [2],
                "currentVersion": 1,
            }
        },
        {"Item": {"tokens": _tokens("#445566").to_ddb_map()}},
    ]

    tokens = repo.redo("shop-1")

    assert tokens is not None
    assert tokens.colors.primary == "#445566"
    draft_item = table.put_item.call_args_list[0].kwargs["Item"]
    stack_item = table.put_item.call_args_list[1].kwargs["Item"]
    assert draft_item["SK"] == "STYLE#DRAFT"
    assert draft_item["version"] == 2
    assert stack_item["undoStack"] == [1, 2]
    assert stack_item["redoStack"] == []
    assert stack_item["currentVersion"] == 2


def test_publish_draft_writes_published_item_with_rollback_window():
    repo, table = _mocked_repo()
    draft = {
        "PK": "MERCHANT#shop-1",
        "SK": "STYLE#DRAFT",
        "styleState": "draft",
        "tokens": _tokens("#778899").to_ddb_map(),
        "updatedAt": "2026-05-20T11:00:00Z",
    }
    table.get_item.return_value = {"Item": draft}

    published = repo.publish_draft("shop-1")

    assert published is not None
    assert published["SK"] == "STYLE#PUBLISHED"
    assert published["styleState"] == "published"
    assert published["tokens"] == draft["tokens"]
    assert "publishedAt" in published
    assert "rollbackUntil" in published
    table.put_item.assert_called_once_with(Item=published)


def test_save_tokens_with_history_stamps_based_on_package_id(monkeypatch):
    """Catalogue applies record basedOnPackageId on both the version and draft items (CF-02 / 3.4)."""
    repo, table = _mocked_repo()
    table.get_item.return_value = {
        "Item": {
            "PK": "MERCHANT#shop-1",
            "SK": "UNDO_STACK",
            "undoStack": [1],
            "redoStack": [],
            "currentVersion": 1,
        }
    }

    repo.save_tokens_with_history(
        StyleTokens(),
        shop_uuid="shop-1",
        based_on_package_id="tuscan_workshop",
    )

    transaction = repo._client.transact_write_items.call_args.kwargs["TransactItems"]
    version_item = transaction[0]["Put"]["Item"]
    draft_item = transaction[1]["Put"]["Item"]
    assert version_item["SK"] == {"S": "STYLE#VERSION#0002"}
    assert version_item["basedOnPackageId"] == {"S": "tuscan_workshop"}
    assert draft_item["SK"] == {"S": "STYLE#DRAFT"}
    assert draft_item["basedOnPackageId"] == {"S": "tuscan_workshop"}


def test_publish_draft_preserves_based_on_package_id():
    """Publishing a catalogue-based draft carries basedOnPackageId onto the published item (CF-02 / 3.4)."""
    repo, table = _mocked_repo()
    draft = {
        "PK": "MERCHANT#shop-1",
        "SK": "STYLE#DRAFT",
        "styleState": "draft",
        "tokens": _tokens("#778899").to_ddb_map(),
        "basedOnPackageId": "tuscan_workshop",
        "updatedAt": "2026-05-20T11:00:00Z",
    }
    table.get_item.return_value = {"Item": draft}

    published = repo.publish_draft("shop-1")

    assert published is not None
    assert published["basedOnPackageId"] == "tuscan_workshop"
    assert published["SK"] == "STYLE#PUBLISHED"
    assert published["styleState"] == "published"


def test_list_theme_packages_paginates_and_caches_scan_results():
    repo = StyleRepository(package_table="PackageTable")
    table = MagicMock()
    repo._resource = MagicMock()
    repo._resource.Table.return_value = table
    table.scan.side_effect = [
        {
            "Items": [
                {"packageId": "b", "displayName": "Beta", "active": True},
                {"packageId": "z", "displayName": "Inactive", "active": False},
            ],
            "LastEvaluatedKey": {"packageId": "b"},
        },
        {
            "Items": [
                {"packageId": "a", "displayName": "Alpha", "active": True},
            ]
        },
    ]

    packages = repo.list_theme_packages()
    cached = repo.list_theme_packages(active_only=False)

    assert [p["packageId"] for p in packages] == ["a", "b"]
    assert [p["packageId"] for p in cached] == ["a", "b", "z"]
    assert table.scan.call_count == 2
    assert table.scan.call_args_list[1].kwargs["ExclusiveStartKey"] == {"packageId": "b"}


def test_list_theme_packages_refresh_clears_cache():
    repo = StyleRepository(package_table="PackageTable")
    table = MagicMock()
    repo._resource = MagicMock()
    repo._resource.Table.return_value = table
    table.scan.side_effect = [
        {"Items": [{"packageId": "old", "displayName": "Old"}]},
        {"Items": [{"packageId": "new", "displayName": "New"}]},
    ]

    assert repo.list_theme_packages()[0]["packageId"] == "old"
    assert repo.list_theme_packages(refresh=True)[0]["packageId"] == "new"
    assert table.scan.call_count == 2
