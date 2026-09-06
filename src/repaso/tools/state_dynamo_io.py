import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from repaso.config.clients import dynamodb_client


def key_of(pk: str, sk: str) -> dict[str, Any]:
    return {"pk": {"S": pk}, "sk": {"S": sk}}


def serialize(model: BaseModel) -> dict[str, Any]:
    from boto3.dynamodb.types import TypeSerializer

    doc = json.loads(model.model_dump_json(), parse_float=Decimal)
    return {"doc": TypeSerializer().serialize(doc)}


def deserialize[M: BaseModel](item: dict[str, Any], model: type[M]) -> M:
    from boto3.dynamodb.types import TypeDeserializer

    document = TypeDeserializer().deserialize(item["doc"])
    # Operation payloads are untyped dictionaries; normalize SDK Decimals so a
    # recovered response can cross the AgentCore JSON boundary.
    document = json.loads(
        json.dumps(document, default=lambda d: int(d) if d % 1 == 0 else float(d))
    )
    return model.model_validate(document)


def put_row(
    table: str, pk: str, sk: str, model: BaseModel, gsi1: tuple[str, str] | None = None
) -> None:
    item = key_of(pk, sk) | serialize(model)
    if gsi1 is not None:
        item["gsi1pk"] = {"S": gsi1[0]}
        item["gsi1sk"] = {"S": gsi1[1]}
    dynamodb_client().put_item(TableName=table, Item=item)


def get_row[M: BaseModel](table: str, pk: str, sk: str, model: type[M]) -> M | None:
    found = dynamodb_client().get_item(TableName=table, Key=key_of(pk, sk), ConsistentRead=True)
    item = found.get("Item")
    return deserialize(item, model) if item else None


def delete_row(table: str, pk: str, sk: str) -> None:
    dynamodb_client().delete_item(TableName=table, Key=key_of(pk, sk))


def query_prefix[M: BaseModel](table: str, pk: str, prefix: str, model: type[M]) -> list[M]:
    values = {":pk": {"S": pk}}
    expression = "pk = :pk"
    if prefix:
        expression += " AND begins_with(sk, :sk)"
        values[":sk"] = {"S": prefix}
    found = query_all(
        TableName=table, KeyConditionExpression=expression, ExpressionAttributeValues=values
    )
    return [deserialize(item, model) for item in found]


def query_keys(table: str, pk: str) -> list[dict[str, Any]]:
    found = query_all(
        TableName=table,
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": {"S": pk}},
        ProjectionExpression="pk, sk",
    )
    return found


def query_index[M: BaseModel](table: str, index: str, gsi1pk: str, model: type[M]) -> list[M]:
    found = query_all(
        TableName=table,
        IndexName=index,
        KeyConditionExpression="gsi1pk = :pk",
        ExpressionAttributeValues={":pk": {"S": gsi1pk}},
    )
    return [deserialize(item, model) for item in found]


def query_all(**kwargs) -> list[dict[str, Any]]:
    if "IndexName" not in kwargs:
        kwargs["ConsistentRead"] = True
    items = []
    while True:
        page = dynamodb_client().query(**kwargs)
        items.extend(page.get("Items", []))
        if not page.get("LastEvaluatedKey"):
            return items
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def scan_profiles[M: BaseModel](table: str, pk_prefix: str, model: type[M]) -> list[M]:
    results: list[M] = []
    kwargs: dict[str, Any] = {
        "TableName": table,
        "ConsistentRead": True,
        "FilterExpression": "begins_with(pk, :pk) AND sk = :sk",
        "ExpressionAttributeValues": {":pk": {"S": pk_prefix}, ":sk": {"S": "PROFILE"}},
    }
    while True:
        found = dynamodb_client().scan(**kwargs)
        results.extend(deserialize(item, model) for item in found.get("Items", []))
        cursor = found.get("LastEvaluatedKey")
        if not cursor:
            return results
        kwargs["ExclusiveStartKey"] = cursor
