"""Deterministic context, retrieval, leakage, budget, and skill relevance evals."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContextEvalCase:
    id: str
    expected_files: frozenset[str]
    selected_files: frozenset[str]
    relevant_skills: frozenset[str]
    selected_skills: frozenset[str]
    output: str
    leakage_canaries: tuple[str, ...]
    estimated_tokens: int
    max_tokens: int


@dataclass(frozen=True, slots=True)
class ContextEvalReport:
    router_version: str
    case_count: int
    file_precision: float
    file_recall: float
    exact_file_match: float
    skill_relevance: float
    leakage_free: float
    budget_compliance: float
    passed: bool

    def as_dict(self) -> dict:
        return {
            "schema": 1,
            "check": "context-eval",
            "router_version": self.router_version,
            "status": "pass" if self.passed else "fail",
            "ok": int(self.passed),
            "metrics": {
                "case_count": self.case_count,
                "file_precision": self.file_precision,
                "file_recall": self.file_recall,
                "exact_file_match": self.exact_file_match,
                "skill_relevance": self.skill_relevance,
                "leakage_free": self.leakage_free,
                "budget_compliance": self.budget_compliance,
            },
        }


def evaluate_context(cases: Iterable[ContextEvalCase], *, router_version: str) -> ContextEvalReport:
    rows = tuple(cases)
    if not router_version.strip() or not rows:
        raise ValueError("ROUTER_VERSION_AND_CASES_REQUIRED")
    if len({case.id for case in rows}) != len(rows) or any(not case.id.strip() for case in rows):
        raise ValueError("CASE_IDS_MUST_BE_UNIQUE")
    if any(
        type(case.estimated_tokens) is not int
        or type(case.max_tokens) is not int
        or case.estimated_tokens < 0
        or case.max_tokens < 1
        for case in rows
    ):
        raise ValueError("INVALID_CASE_BUDGET")

    true_positive = sum(len(case.expected_files & case.selected_files) for case in rows)
    selected = sum(len(case.selected_files) for case in rows)
    expected = sum(len(case.expected_files) for case in rows)
    file_precision = true_positive / selected if selected else float(expected == 0)
    file_recall = true_positive / expected if expected else float(selected == 0)
    exact_file_match = sum(case.expected_files == case.selected_files for case in rows) / len(rows)
    skill_total = sum(len(case.selected_skills) for case in rows)
    relevant = sum(len(case.relevant_skills & case.selected_skills) for case in rows)
    skill_relevance = relevant / skill_total if skill_total else float(
        all(not case.relevant_skills for case in rows)
    )
    leakage_free = sum(
        not any(canary and canary in case.output for canary in case.leakage_canaries)
        for case in rows
    ) / len(rows)
    budget_compliance = sum(case.estimated_tokens <= case.max_tokens for case in rows) / len(rows)
    passed = (
        file_precision == 1.0
        and file_recall == 1.0
        and skill_relevance == 1.0
        and leakage_free == 1.0
        and budget_compliance == 1.0
    )
    return ContextEvalReport(
        router_version,
        len(rows),
        file_precision,
        file_recall,
        exact_file_match,
        skill_relevance,
        leakage_free,
        budget_compliance,
        passed,
    )


def compare_context_reports(
    baseline: ContextEvalReport, candidate: ContextEvalReport
) -> tuple[bool, tuple[str, ...]]:
    """Reject any safety/quality regression; require one measured improvement."""
    if baseline.case_count != candidate.case_count:
        return False, ("CASE_COUNT_CHANGED",)
    regressions = []
    for name in (
        "file_precision",
        "file_recall",
        "exact_file_match",
        "skill_relevance",
        "leakage_free",
        "budget_compliance",
    ):
        if getattr(candidate, name) < getattr(baseline, name):
            regressions.append(f"{name.upper()}_REGRESSED")
    if not candidate.passed:
        regressions.append("CANDIDATE_SAFETY_GATE_FAILED")
    improvements = any(
        getattr(candidate, name) > getattr(baseline, name)
        for name in (
            "file_precision",
            "file_recall",
            "exact_file_match",
            "skill_relevance",
            "leakage_free",
            "budget_compliance",
        )
    )
    if not improvements:
        regressions.append("NO_MEASURED_IMPROVEMENT")
    return not regressions, tuple(regressions)
