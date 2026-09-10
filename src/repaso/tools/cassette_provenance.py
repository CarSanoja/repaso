import json
from datetime import datetime
from pathlib import Path

from pydantic import Field

from repaso.schemas.common import FrozenStrictModel
from repaso.tools.call_ledger import CallOrigin, CallOutcome, CallRecord
from repaso.tools.cassette import CassetteEntry
from repaso.tools.cassette_cost import cassette_spend, model_ids_in
from repaso.tools.cost_report import build_cost_report

PROVENANCE_SUFFIX = ".provenance.json"
NO_VERSION = "unversioned"


class RolePlayback(FrozenStrictModel):
    model_ids: list[str]
    calls: int = Field(ge=0)


class RunSpend(FrozenStrictModel):
    calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    usd: float = Field(ge=0.0)


class CassetteProvenance(FrozenStrictModel):
    cassette: str
    recorded_at: datetime
    commit: str
    working_tree_modified: bool
    region: str
    what_this_is: str
    what_this_is_not: str
    entries: int = Field(ge=0)
    model_ids: list[str]
    roles: dict[str, RolePlayback]
    prompt_versions: dict[str, str]
    replayed: RunSpend
    recorded: RunSpend
    live_calls: int = Field(ge=0)
    failed_calls: int = Field(ge=0)


def provenance_path(cassette: Path) -> Path:
    return cassette.with_suffix(PROVENANCE_SUFFIX)


def roles_in(entries: list[CassetteEntry]) -> dict[str, RolePlayback]:
    roles: dict[str, RolePlayback] = {}
    for role in sorted({entry.role for entry in entries}):
        played = [entry for entry in entries if entry.role == role]
        roles[role] = RolePlayback(model_ids=model_ids_in(played), calls=len(played))
    return roles


def prompt_versions_in(records: list[CallRecord]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for record in records:
        schema = record.output_model or record.kind
        versions.setdefault(schema, record.prompt_version or NO_VERSION)
    return dict(sorted(versions.items()))


def replayed_spend(entries: list[CassetteEntry]) -> RunSpend:
    spend = cassette_spend(entries)
    return RunSpend(
        calls=spend.calls,
        input_tokens=spend.usage.input_tokens,
        output_tokens=spend.usage.output_tokens,
        usd=spend.usd,
    )


def recorded_spend(records: list[CallRecord]) -> RunSpend:
    report = build_cost_report(records)
    return RunSpend(
        calls=report.calls,
        input_tokens=report.usage.input_tokens,
        output_tokens=report.usage.output_tokens,
        usd=report.total_usd,
    )


def build_provenance(
    cassette: Path,
    entries: list[CassetteEntry],
    records: list[CallRecord],
    recorded_at: datetime,
    commit: str,
    working_tree_modified: bool,
    region: str,
    what_this_is: str,
    what_this_is_not: str,
) -> CassetteProvenance:
    return CassetteProvenance(
        cassette=cassette.name,
        recorded_at=recorded_at,
        commit=commit,
        working_tree_modified=working_tree_modified,
        region=region,
        what_this_is=what_this_is,
        what_this_is_not=what_this_is_not,
        entries=len(entries),
        model_ids=model_ids_in(entries),
        roles=roles_in(entries),
        prompt_versions=prompt_versions_in(records),
        replayed=replayed_spend(entries),
        recorded=recorded_spend(records),
        live_calls=sum(1 for r in records if r.origin is CallOrigin.LIVE),
        failed_calls=sum(1 for r in records if r.outcome is not CallOutcome.OK),
    )


def write_provenance(path: Path, provenance: CassetteProvenance) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = provenance.model_dump(mode="json")
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_provenance(path: Path) -> CassetteProvenance | None:
    if not path.exists():
        return None
    return CassetteProvenance.model_validate_json(path.read_text(encoding="utf-8"))
