import re
from dataclasses import dataclass, field
from typing import Protocol

PROJECT = "repaso"
PROJECT_TAG = "project"
MODE_TAG = "deployment-mode"
DURABLE = "durable"
EPHEMERAL = "ephemeral"
UNKNOWN = "unknown"
KINDS = ("stack", "bucket", "secret", "log group")

STACK_ORDER = ("foundation", "messaging", "guardrails", "api", "agentcore", "observability")
DELETE_ORDER = tuple(reversed(STACK_ORDER))
SEGMENTS = re.compile(r"[:/]")


def inside(name: str, project: str) -> bool:
    return any(
        segment == project or segment.startswith(f"{project}-")
        for segment in SEGMENTS.split(name)
    )


@dataclass(frozen=True)
class Target:
    kind: str
    name: str
    note: str = ""
    tags: tuple[tuple[str, str], ...] = ()

    def __str__(self) -> str:
        return f"{self.kind} {self.name}" + (f" ({self.note})" if self.note else "")

    def tag(self, key: str) -> str | None:
        return dict(self.tags).get(key)


def refusal(target: Target, project: str) -> str | None:
    if target.kind not in KINDS:
        return f"{target} is not a kind this teardown knows how to remove"
    if not inside(target.name, project):
        return f"{target} is outside the {project} namespace"
    if target.tag(PROJECT_TAG) != project:
        return f"{target} carries no {PROJECT_TAG}={project} tag"
    return None


@dataclass(frozen=True)
class Plan:
    project: str
    mode: str
    stacks: tuple[Target, ...] = ()
    storage: tuple[Target, ...] = ()
    retained: tuple[Target, ...] = ()
    refusals: tuple[str, ...] = field(default=())

    @property
    def erases_data(self) -> bool:
        return self.mode == EPHEMERAL

    @property
    def buckets(self) -> tuple[Target, ...]:
        return tuple(target for target in self.storage if target.kind == "bucket")

    @property
    def removes(self) -> tuple[Target, ...]:
        return self.stacks + self.storage if self.erases_data else self.stacks

    @property
    def keeps(self) -> tuple[Target, ...]:
        return self.retained if self.erases_data else self.retained + self.storage

    @property
    def blocked(self) -> bool:
        return bool(self.refusals)

    @property
    def empty(self) -> bool:
        return not self.removes


class AccountReader(Protocol):
    def stacks(self) -> list[tuple[str, dict[str, str]]]: ...

    def retained_resources(self, stack: str) -> list[tuple[str, str]]: ...

    def buckets(self) -> list[tuple[str, dict[str, str]]]: ...

    def secrets(self) -> list[tuple[str, dict[str, str]]]: ...

    def log_groups(self) -> list[tuple[str, dict[str, str]]]: ...


def build_plan(reader: AccountReader, project: str = PROJECT) -> Plan:
    refusals: list[str] = []
    found = reader.stacks()
    stacks = _screen("stack", found, project, refusals)
    storage = (
        _screen("bucket", reader.buckets(), project, refusals)
        + _screen("secret", reader.secrets(), project, refusals)
        + _screen("log group", reader.log_groups(), project, refusals)
    )
    retained = tuple(
        Target("retained", physical_id, resource_type)
        for target in stacks
        for resource_type, physical_id in reader.retained_resources(target.name)
    )
    return Plan(
        project=project,
        mode=_mode(found, refusals),
        stacks=tuple(sorted(stacks, key=lambda target: _position(target.name, project))),
        storage=storage,
        retained=retained,
        refusals=tuple(refusals),
    )


def _screen(
    kind: str, found: list[tuple[str, dict[str, str]]], project: str, refusals: list[str]
) -> tuple[Target, ...]:
    kept = []
    for name, tags in found:
        target = Target(kind, name, tags=tuple(sorted(tags.items())))
        problem = refusal(target, project)
        if problem:
            refusals.append(problem)
        else:
            kept.append(target)
    return tuple(kept)


def _mode(found: list[tuple[str, dict[str, str]]], refusals: list[str]) -> str:
    declared = {tags.get(MODE_TAG) for _, tags in found}
    declared.discard(None)
    if not declared:
        return UNKNOWN
    if len(declared) > 1:
        refusals.append(f"stacks disagree about {MODE_TAG}: {', '.join(sorted(declared))}")
        return UNKNOWN
    return declared.pop()


def _position(name: str, project: str) -> int:
    suffix = name[len(project) + 1 :] if name.startswith(f"{project}-") else name
    return DELETE_ORDER.index(suffix) if suffix in DELETE_ORDER else -1
