from copy import deepcopy
from datetime import UTC, datetime

from repaso.api.memory_episodes import learning_episodes
from repaso.api.memory_projection import opaque
from repaso.schemas.operation import OperationRecord
from repaso.schemas.telemetry import TraceEvent
from repaso.simulator.memory_rehearsal import FAMILY_ID, MemoryRehearsal
from tests.api.conftest import JUDGE_CODE, make_family

HEADERS = {"X-Judge-Code": JUDGE_CODE}


def note(key, approach="", session="session", **kwargs):
    return {
        "id": key,
        "at": f"2026-09-14T10:0{key}:00+00:00",
        "intent": "explanation",
        "said": "another example",
        "explained": approach,
        "session_ref": session,
        **kwargs,
    }


def event(key, kind, name, correlation, **extra):
    return {
        "id": key,
        "at": "2026-09-14T10:05:00+00:00",
        "kind": kind,
        "name": name,
        "extra": {"correlation_id": correlation, **extra},
    }


def test_explicit_note_and_delivery_chain_reconstructs_real_reply_without_time_guessing():
    notes = [note("1", "cake"), note("2", "fold paper"), note("0", "private", "different")]
    events = [
        event("save", "memory", "turn.saved", "turn-2", record_ref="2"),
        event(
            "read",
            "memory",
            "explanation.context_loaded",
            "turn-2",
            notes_loaded="1",
            approaches_loaded="1",
        ),
        event("send", "delivery", "acknowledged", "outbox-2", parent_correlation_id="turn-2"),
        event("unrelated", "delivery", "acknowledged", "outbox-foreign"),
    ]
    deliveries = [
        {
            "id": "reply",
            "delivery_ref": "outbox-2",
            "text": "Actual paper explanation",
            "at": "2026-09-14T10:05:00+00:00",
            "status": "acknowledged",
        },
        {
            "id": "wrong",
            "delivery_ref": "outbox-foreign",
            "text": "DO NOT EXPOSE",
            "at": "2026-09-14T10:05:00+00:00",
            "status": "acknowledged",
        },
    ]
    original = deepcopy((notes, events, deliveries))
    episodes = learning_episodes(notes, events, deliveries)
    second = episodes[-1]
    assert second["conversation"][-1]["text"] == "Actual paper explanation"
    assert second["conversation"][0]["status"] == "retained_snippet"
    assert second["memory"]["previous_approaches"] == [{"note_id": "1", "approach": "cake"}]
    assert second["memory"]["approaches_loaded"] == 1
    assert second["transcript_complete"] is False
    assert "DO NOT EXPOSE" not in str(episodes)
    assert (notes, events, deliveries) == original  # Playback cannot mutate the observation.


def test_missing_trace_never_invents_reply_retrieval_or_success():
    result = learning_episodes(
        [note("1")], [], [{"id": "nearby", "delivery_ref": "same-time", "text": "unrelated"}]
    )[0]
    assert result["outcome"] == "help_unavailable"
    assert result["reconstruction"] == "partial"
    assert result["memory"]["approaches_loaded"] is None
    assert result["memory"]["previous_approaches"] == []
    assert len(result["conversation"]) == 1


def test_incomplete_retained_window_shows_count_without_guessing_approaches():
    notes = [note("1", "cake"), note("2", "paper")]
    events = [
        event("save", "memory", "turn.saved", "turn-2", record_ref="2"),
        event("read", "memory", "explanation.context_loaded", "turn-2", approaches_loaded="3"),
    ]
    memory = learning_episodes(notes, events, [])[-1]["memory"]
    assert memory["approaches_loaded"] == 3
    assert memory["previous_approaches"] == []


async def test_rehearsal_endpoint_proves_context_reply_and_ungraded_help(
    api_settings, container, app, client
):
    api_settings.judge_family_ids = FAMILY_ID
    run = MemoryRehearsal(api_settings)
    await run.prepare()
    container.clock = run.clock
    app.state.memory_rehearsal = run
    await run.step("help")
    await run.step("another")
    response = await client.get("/judge/memory/snapshot/" + FAMILY_ID, headers=HEADERS)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "_episode_deliveries" not in data
    assert data["counts"]["assessed"] == 0
    assert len(data["episodes"]) == 2
    first, second = data["episodes"]
    assert first["memory"]["approaches_loaded"] == 0
    assert second["memory"]["approaches_loaded"] == 1
    assert second["memory"]["previous_approaches"] == [
        {"note_id": first["id"], "approach": "bar split into quarters"}
    ]
    assert any(m["text"].startswith("Imagina media pizza") for m in second["conversation"])
    assert second["conversation"][-1]["status"] == "acknowledged"
    assert second["difficulty"] == 2
    assert "answer_key" not in response.text

    await run.step("answer")
    answered = (await client.get("/judge/memory/snapshot/" + FAMILY_ID, headers=HEADERS)).json()
    assert answered["counts"]["assessed"] == 1
    assert len(answered["episodes"]) == 3
    assessment = answered["episodes"][-1]
    assert assessment["intent"] == "answer"
    assert assessment["outcome"] == "assessed"
    assert assessment["correct"] is True
    assert assessment["difficulty"] == 2
    assert assessment["assessment_source"] == "attempt_record"
    assert assessment["conversation"] == assessment["events"] == []
    assert assessment["memory"]["correlation_verified"] is False
    assert assessment["question"] == second["question"]
    assert assessment["student_ref"] == second["student_ref"]
    assert "_assessment_episodes" not in answered


def test_held_assessment_never_claims_to_be_a_correct_or_incorrect_answer():
    attempt = {
        "id": "held",
        "at": "2026-09-14T10:00:00+00:00",
        "session_ref": "s",
        "content_ref": "q",
        "held": True,
        "correct": None,
    }
    result = learning_episodes([], [], [], [attempt])[0]
    assert result["outcome"] == "held"
    assert result["correct"] is None
    assert result["conversation"] == []


async def test_unlinked_outbox_text_stays_private_even_when_destination_is_valid(
    client, container, app
):
    family = make_family()
    container.store.put_family(family)
    container.store.put_record(
        OperationRecord(
            scope=family.id,
            key="outbox#unlinked",
            payload={
                "created_at": datetime.now(UTC).isoformat(),
                "messages": [
                    {
                        "channel": family.channel.value,
                        "chat_ref": family.chat_ref,
                        "text": "UNLINKED PRIVATE BODY",
                    }
                ],
                "receipts": ["secret"],
            },
        )
    )

    class Feed:
        def read(self):
            return [
                TraceEvent(
                    at=datetime.now(UTC),
                    kind="delivery",
                    name="acknowledged",
                    family_id=family.id,
                    extra={"correlation_id": opaque("outbox#unlinked")},
                )
            ]

    app.state.memory_events = Feed()
    response = await client.get("/judge/memory/snapshot/f1", headers=HEADERS)
    assert response.status_code == 200
    assert "UNLINKED PRIVATE BODY" not in response.text
    assert "secret" not in response.text
    assert response.json()["episodes"] == []
