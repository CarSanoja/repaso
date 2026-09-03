import json
import pkgutil
import sys
from importlib import import_module
from typing import Any

import boto3
import httpx

import repaso

CLOUD_SDKS = ("aws_cdk", "constructs")
WATCHED = (
    (boto3, "client", "boto3.client"),
    (boto3, "resource", "boto3.resource"),
    (httpx.Client, "__init__", "httpx.Client"),
    (httpx.AsyncClient, "__init__", "httpx.AsyncClient"),
)


def watch(owner: Any, attribute: str, label: str, opened: list[str]) -> None:
    original = getattr(owner, attribute)

    def sentinel(*args: Any, **kwargs: Any) -> Any:
        opened.append(label)
        return original(*args, **kwargs)

    setattr(owner, attribute, sentinel)


def main() -> int:
    opened: list[str] = []
    for owner, attribute, label in WATCHED:
        watch(owner, attribute, label, opened)

    imported: list[str] = []
    failed: list[str] = []
    for found in sorted(m.name for m in pkgutil.walk_packages(repaso.__path__, "repaso.")):
        try:
            import_module(found)
        except Exception as error:
            failed.append(f"{found}: {type(error).__name__}: {error}")
            continue
        imported.append(found)

    json.dump(
        {
            "opened": sorted(set(opened)),
            "cloud_sdks": sorted(name for name in CLOUD_SDKS if name in sys.modules),
            "failed": failed,
            "imported": imported,
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
