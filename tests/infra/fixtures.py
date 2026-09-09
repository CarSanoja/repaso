import json
from pathlib import Path

import pytest

assertions = pytest.importorskip("aws_cdk.assertions")


def template(assembly: Path, name: str):
    rendered = (assembly / f"repaso-{name}.template.json").read_text(encoding="utf-8")
    return assertions.Template.from_string(rendered)


def resources(assembly: Path, stack: str, resource_type: str) -> dict:
    return template(assembly, stack).find_resources(resource_type)


def only(assembly: Path, stack: str, resource_type: str) -> dict:
    found = resources(assembly, stack, resource_type)
    assert len(found) == 1
    return next(iter(found.values()))["Properties"]


def properties(assembly: Path, stack: str, resource_type: str) -> list[dict]:
    return [entry["Properties"] for entry in resources(assembly, stack, resource_type).values()]


def annotations(assembly: Path, stack: str) -> list[dict]:
    metadata = json.loads(
        (assembly / f"repaso-{stack}.metadata.json").read_text(encoding="utf-8")
    )
    return [entry for entries in metadata.values() for entry in entries]
