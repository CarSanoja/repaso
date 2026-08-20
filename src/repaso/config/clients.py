from functools import cache
from typing import Any

from repaso.config.settings import get_settings


@cache
def _cached_client(service: str) -> Any | None:
    settings = get_settings()
    if settings.local_mode:
        return None
    import boto3

    return boto3.client(service, region_name=settings.aws_region)


def dynamodb_client() -> Any | None:
    return _cached_client("dynamodb")


def s3_client() -> Any | None:
    return _cached_client("s3")


def events_client() -> Any | None:
    return _cached_client("events")


def scheduler_client() -> Any | None:
    return _cached_client("scheduler")


def secrets_client() -> Any | None:
    return _cached_client("secretsmanager")


def bedrock_runtime_client() -> Any | None:
    return _cached_client("bedrock-runtime")


def textract_client() -> Any | None:
    return _cached_client("textract")


def sqs_client() -> Any | None:
    return _cached_client("sqs")


def reset_client_cache() -> None:
    _cached_client.cache_clear()
