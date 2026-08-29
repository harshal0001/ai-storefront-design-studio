"""Low-level DynamoDB access for ``StorefrontStyle`` and ``ThemePackage``.

Partition key: ``PK = MERCHANT#{shop_uuid}``. Important sort keys:
  - ``STYLE_PROFILE`` — mood tags, merchant category (CF-01)
  - ``STYLE#DRAFT`` — editable preview tokens
  - ``STYLE#PUBLISHED`` — live storefront (CF-10)
  - ``STYLE#VERSION#{seq}`` — version history (max ``MAX_VERSION_DEPTH``)
  - ``UNDO_STACK`` — undo/redo version id lists
  - ``ZONE_TOUR`` — CF-05 tour progress

Enabled when ``USE_DYNAMODB`` is true. ``DYNAMODB_ENDPOINT`` is optional and
only selects DynamoDB Local; without it boto3 uses the normal AWS endpoint and
credential chain.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer

from .style_tokens import StyleTokens


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pk(shop_uuid: str) -> str:
    return f"MERCHANT#{shop_uuid}"


def _data_dir() -> Path:
    raw = os.environ.get("DESIGN_STUDIO_DATA_DIR", "").strip()
    return Path(raw) if raw else Path(".")


def _profile_json_path(shop_uuid: str) -> Path:
    return _data_dir() / f"storefront_profile_{shop_uuid}.json"


def _int_list(values: list | None) -> list[int]:
    if not values:
        return []
    return [int(v) for v in values]


MAX_VERSION_DEPTH = 20
_SERIALIZER = TypeSerializer()


def _to_attribute_map(item: dict[str, Any]) -> dict[str, Any]:
    return {key: _SERIALIZER.serialize(value) for key, value in item.items()}


class StyleRepository:
    """CRUD for style items, versions, undo stack, theme packages, and zone tour state."""

    def __init__(
        self,
        *,
        shop_uuid: str | None = None,
        endpoint_url: str | None = None,
        region: str | None = None,
        style_table: str | None = None,
        package_table: str | None = None,
    ):
        self.shop_uuid = shop_uuid or os.environ.get("DEFAULT_SHOP_UUID", "demo-merchant")
        self.endpoint_url = endpoint_url or os.environ.get("DYNAMODB_ENDPOINT")
        self.region = region or os.environ.get("AWS_REGION", "eu-north-1")
        self.style_table_name = style_table or os.environ.get(
            "DYNAMODB_STYLE_TABLE", "StorefrontStyle"
        )
        self.package_table_name = package_table or os.environ.get(
            "DYNAMODB_THEME_PACKAGE_TABLE", "ThemePackage"
        )
        self._resource = None
        self._client = None
        self._package_cache: list[dict] | None = None

    @property
    def enabled(self) -> bool:
        """True when DynamoDB persistence is requested."""
        use = os.environ.get("USE_DYNAMODB", "true").lower()
        return use in ("1", "true", "yes")

    def _client_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"region_name": self.region}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        return kwargs

    @property
    def resource(self):
        if self._resource is None:
            kwargs = self._client_kwargs()
            # Dummy creds only for DynamoDB Local — never use AWS_ACCESS_KEY_ID here
            # or sourcing example.env would break Bedrock (real AWS creds required).
            if self.endpoint_url:
                kwargs["aws_access_key_id"] = os.environ.get("DYNAMODB_ACCESS_KEY_ID", "local")
                kwargs["aws_secret_access_key"] = os.environ.get(
                    "DYNAMODB_SECRET_ACCESS_KEY", "local"
                )
            self._resource = boto3.resource("dynamodb", **kwargs)
        return self._resource

    @property
    def client(self):
        """Low-level DynamoDB client for pre-serialized payloads (e.g. transactions).

        Must NOT be ``resource.meta.client``: a resource-owned client has boto3's
        high-level (de)serialization injector attached, which would serialize our
        already-``TypeSerializer``-encoded items a second time and DynamoDB rejects
        the result with ``ValidationException: Invalid attribute value type``.
        """
        if self._client is None:
            kwargs = self._client_kwargs()
            if self.endpoint_url:
                kwargs["aws_access_key_id"] = os.environ.get("DYNAMODB_ACCESS_KEY_ID", "local")
                kwargs["aws_secret_access_key"] = os.environ.get(
                    "DYNAMODB_SECRET_ACCESS_KEY", "local"
                )
            self._client = boto3.client("dynamodb", **kwargs)
        return self._client

    @property
    def style_table(self):
        return self.resource.Table(self.style_table_name)

    @property
    def package_table(self):
        return self.resource.Table(self.package_table_name)

    # ------------------------------------------------------------------ profile

    def get_style_profile(self, shop_uuid: str | None = None) -> dict | None:
        shop = shop_uuid or self.shop_uuid
        if not self.enabled:
            path = _profile_json_path(shop)
            if not path.is_file():
                return None
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        item = self._get_item(shop_uuid, "STYLE_PROFILE")
        return item if item else None

    def put_style_profile(
        self,
        profile: dict,
        shop_uuid: str | None = None,
    ) -> None:
        shop = shop_uuid or self.shop_uuid
        now = _utc_now()
        if not self.enabled:
            path = _profile_json_path(shop)
            existing = self.get_style_profile(shop) or {}
            payload = {
                **existing,
                **profile,
                "shopUuid": shop,
                "type": "STYLE_PROFILE",
                "updatedAt": now,
                "createdAt": existing.get("createdAt", now),
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            return
        item = {
            "PK": _pk(shop),
            "SK": "STYLE_PROFILE",
            "type": "STYLE_PROFILE",
            "shopUuid": shop,
            "updatedAt": now,
            **profile,
        }
        if "createdAt" not in item:
            existing = self.get_style_profile(shop)
            item["createdAt"] = existing.get("createdAt", now) if existing else now
        self.style_table.put_item(Item=item)

    def get_zone_tour(self, shop_uuid: str | None = None) -> dict | None:
        if not self.enabled:
            return None
        return self._get_item(shop_uuid, "ZONE_TOUR")

    def put_zone_tour(self, shop_uuid: str, state: dict) -> None:
        if not self.enabled:
            raise RuntimeError(
                "put_zone_tour requires USE_DYNAMODB=true; use ZoneTourManager JSON persistence."
            )
        shop = shop_uuid or self.shop_uuid
        item = {
            "PK": _pk(shop),
            "SK": "ZONE_TOUR",
            "type": "ZONE_TOUR",
            "shopUuid": shop,
            "updatedAt": _utc_now(),
            **state,
        }
        self.style_table.put_item(Item=item)

    def update_mood_tags(
        self,
        mood_tags: list[str],
        *,
        merchant_category: str = "",
        audience_tags: list[str] | None = None,
        shop_uuid: str | None = None,
    ) -> None:
        shop = shop_uuid or self.shop_uuid
        existing = self.get_style_profile(shop) or {}
        self.put_style_profile(
            {
                "merchantCategory": merchant_category or existing.get("merchantCategory", ""),
                "moodTags": mood_tags,
                "audienceTags": audience_tags or existing.get("audienceTags", []),
                "brandPaletteInput": existing.get("brandPaletteInput"),
            },
            shop_uuid=shop,
        )

    def update_brand_palette(
        self,
        palette: list[str],
        *,
        shop_uuid: str | None = None,
    ) -> None:
        """Store a merchant-supplied brand palette on STYLE_PROFILE (CF-01 / Z1-03)."""
        shop = shop_uuid or self.shop_uuid
        existing = self.get_style_profile(shop) or {}
        self.put_style_profile(
            {
                "merchantCategory": existing.get("merchantCategory", ""),
                "moodTags": existing.get("moodTags", []),
                "audienceTags": existing.get("audienceTags", []),
                "brandPaletteInput": palette,
            },
            shop_uuid=shop,
        )

    # ------------------------------------------------------------------ style items

    def _get_item(self, shop_uuid: str | None, sk: str) -> dict | None:
        if not self.enabled:
            return None
        resp = self.style_table.get_item(Key={"PK": _pk(shop_uuid or self.shop_uuid), "SK": sk})
        return resp.get("Item")

    def get_draft(self, shop_uuid: str | None = None) -> dict | None:
        return self._get_item(shop_uuid, "STYLE#DRAFT")

    def get_published(self, shop_uuid: str | None = None) -> dict | None:
        return self._get_item(shop_uuid, "STYLE#PUBLISHED")

    def get_effective_tokens(self, shop_uuid: str | None = None) -> StyleTokens:
        draft = self.get_draft(shop_uuid)
        if draft and draft.get("tokens"):
            return StyleTokens.from_ddb_map(_from_ddb(draft["tokens"]))
        published = self.get_published(shop_uuid)
        if published and published.get("tokens"):
            return StyleTokens.from_ddb_map(_from_ddb(published["tokens"]))
        return StyleTokens()

    def get_effective_meta(self, shop_uuid: str | None = None) -> dict:
        draft = self.get_draft(shop_uuid)
        if draft:
            return draft
        published = self.get_published(shop_uuid)
        return published or {}

    def _version_sk(self, seq: int) -> str:
        return f"STYLE#VERSION#{seq:04d}"

    def _draft_item(
        self,
        tokens: StyleTokens,
        *,
        shop_uuid: str,
        version: int,
        now: str,
        based_on_package_id: str | None = None,
        agent_prompt: str = "",
        change_summary: dict | None = None,
    ) -> dict[str, Any]:
        style_id = f"sty_{now[:10].replace('-', '')}_{uuid.uuid4().hex[:4]}"
        item: dict[str, Any] = {
            "PK": _pk(shop_uuid),
            "SK": "STYLE#DRAFT",
            "type": "STYLE",
            "styleState": "draft",
            "styleId": style_id,
            "version": version,
            "createdBy": "agent",
            "tokens": tokens.to_ddb_map(),
            "updatedAt": now,
            "createdAt": now,
        }
        if based_on_package_id:
            item["basedOnPackageId"] = based_on_package_id
        if agent_prompt:
            item["agentPrompt"] = agent_prompt
        if change_summary:
            item["changeSummary"] = change_summary
        return item

    def put_draft(
        self,
        tokens: StyleTokens,
        *,
        shop_uuid: str | None = None,
        version: int = 1,
        based_on_package_id: str | None = None,
        agent_prompt: str = "",
        change_summary: dict | None = None,
    ) -> dict:
        shop = shop_uuid or self.shop_uuid
        now = _utc_now()
        item = self._draft_item(
            tokens,
            shop_uuid=shop,
            version=version,
            now=now,
            based_on_package_id=based_on_package_id,
            agent_prompt=agent_prompt,
            change_summary=change_summary,
        )
        self.style_table.put_item(Item=item)
        return item

    def _version_item(
        self,
        tokens: StyleTokens,
        version: int,
        *,
        shop_uuid: str,
        now: str,
        based_on_package_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "PK": _pk(shop_uuid),
            "SK": self._version_sk(version),
            "type": "STYLE",
            "styleState": "version",
            "version": version,
            "tokens": tokens.to_ddb_map(),
            "updatedAt": now,
            "createdAt": now,
            **({"basedOnPackageId": based_on_package_id} if based_on_package_id else {}),
        }

    def append_version(
        self,
        tokens: StyleTokens,
        version: int,
        *,
        shop_uuid: str | None = None,
        based_on_package_id: str | None = None,
    ) -> None:
        shop = shop_uuid or self.shop_uuid
        now = _utc_now()
        self.style_table.put_item(
            Item=self._version_item(
                tokens,
                version,
                shop_uuid=shop,
                now=now,
                based_on_package_id=based_on_package_id,
            )
        )

    def get_version_item(self, version: int, shop_uuid: str | None = None) -> dict | None:
        return self._get_item(shop_uuid, self._version_sk(version))

    # ------------------------------------------------------------------ undo stack

    def get_undo_stack(self, shop_uuid: str | None = None) -> dict:
        item = self._get_item(shop_uuid, "UNDO_STACK")
        if item:
            return {
                **item,
                "undoStack": _int_list(item.get("undoStack")),
                "redoStack": _int_list(item.get("redoStack")),
                "currentVersion": int(item.get("currentVersion", 0)),
            }
        return {
            "undoStack": [],
            "redoStack": [],
            "currentVersion": 0,
            "maxDepth": MAX_VERSION_DEPTH,
        }

    def _put_undo_stack(
        self,
        undo_stack: list[int],
        redo_stack: list[int],
        current_version: int,
        shop_uuid: str | None = None,
    ) -> None:
        shop = shop_uuid or self.shop_uuid
        self.style_table.put_item(
            Item=self._undo_stack_item(
                undo_stack,
                redo_stack,
                current_version,
                shop_uuid=shop,
                now=_utc_now(),
            )
        )

    def _undo_stack_item(
        self,
        undo_stack: list[int],
        redo_stack: list[int],
        current_version: int,
        *,
        shop_uuid: str,
        now: str,
    ) -> dict[str, Any]:
        return {
            "PK": _pk(shop_uuid),
            "SK": "UNDO_STACK",
            "type": "UNDO_STACK",
            "undoStack": undo_stack,
            "redoStack": redo_stack,
            "currentVersion": current_version,
            "maxDepth": MAX_VERSION_DEPTH,
            "updatedAt": now,
        }

    def _evict_old_versions(self, shop_uuid: str, undo_stack: list[int]) -> list[int]:
        if len(undo_stack) <= MAX_VERSION_DEPTH:
            return undo_stack
        to_remove = undo_stack[: len(undo_stack) - MAX_VERSION_DEPTH]
        kept = undo_stack[len(undo_stack) - MAX_VERSION_DEPTH :]
        for seq in to_remove:
            self.style_table.delete_item(Key={"PK": _pk(shop_uuid), "SK": self._version_sk(seq)})
        return kept

    def save_tokens_with_history(
        self,
        tokens: StyleTokens,
        *,
        shop_uuid: str | None = None,
        based_on_package_id: str | None = None,
        change_summary: dict | None = None,
    ) -> int:
        """Write draft, version snapshot, and update undo stack. Returns new version seq."""
        shop = shop_uuid or self.shop_uuid
        stack = self.get_undo_stack(shop)
        undo = list(stack.get("undoStack") or [])
        redo: list[int] = []

        previous_version = int(stack.get("currentVersion") or 0)
        next_version = previous_version + 1
        undo.append(next_version)
        versions_to_evict = undo[: max(0, len(undo) - MAX_VERSION_DEPTH)]
        undo = undo[len(versions_to_evict) :]
        now = _utc_now()

        version_item = self._version_item(
            tokens,
            next_version,
            shop_uuid=shop,
            now=now,
            based_on_package_id=based_on_package_id,
        )
        draft_item = self._draft_item(
            tokens,
            shop_uuid=shop,
            version=next_version,
            now=now,
            based_on_package_id=based_on_package_id,
            change_summary=change_summary,
        )
        stack_item = self._undo_stack_item(
            undo,
            redo,
            next_version,
            shop_uuid=shop,
            now=now,
        )
        stack_exists = "PK" in stack and "SK" in stack

        transact_items: list[dict[str, Any]] = [
            {
                "Put": {
                    "TableName": self.style_table_name,
                    "Item": _to_attribute_map(version_item),
                    "ConditionExpression": "attribute_not_exists(PK)",
                }
            },
            {
                "Put": {
                    "TableName": self.style_table_name,
                    "Item": _to_attribute_map(draft_item),
                }
            },
            {
                "Put": {
                    "TableName": self.style_table_name,
                    "Item": _to_attribute_map(stack_item),
                    **(
                        {
                            "ConditionExpression": "#currentVersion = :previousVersion",
                            "ExpressionAttributeNames": {"#currentVersion": "currentVersion"},
                            "ExpressionAttributeValues": {
                                ":previousVersion": _SERIALIZER.serialize(previous_version)
                            },
                        }
                        if stack_exists
                        else {"ConditionExpression": "attribute_not_exists(PK)"}
                    ),
                }
            },
        ]
        for seq in versions_to_evict:
            transact_items.append(
                {
                    "Delete": {
                        "TableName": self.style_table_name,
                        "Key": _to_attribute_map({"PK": _pk(shop), "SK": self._version_sk(seq)}),
                    }
                }
            )

        self.client.transact_write_items(TransactItems=transact_items)

        return next_version

    def undo(self, shop_uuid: str | None = None) -> StyleTokens | None:
        shop = shop_uuid or self.shop_uuid
        stack = self.get_undo_stack(shop)
        undo = list(stack.get("undoStack") or [])
        redo = list(stack.get("redoStack") or [])
        if len(undo) < 2:
            return None

        current = undo.pop()
        redo.append(current)
        target = undo[-1]

        version_item = self.get_version_item(target, shop)
        if not version_item or not version_item.get("tokens"):
            return None

        tokens = StyleTokens.from_ddb_map(_from_ddb(version_item["tokens"]))
        self.put_draft(tokens, shop_uuid=shop, version=target)
        self._put_undo_stack(undo, redo, target, shop)
        return tokens

    def redo(self, shop_uuid: str | None = None) -> StyleTokens | None:
        shop = shop_uuid or self.shop_uuid
        stack = self.get_undo_stack(shop)
        undo = list(stack.get("undoStack") or [])
        redo = list(stack.get("redoStack") or [])
        if not redo:
            return None

        target = redo.pop()
        undo.append(target)

        version_item = self.get_version_item(target, shop)
        if not version_item or not version_item.get("tokens"):
            return None

        tokens = StyleTokens.from_ddb_map(_from_ddb(version_item["tokens"]))
        self.put_draft(tokens, shop_uuid=shop, version=target)
        self._put_undo_stack(undo, redo, target, shop)
        return tokens

    def restore_version(self, version: int, shop_uuid: str | None = None) -> StyleTokens | None:
        shop = shop_uuid or self.shop_uuid
        version_item = self.get_version_item(version, shop)
        if not version_item or not version_item.get("tokens"):
            return None

        tokens = StyleTokens.from_ddb_map(_from_ddb(version_item["tokens"]))
        stack = self.get_undo_stack(shop)
        undo = list(stack.get("undoStack") or [])
        if version not in undo:
            undo.append(version)
            undo = self._evict_old_versions(shop, undo)
        self.put_draft(tokens, shop_uuid=shop, version=version)
        self._put_undo_stack(undo, [], version, shop)
        return tokens

    def _version_timestamp(self, version: int, shop_uuid: str) -> str:
        item = self.get_version_item(version, shop_uuid)
        if item:
            ts = item.get("updatedAt") or item.get("createdAt")
            if ts:
                return str(ts)
        return _utc_now()

    def list_version_summaries(self, shop_uuid: str | None = None) -> list[dict]:
        shop = shop_uuid or self.shop_uuid
        stack = self.get_undo_stack(shop)
        undo = _int_list(stack.get("undoStack"))
        redo = list(reversed(_int_list(stack.get("redoStack"))))
        current = int(stack.get("currentVersion", undo[-1] if undo else 0))
        summaries: list[dict] = [
            {
                "versionId": i,
                "versionSeq": seq,
                "label": f"Version {i + 1}",
                "isCurrent": seq == current,
                "branch": "current",
                "lastModified": self._version_timestamp(seq, shop),
            }
            for i, seq in enumerate(undo)
        ]
        for seq in redo:
            summaries.append(
                {
                    "versionId": len(summaries),
                    "versionSeq": seq,
                    "label": f"Redo → v{seq}",
                    "isCurrent": False,
                    "branch": "redo",
                    "lastModified": self._version_timestamp(seq, shop),
                }
            )
        return summaries

    def can_undo(self, shop_uuid: str | None = None) -> bool:
        undo = self.get_undo_stack(shop_uuid).get("undoStack") or []
        return len(undo) >= 2

    def can_redo(self, shop_uuid: str | None = None) -> bool:
        redo = self.get_undo_stack(shop_uuid).get("redoStack") or []
        return len(redo) > 0

    def publish_draft(self, shop_uuid: str | None = None) -> dict | None:
        draft = self.get_draft(shop_uuid)
        if not draft:
            return None
        now = _utc_now()
        published = {
            **draft,
            "SK": "STYLE#PUBLISHED",
            "styleState": "published",
            "publishedAt": now,
        }
        rollback_days = 7
        from datetime import timedelta

        rollback_until = (datetime.now(timezone.utc) + timedelta(days=rollback_days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        published["rollbackUntil"] = rollback_until
        published["updatedAt"] = now
        self.style_table.put_item(Item=published)
        return published

    def reset_shop(self, shop_uuid: str | None = None) -> None:
        shop = shop_uuid or self.shop_uuid
        pk = _pk(shop)
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": Key("PK").eq(pk),
        }
        while True:
            resp = self.style_table.query(**query_kwargs)
            for item in resp.get("Items", []):
                self.style_table.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key

    # ------------------------------------------------------------------ theme packages

    def clear_theme_package_cache(self) -> None:
        self._package_cache = None

    def list_theme_packages(self, *, active_only: bool = True, refresh: bool = False) -> list[dict]:
        if refresh:
            self.clear_theme_package_cache()
        if self._package_cache is not None:
            packages = self._package_cache
        else:
            scan_kwargs: dict[str, Any] = {}
            packages = []
            while True:
                resp = self.package_table.scan(**scan_kwargs)
                packages.extend(resp.get("Items", []))
                last_key = resp.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_kwargs["ExclusiveStartKey"] = last_key
            self._package_cache = packages

        if active_only:
            packages = [p for p in packages if p.get("active", True)]
        return sorted(packages, key=lambda p: p.get("displayName", ""))

    def get_theme_package(self, package_id: str) -> dict | None:
        resp = self.package_table.get_item(Key={"packageId": package_id})
        return resp.get("Item")

    def get_theme_package_tokens(self, package_id: str) -> StyleTokens | None:
        pkg = self.get_theme_package(package_id)
        if not pkg or not pkg.get("tokens"):
            return None
        return StyleTokens.from_ddb_map(_from_ddb(pkg["tokens"]))


def _from_ddb(value: Any) -> Any:
    """Convert DynamoDB types (Decimal, set) to JSON-serializable Python types."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, set):
        return [_from_ddb(v) for v in sorted(value)]
    if isinstance(value, list):
        return [_from_ddb(v) for v in value]
    if isinstance(value, dict):
        return {k: _from_ddb(v) for k, v in value.items()}
    return value
