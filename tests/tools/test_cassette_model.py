import pytest
from pydantic import BaseModel

from repaso.tools.cassette import CassetteEntry
from repaso.tools.cassette_model import CassetteExhausted, CassetteModel
from repaso.tools.model_usage import CallUsage


class Snippet(BaseModel):
    text: str


class Verdict(BaseModel):
    label: str
    score: float


def user_message(text: str) -> dict:
    return {"role": "user", "content": [{"text": text}]}


def structured(role: str, name: str, payload: dict) -> CassetteEntry:
    return CassetteEntry(role=role, kind="structured_output", output_model=name, payload=payload)


def streamed(role: str, text: str, usage: CallUsage | None = None) -> CassetteEntry:
    return CassetteEntry(role=role, kind="stream", text=text, usage=usage)


async def collect(stream) -> list[dict]:
    return [event async for event in stream]


async def outputs(model: CassetteModel, schema: type[BaseModel], count: int) -> list[BaseModel]:
    prompt = [user_message("da igual lo que diga el prompt")]
    return [
        [event async for event in model.structured_output(schema, prompt)][-1]["output"]
        for _ in range(count)
    ]


async def test_each_schema_replays_in_its_own_recorded_order():
    entries = [
        structured("judge", "Verdict", {"label": "primero", "score": 0.1}),
        structured("judge", "Snippet", {"text": "uno"}),
        structured("judge", "Verdict", {"label": "segundo", "score": 0.2}),
        structured("judge", "Snippet", {"text": "dos"}),
    ]
    model = CassetteModel(entries, "judge")

    snippets = await outputs(model, Snippet, 2)
    verdicts = await outputs(model, Verdict, 2)

    assert [snippet.text for snippet in snippets] == ["uno", "dos"]
    assert [verdict.label for verdict in verdicts] == ["primero", "segundo"]


async def test_replay_does_not_depend_on_the_prompt():
    model = CassetteModel([structured("judge", "Snippet", {"text": "uno"})], "judge")
    events = [
        event
        async for event in model.structured_output(Snippet, [user_message("una redaccion nueva")])
    ]

    assert events[-1]["output"] == Snippet(text="uno")


async def test_entries_recorded_for_other_roles_are_not_replayed():
    entries = [
        structured("generate", "Snippet", {"text": "de generate"}),
        structured("judge", "Snippet", {"text": "de judge"}),
    ]
    model = CassetteModel(entries, "judge")

    assert model.remaining("structured_output", "Snippet") == 1
    assert (await outputs(model, Snippet, 1))[0].text == "de judge"


async def test_exhaustion_names_the_role_the_kind_the_schema_and_the_call_number():
    model = CassetteModel([structured("judge", "Snippet", {"text": "uno"})], "judge")
    await outputs(model, Snippet, 1)

    with pytest.raises(CassetteExhausted) as exhausted:
        await outputs(model, Snippet, 1)

    message = str(exhausted.value)
    assert "judge" in message
    assert "structured_output" in message
    assert "Snippet" in message
    assert "call number 2" in message


async def test_a_schema_never_recorded_is_exhausted_on_its_first_call():
    model = CassetteModel([structured("judge", "Snippet", {"text": "uno"})], "judge")

    with pytest.raises(CassetteExhausted, match="Verdict.*call number 1"):
        await outputs(model, Verdict, 1)


async def test_an_empty_cassette_exhausts_the_stream_naming_text():
    model = CassetteModel([], "probe")

    with pytest.raises(CassetteExhausted, match="text: call number 1"):
        await collect(model.stream([user_message("hola")]))


async def test_stream_replays_the_recorded_text_as_converse_events():
    model = CassetteModel([streamed("generate", "cuarenta y dos")], "generate")

    assert await collect(model.stream([user_message("hola")])) == [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockStart": {"start": {}}},
        {"contentBlockDelta": {"delta": {"text": "cuarenta y dos"}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "end_turn"}},
    ]


async def test_recorded_usage_is_replayed_as_a_metadata_event():
    usage = CallUsage(input_tokens=311, output_tokens=27)
    model = CassetteModel([streamed("generate", "hola", usage)], "generate")

    events = await collect(model.stream([user_message("hola")]))

    assert events[-1] == {
        "metadata": {"usage": {"inputTokens": 311, "outputTokens": 27, "totalTokens": 338}}
    }


async def test_streams_and_structured_outputs_draw_from_separate_queues():
    entries = [
        streamed("judge", "texto"),
        structured("judge", "Snippet", {"text": "uno"}),
    ]
    model = CassetteModel(entries, "judge")

    assert (await outputs(model, Snippet, 1))[0].text == "uno"
    assert model.remaining("stream") == 1


async def test_a_payload_that_no_longer_fits_the_schema_fails_at_replay():
    model = CassetteModel([structured("judge", "Verdict", {"label": "sin score"})], "judge")

    with pytest.raises(ValueError):
        await outputs(model, Verdict, 1)


def test_update_config_stores_and_get_config_returns_it():
    model = CassetteModel([], "judge")
    model.update_config(temperature=0.2)

    assert model.get_config() == {"temperature": 0.2}
