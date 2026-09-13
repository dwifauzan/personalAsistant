"""Thread-safe session metrics used by the terminal dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock


@dataclass(frozen=True)
class UsageSnapshot:
    model_calls: int
    tool_calls: int
    input_chars: int
    output_chars: int
    backend: str
    started_at: datetime


_lock = Lock()
_started_at = datetime.now()
_model_calls = 0
_tool_calls = 0
_input_chars = 0
_output_chars = 0
_backend = "not connected"


def record_input(characters: int) -> None:
    global _input_chars
    with _lock:
        _input_chars += max(0, characters)


def record_model_call(backend: str) -> None:
    global _model_calls, _backend
    with _lock:
        _model_calls += 1
        _backend = backend


def record_tool_calls(count: int) -> None:
    global _tool_calls
    with _lock:
        _tool_calls += max(0, count)


def record_output(characters: int) -> None:
    global _output_chars
    with _lock:
        _output_chars += max(0, characters)


def snapshot() -> UsageSnapshot:
    with _lock:
        return UsageSnapshot(
            model_calls=_model_calls,
            tool_calls=_tool_calls,
            input_chars=_input_chars,
            output_chars=_output_chars,
            backend=_backend,
            started_at=_started_at,
        )
