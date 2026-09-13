from datetime import datetime, timedelta

from repaso.core.orchestration.context import Services
from repaso.schemas.common import FamilyId, SessionId
from repaso.schemas.item import Item
from repaso.schemas.operation import OperationRecord
from repaso.schemas.turn import TurnIntent, TurnNote, TurnWindow

MAX_NOTES = 8
SAID_LIMIT = 160
STEM_LIMIT = 120
WINDOW_TTL_DAYS = 7
VERDICTS = {True: "correct", False: "incorrect"}


def window_prefix(session_id: SessionId) -> str:
    return f"turn#{session_id}#"


def note_key(session_id: SessionId, turn_id: str) -> str:
    return f"{window_prefix(session_id)}{turn_id}"


def note(
    turn_id: str,
    intent: TurnIntent,
    at: datetime,
    item: Item | None = None,
    item_index: int = 0,
    said: str = "",
    correct: bool | None = None,
    explained: str = "",
) -> TurnNote:
    return TurnNote(
        turn_id=turn_id,
        intent=intent,
        at=at,
        item_id=item.id if item is not None else None,
        item_index=item_index,
        said=said.strip()[:SAID_LIMIT],
        correct=correct,
        explained=explained.strip(),
    )


def read_window(services: Services, family_id: FamilyId, session_id: SessionId) -> TurnWindow:
    notes = [
        TurnNote.model_validate(record.payload["note"])
        for record in services.store.list_records(family_id, window_prefix(session_id))
        if record.payload.get("note")
    ]
    notes.sort(key=lambda entry: entry.at)
    return TurnWindow(session_id=session_id, notes=notes[-MAX_NOTES:])


def remember(
    services: Services, family_id: FamilyId, session_id: SessionId, entry: TurnNote
) -> TurnWindow:
    _write(services, family_id, session_id, entry.turn_id, entry.model_dump(mode="json"))
    return read_window(services, family_id, session_id)


def close_window(services: Services, family_id: FamilyId, session_id: SessionId) -> None:
    for record in services.store.list_records(family_id, window_prefix(session_id)):
        entry = record.payload.get("note")
        if not entry or not entry.get("said"):
            continue
        turn_id = record.key.removeprefix(window_prefix(session_id))
        _write(services, family_id, session_id, turn_id, entry | {"said": ""})


def last_answer(window: TurnWindow, item_id: str | None) -> TurnNote | None:
    answers = [
        entry
        for entry in window.notes
        if entry.intent is TurnIntent.ANSWER and entry.item_id == item_id
    ]
    return answers[-1] if answers else None


def tried_approaches(window: TurnWindow) -> list[str]:
    approaches: list[str] = []
    for entry in window.notes:
        if entry.explained and entry.explained not in approaches:
            approaches.append(entry.explained)
    return approaches


def history_lines(services: Services, window: TurnWindow) -> list[str]:
    stems: dict[str, str] = {}
    return [
        _line(services, number, entry, stems) for number, entry in enumerate(window.notes, start=1)
    ]


def _line(services: Services, number: int, entry: TurnNote, stems: dict[str, str]) -> str:
    parts = [f"turn {number}", f"intent: {entry.intent.value}"]
    question = _stem(services, entry.item_id, stems)
    if question:
        parts.append(f"question: {question}")
    if entry.said:
        parts.append(f'wrote: "{entry.said}"')
    if entry.correct is not None:
        parts.append(f"harness graded: {VERDICTS[entry.correct]}")
    if entry.explained:
        parts.append(f"explained with: {entry.explained}")
    return " | ".join(parts)


def _stem(services: Services, item_id: str | None, stems: dict[str, str]) -> str:
    if item_id is None:
        return ""
    if item_id not in stems:
        item = services.store.get_item(item_id)
        stems[item_id] = item.stem[:STEM_LIMIT] if item is not None else ""
    return stems[item_id]


def _write(
    services: Services,
    family_id: FamilyId,
    session_id: SessionId,
    turn_id: str,
    payload: dict | None,
) -> None:
    expires_at = services.clock.now() + timedelta(days=WINDOW_TTL_DAYS)
    services.store.put_record(
        OperationRecord(
            scope=family_id,
            key=note_key(session_id, turn_id),
            payload={"note": payload, "expires_at": int(expires_at.timestamp())},
        )
    )
