import json

import pytest

from ai_os.latency_probe import measure


class Response:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    def iter_lines(self, **kwargs):
        return (json.dumps(event).encode() for event in self.events)


class Session:
    def __init__(self, events):
        self.events = events

    def post(self, *args, **kwargs):
        return Response(self.events)


def test_metrics_never_include_response_text():
    result = measure(
        Session(
            [
                {"message": {"content": "private text"}},
                {"done": True, "eval_count": 4, "eval_duration": 2_000_000_000},
            ]
        ),
        "unused",
        {},
    )
    assert result["tokens_per_s"] == 2 and result["first_token_s"] is not None
    assert "private" not in json.dumps(result)


def test_incomplete_stream_is_not_a_success():
    with pytest.raises(ValueError, match="without completion"):
        measure(Session([{"response": "partial"}]), "unused", {})
