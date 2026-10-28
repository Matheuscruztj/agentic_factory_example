"""Deterministic local workflow doubles with no network or model dependencies."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable


class FakeModel:
    def __init__(self, responses: list[str]) -> None:
        self._responses = deque(responses)
        self.calls = 0

    def invoke(self, _prompt: str) -> str:
        self.calls += 1
        if not self._responses:
            raise RuntimeError("FAKE_MODEL_EXHAUSTED")
        return self._responses.popleft()


class FakeTools:
    def __init__(self, handlers: dict[str, Callable[..., object]]) -> None:
        self._handlers = dict(handlers)
        self.calls: list[tuple[str, dict]] = []

    def invoke(self, name: str, **arguments):
        handler = self._handlers.get(name)
        if handler is None:
            raise PermissionError("FAKE_TOOL_NOT_REGISTERED")
        self.calls.append((name, dict(arguments)))
        return handler(**arguments)
