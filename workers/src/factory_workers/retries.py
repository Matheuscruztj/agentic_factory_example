"""Idempotent retry/DLQ policy for transient workflow failures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

FailureKind = Literal["llm_transient", "infrastructure_transient", "invalid_data", "policy"]


@dataclass(frozen=True, slots=True)
class RetryDecision:
    state: str
    attempt: int
    available_at: datetime | None
    idempotency_key: str


def plan_retry(
    *, task_id: str, operation_key: str, attempt: int, max_attempts: int,
    now: datetime, base_delay_seconds: int = 5,
    failure_kind: FailureKind = "infrastructure_transient",
) -> RetryDecision:
    if (
        not task_id or not operation_key
        or type(attempt) is not int or attempt < 1
        or type(max_attempts) is not int or max_attempts < 1
        or type(base_delay_seconds) is not int or not 1 <= base_delay_seconds <= 3600
    ):
        raise ValueError("INVALID_RETRY_REQUEST")
    key = f"{task_id}:{operation_key}"
    if failure_kind in {"invalid_data", "policy"}:
        return RetryDecision("dead_letter", attempt, None, key)
    if failure_kind not in {"llm_transient", "infrastructure_transient"}:
        raise ValueError("INVALID_FAILURE_KIND")
    if attempt >= max_attempts:
        return RetryDecision("dead_letter", attempt, None, key)
    delay = min(base_delay_seconds * (2 ** min(attempt - 1, 16)), 3600)
    return RetryDecision("retry_wait", attempt + 1, now + timedelta(seconds=delay), key)
