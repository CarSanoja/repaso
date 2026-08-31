import json

import pytest
from pydantic import ValidationError

from repaso.tools.cassette import (
    CassetteEntry,
    CassetteFormatError,
    CassetteWriter,
    Usage,
    load_cassette,
)

SNIPPET = "Dos fracciones equivalen cuando nombran la misma cantidad."


def stream_entry(role: str = "generate", text: str = SNIPPET) -> CassetteEntry:
    return CassetteEntry(role=role, kind="stream", text=text)


def structured_entry(role: str = "judge", name: str = "OpenGrade") -> CassetteEntry:
    return CassetteEntry(
        role=role,
        kind="structured_output",
        output_model=name,
        payload={"correct": True, "confidence": 0.9},
        usage=Usage(input_tokens=120, output_tokens=8),
        latency_ms=412.5,
    )


def test_a_stream_entry_without_text_is_rejected():
    with pytest.raises(ValidationError, match="a stream entry needs text"):
        CassetteEntry(role="generate", kind="stream")


def test_a_structured_entry_without_payload_or_output_model_is_rejected():
    with pytest.raises(ValidationError, match="needs both output_model and payload"):
        CassetteEntry(role="judge", kind="structured_output", output_model="OpenGrade")
    with pytest.raises(ValidationError, match="needs both output_model and payload"):
        CassetteEntry(role="judge", kind="structured_output", payload={"correct": True})


def test_an_unknown_kind_is_rejected():
    with pytest.raises(ValidationError):
        CassetteEntry(role="judge", kind="completion", text="hola")


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        CassetteEntry(role="judge", kind="stream", text="hola", temperature=0.2)


def test_negative_usage_and_latency_are_rejected():
    with pytest.raises(ValidationError):
        Usage(input_tokens=-1, output_tokens=0)
    with pytest.raises(ValidationError):
        CassetteEntry(role="judge", kind="stream", text="hola", latency_ms=-0.1)


def test_write_then_load_returns_the_same_entries(tmp_path):
    path = tmp_path / "run" / "cassette.jsonl"
    writer = CassetteWriter(path)
    entries = [stream_entry(), structured_entry(), stream_entry(role="probe", text="sí")]
    for entry in entries:
        writer.append(entry)

    assert load_cassette(path) == entries


def test_each_entry_is_one_line_with_sorted_keys_and_utf8_text(tmp_path):
    path = tmp_path / "cassette.jsonl"
    writer = CassetteWriter(path)
    writer.append(structured_entry())
    writer.append(stream_entry(text="fracción"))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert list(json.loads(lines[0])) == sorted(json.loads(lines[0]))
    assert "fracción" in lines[1]


def test_blank_lines_are_ignored(tmp_path):
    path = tmp_path / "cassette.jsonl"
    path.write_text(f"\n{stream_entry().model_dump_json()}\n\n", encoding="utf-8")

    assert load_cassette(path) == [stream_entry()]


def test_a_malformed_line_names_the_file_and_the_line_number(tmp_path):
    path = tmp_path / "cassette.jsonl"
    path.write_text(f"{stream_entry().model_dump_json()}\nnot json\n", encoding="utf-8")

    with pytest.raises(CassetteFormatError, match=r"cassette\.jsonl:2"):
        load_cassette(path)


def test_an_entry_that_fails_validation_names_the_line_number(tmp_path):
    path = tmp_path / "cassette.jsonl"
    path.write_text('{"role": "judge", "kind": "stream"}\n', encoding="utf-8")

    with pytest.raises(CassetteFormatError, match=r"cassette\.jsonl:1"):
        load_cassette(path)


def test_a_missing_cassette_says_so_instead_of_raising_oserror(tmp_path):
    with pytest.raises(CassetteFormatError, match="cassette not found"):
        load_cassette(tmp_path / "absent.jsonl")


def test_the_writer_creates_the_directory_it_writes_into(tmp_path):
    path = tmp_path / "deep" / "nested" / "cassette.jsonl"
    CassetteWriter(path).append(stream_entry())

    assert path.exists()
