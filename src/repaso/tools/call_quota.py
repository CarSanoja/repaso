from pathlib import Path
from typing import Protocol, runtime_checkable

from repaso.config.settings import Settings
from repaso.tools.state_local_io import JsonTables

QUOTA_TABLE = "quotas"
USED_FIELD = "used"
EXPIRES_FIELD = "expires_at"
PARTITION = "QUOTA"


@runtime_checkable
class CallQuota(Protocol):
    def reserve(self, key: str, limit: int, expires_at: int) -> bool: ...

    def used(self, key: str) -> int: ...


def _checked(limit: int) -> int:
    if limit < 1:
        raise ValueError("limit must be positive")
    return limit


class LocalCallQuota:
    def __init__(self, root: Path) -> None:
        self._tables = JsonTables(root)

    def reserve(self, key: str, limit: int, expires_at: int) -> bool:
        _checked(limit)
        with self._tables.exclusive():
            rows = self._tables.read(QUOTA_TABLE)
            row = rows.get(key) or {USED_FIELD: 0, EXPIRES_FIELD: expires_at}
            if row[USED_FIELD] >= limit:
                return False
            row[USED_FIELD] += 1
            rows[key] = row
            self._tables.write(QUOTA_TABLE, rows)
            return True

    def used(self, key: str) -> int:
        row = self._tables.read(QUOTA_TABLE).get(key)
        return int(row[USED_FIELD]) if row else 0


class DynamoCallQuota:
    def __init__(self, table: str) -> None:
        self._table = table

    def reserve(self, key: str, limit: int, expires_at: int) -> bool:
        from botocore.exceptions import ClientError

        from repaso.config.clients import dynamodb_client
        from repaso.tools.state_dynamo_io import key_of

        _checked(limit)
        try:
            dynamodb_client().update_item(
                TableName=self._table,
                Key=key_of(f"{PARTITION}#{key}", PARTITION),
                UpdateExpression=(
                    f"SET {EXPIRES_FIELD} = if_not_exists({EXPIRES_FIELD}, :expires) "
                    "ADD #used :one"
                ),
                ConditionExpression="attribute_not_exists(#used) OR #used < :limit",
                ExpressionAttributeNames={"#used": USED_FIELD},
                ExpressionAttributeValues={
                    ":one": {"N": "1"},
                    ":limit": {"N": str(limit)},
                    ":expires": {"N": str(expires_at)},
                },
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True

    def used(self, key: str) -> int:
        from repaso.config.clients import dynamodb_client
        from repaso.tools.state_dynamo_io import key_of

        found = dynamodb_client().get_item(
            TableName=self._table,
            Key=key_of(f"{PARTITION}#{key}", PARTITION),
            ConsistentRead=True,
        )
        item = found.get("Item")
        return int(item[USED_FIELD]["N"]) if item else 0


def build_call_quota(settings: Settings) -> CallQuota:
    if settings.local_mode:
        return LocalCallQuota(settings.local_data_dir / "state")
    return DynamoCallQuota(settings.ddb_table)
