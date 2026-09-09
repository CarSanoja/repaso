from repaso.tools.model_usage import (
    CallUsage,
    stop_reason_from_event,
    usage_from_event,
    usage_from_response,
    usage_metadata,
)

STREAM_EVENT = {
    "metadata": {
        "usage": {"inputTokens": 14, "outputTokens": 4, "totalTokens": 18},
        "metrics": {"latencyMs": 497},
    }
}

STRUCTURED_EVENT = {
    "event": {
        "metadata": {
            "usage": {"inputTokens": 671, "outputTokens": 37, "totalTokens": 708},
            "metrics": {"latencyMs": 590},
        }
    }
}

CACHE_WRITE_EVENT = {
    "metadata": {
        "usage": {
            "inputTokens": 15,
            "outputTokens": 4,
            "totalTokens": 3742,
            "cacheReadInputTokens": 0,
            "cacheWriteInputTokens": 3723,
            "cacheDetails": [{"ttl": "5m", "inputTokens": 3723}],
        }
    }
}

CACHE_READ_EVENT = {
    "metadata": {
        "usage": {
            "inputTokens": 15,
            "outputTokens": 4,
            "totalTokens": 3742,
            "cacheReadInputTokens": 3723,
            "cacheWriteInputTokens": 0,
        }
    }
}


def test_a_streamed_call_reports_its_usage_flat():
    usage = usage_from_event(STREAM_EVENT)
    assert (usage.input_tokens, usage.output_tokens) == (14, 4)


def test_a_structured_call_reports_the_same_usage_one_level_deeper():
    usage = usage_from_event(STRUCTURED_EVENT)
    assert (usage.input_tokens, usage.output_tokens) == (671, 37)


def test_the_older_chunk_wrapper_is_read_too():
    usage = usage_from_event({"chunk": STREAM_EVENT})
    assert (usage.input_tokens, usage.output_tokens) == (14, 4)


def test_cache_writes_and_reads_are_counted_apart_from_input():
    written = usage_from_event(CACHE_WRITE_EVENT)
    read = usage_from_event(CACHE_READ_EVENT)

    assert (written.input_tokens, written.cache_write_tokens) == (15, 3723)
    assert written.cache_read_tokens == 0
    assert (read.input_tokens, read.cache_read_tokens) == (15, 3723)
    assert read.cache_write_tokens == 0


def test_a_reasoning_count_is_read_under_either_spelling():
    camel = usage_from_event({"metadata": {"usage": {"outputTokens": 90, "reasoningTokens": 64}}})
    snake = usage_from_event({"metadata": {"usage": {"outputTokens": 90, "reasoning_tokens": 64}}})

    assert camel.reasoning_tokens == 64
    assert snake.reasoning_tokens == 64


def test_an_event_that_carries_no_usage_is_not_a_zero_reading():
    assert usage_from_event({"output": object()}) is None
    assert usage_from_event({"metadata": {"metrics": {"latencyMs": 12}}}) is None
    assert usage_from_event({"event": {"messageStop": {"stopReason": "tool_use"}}}) is None
    assert usage_from_event({"metadata": {"usage": {"cacheDetails": []}}}) is None
    assert usage_from_event("not an event") is None


def test_a_reported_zero_stays_a_reading():
    usage = usage_from_event({"metadata": {"usage": {"inputTokens": 0, "outputTokens": 0}}})
    assert usage == CallUsage()


def test_a_nonsense_count_is_read_as_zero_rather_than_rejected():
    usage = usage_from_event({"metadata": {"usage": {"inputTokens": "many", "outputTokens": -3}}})
    assert usage == CallUsage()


def test_a_converse_response_reports_its_usage_at_the_top_level():
    answered = usage_from_response({"output": {}, "usage": {"inputTokens": 3, "outputTokens": 1}})

    assert (answered.input_tokens, answered.output_tokens) == (3, 1)
    assert usage_from_response({"output": {}}) is None
    assert usage_from_response("not a response") is None


def test_the_stop_reason_reads_through_either_shape():
    assert stop_reason_from_event({"messageStop": {"stopReason": "end_turn"}}) == "end_turn"
    assert stop_reason_from_event({"event": {"messageStop": {"stopReason": "tool_use"}}}) == (
        "tool_use"
    )
    assert stop_reason_from_event({"messageStop": {}}) is None
    assert stop_reason_from_event(STREAM_EVENT) is None


def test_usage_adds_across_calls():
    total = CallUsage(input_tokens=10, output_tokens=2, cache_read_tokens=5) + CallUsage(
        input_tokens=1, cache_write_tokens=7, reasoning_tokens=3
    )
    assert total == CallUsage(
        input_tokens=11,
        output_tokens=2,
        cache_read_tokens=5,
        cache_write_tokens=7,
        reasoning_tokens=3,
    )
    assert total.total_tokens == 28


def test_what_the_reader_reads_is_what_a_replay_writes():
    for event in (STREAM_EVENT, STRUCTURED_EVENT, CACHE_WRITE_EVENT, CACHE_READ_EVENT):
        usage = usage_from_event(event)
        assert usage_from_event(usage_metadata(usage)) == usage


def test_a_replayed_event_names_only_the_classes_the_call_used():
    plain = usage_metadata(CallUsage(input_tokens=7, output_tokens=3))
    counted = {"inputTokens": 7, "outputTokens": 3, "totalTokens": 10}
    assert plain == {"metadata": {"usage": counted}}
