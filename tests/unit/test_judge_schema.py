import json

import pytest
from eval_engine.judge import (
    JudgeError,
    OllamaJudge,
    calibration_metrics,
    validate_acceptance_verdict,
    validate_verdict,
)


def test_judge_requires_distinct_executor_and_known_evidence():
    value = {
        "schema": 1,
        "judge_model": "judge-b",
        "executor_model": "executor-a",
        "score": 4,
        "confidence": 0.9,
        "verdict": "pass",
        "rationale": "Evidence supports the result.",
        "evidence_refs": ["artifact:tests"],
        "human_review_required": False,
    }
    result = validate_verdict(
        value, allowed_evidence={"artifact:tests"}, executor_model="executor-a"
    )
    assert result.judge_model == "judge-b"
    with pytest.raises(JudgeError, match="UNKNOWN_EVIDENCE"):
        validate_verdict(value, allowed_evidence=set(), executor_model="executor-a")
    with pytest.raises(JudgeError, match="MUST_DIFFER"):
        validate_verdict(
            {**value, "judge_model": "executor-a"},
            allowed_evidence={"artifact:tests"},
            executor_model="executor-a",
        )


def test_low_confidence_escalates_and_calibration_is_report_only():
    uncertain = {
        "schema": 1,
        "judge_model": "judge-b",
        "executor_model": "executor-a",
        "score": 3,
        "confidence": 0.5,
        "verdict": "uncertain",
        "rationale": "Evidence is ambiguous.",
        "evidence_refs": ["artifact:tests"],
        "human_review_required": True,
    }
    assert validate_verdict(
        uncertain, allowed_evidence={"artifact:tests"}, executor_model="executor-a"
    ).human_review_required
    assert validate_verdict(
        {**uncertain, "human_review_required": False},
        allowed_evidence={"artifact:tests"},
        executor_model="executor-a",
    ).human_review_required
    assert calibration_metrics(["pass", "reject"], ["pass", "pass"]) == {
        "cases": 2,
        "accuracy": 0.5,
        "false_positive_rate": 1.0,
        "recall": 1.0,
    }


def test_gate_reference_with_json_copy_is_normalized_only_when_exact():
    gate = {"activity_id": "FAC-999", "status": "pass"}
    evidence_text = '{"activity_id": "FAC-999", "status": "pass"}'
    value = {
        "schema": 1,
        "judge_model": "judge-b",
        "executor_model": "executor-a",
        "score": 5,
        "confidence": 0.95,
        "verdict": "pass",
        "rationale": "The gate passed.",
        "evidence_refs": [f"gate:1: {evidence_text}"],
        "human_review_required": False,
    }
    result = validate_verdict(
        value,
        allowed_evidence={"gate:1"},
        executor_model="executor-a",
        evidence_values={"gate:1": json.dumps(gate, sort_keys=True)},
    )
    assert result.evidence_refs == ("gate:1",)
    with pytest.raises(JudgeError, match="UNKNOWN_EVIDENCE"):
        validate_verdict(
            {**value, "evidence_refs": ["gate:1: {\"status\": \"failed\"}"]},
            allowed_evidence={"gate:1"},
            executor_model="executor-a",
            evidence_values={"gate:1": json.dumps(gate, sort_keys=True)},
        )


def test_named_gate_reference_is_normalized_only_when_name_matches():
    gate = {"activity_id": "FAC-999", "name": "component-scope-boundary", "status": "pass"}
    evidence = {"gate:1": json.dumps(gate, sort_keys=True)}
    value = {
        "schema": 1,
        "judge_model": "judge-b",
        "executor_model": "executor-a",
        "score": 5,
        "confidence": 0.95,
        "verdict": "pass",
        "rationale": "The cited gate passed.",
        "evidence_refs": ["gate:1: component-scope-boundary"],
        "human_review_required": False,
    }
    result = validate_verdict(
        value, allowed_evidence=set(evidence), executor_model="executor-a", evidence_values=evidence
    )
    assert result.evidence_refs == ("gate:1",)
    with pytest.raises(JudgeError, match="UNKNOWN_EVIDENCE"):
        validate_verdict(
            {**value, "evidence_refs": ["gate:1:next-wave-focused-tests"]},
            allowed_evidence=set(evidence),
            executor_model="executor-a",
            evidence_values=evidence,
        )


def test_named_gate_reference_is_supported_for_binary_acceptance():
    gate = {"activity_id": "FAC-999", "name": "current-required-core-gates", "status": "pass"}
    evidence = {"gate:1": json.dumps(gate, sort_keys=True)}
    value = {
        "schema": 1,
        "judge_model": "judge-b",
        "executor_model": "executor-a",
        "confidence": 0.95,
        "verdict": "pass",
        "rationale": "The cited gate passed.",
        "evidence_refs": ["gate:1:current-required-core-gates"],
        "human_review_required": False,
    }
    result = validate_acceptance_verdict(
        value, allowed_evidence=set(evidence), executor_model="executor-a", evidence_values=evidence
    )
    assert result.evidence_refs == ("gate:1",)


def test_gate_status_reference_is_normalized_only_when_status_matches():
    gate = {"activity_id": "FAC-999", "name": "security", "status": "pass"}
    evidence = {"gate:1": json.dumps(gate, sort_keys=True)}
    value = {
        "schema": 1,
        "judge_model": "judge-b",
        "executor_model": "executor-a",
        "confidence": 0.95,
        "verdict": "pass",
        "rationale": "The cited gate passed.",
        "evidence_refs": ["gate:1: status: pass"],
        "human_review_required": False,
    }
    result = validate_acceptance_verdict(
        value, allowed_evidence=set(evidence), executor_model="executor-a", evidence_values=evidence
    )
    assert result.evidence_refs == ("gate:1",)
    quoted = validate_acceptance_verdict(
        {**value, "evidence_refs": ["gate:1: status 'pass'"]},
        allowed_evidence=set(evidence), executor_model="executor-a", evidence_values=evidence,
    )
    assert quoted.evidence_refs == ("gate:1",)
    with pytest.raises(JudgeError, match="UNKNOWN_EVIDENCE"):
        validate_acceptance_verdict(
            {**value, "evidence_refs": ["gate:1: status: fail"]},
            allowed_evidence=set(evidence),
            executor_model="executor-a",
            evidence_values=evidence,
        )
    with pytest.raises(JudgeError, match="UNKNOWN_EVIDENCE"):
        validate_acceptance_verdict(
            {**value, "evidence_refs": ["gate:1: status 'fail'"]},
            allowed_evidence=set(evidence), executor_model="executor-a", evidence_values=evidence,
        )


def test_inconsistent_pass_and_low_score_is_escalated():
    result = validate_verdict(
        {
            "schema": 1,
            "judge_model": "judge-b",
            "executor_model": "executor-a",
            "score": 1,
            "confidence": 0.95,
            "verdict": "pass",
            "rationale": "The evidence supports acceptance.",
            "evidence_refs": ["artifact:tests"],
            "human_review_required": False,
        },
        allowed_evidence={"artifact:tests"},
        executor_model="executor-a",
    )
    assert result.verdict == "uncertain"
    assert result.human_review_required is True


def test_binary_acceptance_requires_exact_evidence_and_escalates_low_confidence():
    value = {
        "schema": 1,
        "judge_model": "judge-b",
        "executor_model": "executor-a",
        "confidence": 0.79,
        "verdict": "pass",
        "rationale": "The test artifact directly supports the criterion.",
        "evidence_refs": ["artifact:tests"],
        "human_review_required": False,
    }
    accepted = validate_acceptance_verdict(
        value,
        allowed_evidence={"artifact:tests"},
        executor_model="executor-a",
    )
    assert accepted.verdict == "pass"
    assert accepted.human_review_required is True
    with pytest.raises(JudgeError, match="ACCEPTANCE_SCHEMA_INVALID"):
        validate_acceptance_verdict(
            {**value, "score": 5},
            allowed_evidence={"artifact:tests"},
            executor_model="executor-a",
        )


def test_judge_transport_rejects_remote_endpoint():
    with pytest.raises(JudgeError, match="LOOPBACK"):
        OllamaJudge(base_url="https://public.example/api", model="judge-b")
