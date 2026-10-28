"""Finite collaboration guard against loops, replayed messages, and runaway tools."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


class CollaborationLimitError(RuntimeError):
    pass


@dataclass(slots=True)
class CollaborationBudget:
    max_hops: int = 3
    max_calls: int = 20
    max_repeats: int = 1
    hops: int = 0
    calls: int = 0
    _messages: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            type(self.max_hops) is not int
            or self.max_hops < 0
            or type(self.max_calls) is not int
            or self.max_calls < 1
            or type(self.max_repeats) is not int
            or self.max_repeats < 0
        ):
            raise ValueError("INVALID_COLLABORATION_LIMIT")

    def observe_message(
        self, *, sender: str, content: str, human_or_external: bool = False
    ) -> None:
        if human_or_external:
            self.hops = 0
        elif sender.startswith("@"):
            self.hops += 1
            if self.hops > self.max_hops:
                raise CollaborationLimitError("MAX_AGENT_HOPS_EXCEEDED")
        normalized = re.sub(r"\s+", " ", content.strip()).casefold()
        digest = hashlib.sha256(normalized.encode()).hexdigest()
        self._messages[digest] = self._messages.get(digest, 0) + 1
        if self._messages[digest] > self.max_repeats + 1:
            raise CollaborationLimitError("REPEATED_MESSAGE_LIMIT_EXCEEDED")

    def consume_call(self) -> None:
        if self.calls >= self.max_calls:
            raise CollaborationLimitError("MAX_AGENT_CALLS_EXCEEDED")
        self.calls += 1

    def snapshot(self) -> dict[str, int]:
        return {"hops": self.hops, "calls": self.calls, "distinct_messages": len(self._messages)}
