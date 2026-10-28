"""Optional independent Ollama judge with strict evidence-bound output."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class JudgeVerdict:
    schema: int
    judge_model: str
    executor_model: str
    score: int
    confidence: float
    verdict: str
    rationale: str
    evidence_refs: tuple[str, ...]
    human_review_required: bool
    prompt_sha256: str = ""
    response_sha256: str = ""
    raw_response: str = ""


@dataclass(frozen=True)
class AcceptanceVerdict:
    schema: int
    judge_model: str
    executor_model: str
    confidence: float
    verdict: str
    rationale: str
    evidence_refs: tuple[str, ...]
    human_review_required: bool
    prompt_sha256: str = ""
    response_sha256: str = ""
    raw_response: str = ""


class JudgeError(ValueError):
    pass


def build_judge_prompt(
    *, executor_model: str, answer: str, evidence: dict[str, str], rubric: dict[str, Any]
) -> str:
    return json.dumps(
        {
            "task": "Judge the supplied answer against the rubric and evidence only.",
            "output_instructions": "Return one JSON object with exactly these fields: "
            "schema, judge_model, executor_model, score (integer 1..5), confidence "
            "(0..1), verdict (pass|fail|uncertain), rationale, evidence_refs "
            "(known evidence keys only), human_review_required (boolean). "
            "Score anchors: 5 means all criteria are directly supported, 4 means support with "
            "minor non-blocking gaps, 3 means material uncertainty, 2 means substantial work is "
            "missing, and 1 means the evidence contradicts the claim. A pass requires score 4 "
            "or 5; a score 1 or 2 cannot be pass. "
            "Set human_review_required=true when confidence is 0.75 or lower, or uncertain. "
            "Apply this decision order: (1) if supplied evidence directly contradicts a "
            "factual claim in the answer, verdict must be fail and cite that evidence; "
            "(2) if evidence is missing, incomplete, or ambiguous, verdict must be uncertain; "
            "(3) otherwise rate the supported answer. Unsupported is not disproven: missing "
            "evidence alone is not proof of failure. A tentative claim with no test result is "
            "uncertain. Do not use uncertain to soften a directly disproven claim. An answer "
            "that calls an endpoint safe while evidence shows credential disclosure is a fail, "
            "not uncertain.",
            "rubric": rubric,
            "answer": answer,
            "allowed_evidence_refs": list(evidence),
            "evidence": evidence,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def build_acceptance_prompt(
    *, executor_model: str, answer: str, evidence: dict[str, str], rubric: dict[str, Any]
) -> str:
    return json.dumps(
        {
            "task": "Decide whether the recorded activity acceptance criteria are met.",
            "output_instructions": (
                "Return exactly one JSON object with fields schema, judge_model, executor_model, "
                "confidence (0..1), verdict (pass|fail|uncertain), rationale, evidence_refs, "
                "human_review_required. Do not return a numeric score. evidence_refs must be "
                "exact strings copied from allowed_evidence_refs. Pass only if every recorded "
                "criterion is directly supported by implementation evidence and all required "
                "gates. Missing or ambiguous support is uncertain. Contradicting evidence is fail. "
                "Set human_review_required for uncertain or confidence below 0.8."
            ),
            "rubric": rubric,
            "answer": answer,
            "allowed_evidence_refs": list(evidence),
            "evidence": evidence,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def acceptance_output_schema(
    *, judge_model: str, executor_model: str, evidence_refs: list[str]
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "schema": {"type": "integer", "const": 1},
            "judge_model": {"type": "string", "const": judge_model},
            "executor_model": {"type": "string", "const": executor_model},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "verdict": {"type": "string", "enum": ["pass", "fail", "uncertain"]},
            "rationale": {"type": "string"},
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "enum": evidence_refs},
            },
            "human_review_required": {"type": "boolean"},
        },
        "required": [
            "schema",
            "judge_model",
            "executor_model",
            "confidence",
            "verdict",
            "rationale",
            "evidence_refs",
            "human_review_required",
        ],
        "additionalProperties": False,
    }


def validate_acceptance_verdict(
    value: dict[str, Any],
    *,
    allowed_evidence: set[str],
    executor_model: str,
    evidence_values: dict[str, str] | None = None,
) -> AcceptanceVerdict:
    required = {
        "schema",
        "judge_model",
        "executor_model",
        "confidence",
        "verdict",
        "rationale",
        "evidence_refs",
        "human_review_required",
    }
    if set(value) != required or value.get("schema") != 1:
        raise JudgeError("ACCEPTANCE_SCHEMA_INVALID")
    if not isinstance(value["judge_model"], str) or value["judge_model"] == executor_model:
        raise JudgeError("JUDGE_MUST_DIFFER_FROM_EXECUTOR")
    if value["executor_model"] != executor_model:
        raise JudgeError("EXECUTOR_BINDING_MISMATCH")
    confidence = value["confidence"]
    if type(confidence) not in (float, int) or not 0 <= confidence <= 1:
        raise JudgeError("CONFIDENCE_INVALID")
    if value["verdict"] not in {"pass", "fail", "uncertain"}:
        raise JudgeError("VERDICT_INVALID")
    if not isinstance(value["rationale"], str) or not value["rationale"].strip():
        raise JudgeError("RATIONALE_REQUIRED")
    refs = value["evidence_refs"]
    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
        raise JudgeError("EVIDENCE_REFS_INVALID")
    normalized_refs = _normalize_evidence_refs(
        refs, allowed_evidence=allowed_evidence, evidence_values=evidence_values
    )
    verdict = value["verdict"] if normalized_refs else "uncertain"
    requires_review = verdict == "uncertain" or confidence < 0.8
    if type(value["human_review_required"]) is not bool:
        raise JudgeError("HUMAN_ESCALATION_REQUIRED")
    return AcceptanceVerdict(
        schema=1,
        judge_model=value["judge_model"],
        executor_model=executor_model,
        confidence=float(confidence),
        verdict=verdict,
        rationale=value["rationale"].strip(),
        evidence_refs=tuple(normalized_refs),
        human_review_required=value["human_review_required"] or requires_review,
    )


def _normalize_evidence_refs(
    refs: list[str],
    *,
    allowed_evidence: set[str],
    evidence_values: dict[str, str] | None,
) -> list[str]:
    normalized_refs: list[str] = []
    for ref in refs:
        if ref in allowed_evidence:
            normalized_refs.append(ref)
            continue
        named_gate = re.fullmatch(r"(gate:[0-9]+):[ \t]*([A-Za-z0-9_-]+)", ref)
        if (
            named_gate
            and named_gate.group(1) in allowed_evidence
            and named_gate.group(2)[0].isalnum()
            and evidence_values is not None
        ):
            key, cited_name = named_gate.groups()
            try:
                expected_gate = json.loads(evidence_values[key])
            except (KeyError, json.JSONDecodeError):
                raise JudgeError("UNKNOWN_EVIDENCE_REFERENCE") from None
            if isinstance(expected_gate, dict) and expected_gate.get("name") == cited_name:
                normalized_refs.append(key)
                continue
        status_gate = re.fullmatch(
            r"(gate:[0-9]+):[ \t]*status[ \t]*:?[ \t]*"
            r"(?:'(?P<single>pass|fail|uncertain)'|\"(?P<double>pass|fail|uncertain)\"|"
            r"(?P<bare>pass|fail|uncertain))",
            ref,
        )
        if status_gate and status_gate.group(1) in allowed_evidence and evidence_values is not None:
            key = status_gate.group(1)
            cited_status = (
                status_gate.group("single")
                or status_gate.group("double")
                or status_gate.group("bare")
            )
            try:
                expected_gate = json.loads(evidence_values[key])
            except (KeyError, json.JSONDecodeError):
                raise JudgeError("UNKNOWN_EVIDENCE_REFERENCE") from None
            if isinstance(expected_gate, dict) and expected_gate.get("status") == cited_status:
                normalized_refs.append(key)
                continue
        # Accept a copied gate object only when it exactly matches the evidence.
        match = re.fullmatch(r"(gate:\d+):\s*(\{.*\})", ref, flags=re.DOTALL)
        if match and match.group(1) in allowed_evidence and evidence_values is not None:
            key, copied = match.groups()
            try:
                expected = json.loads(evidence_values[key])
                actual = json.loads(copied)
            except (KeyError, json.JSONDecodeError):
                raise JudgeError("UNKNOWN_EVIDENCE_REFERENCE") from None
            if actual == expected:
                normalized_refs.append(key)
                continue
        raise JudgeError("UNKNOWN_EVIDENCE_REFERENCE")
    return normalized_refs


def validate_verdict(
    value: dict[str, Any],
    *,
    allowed_evidence: set[str],
    executor_model: str,
    evidence_values: dict[str, str] | None = None,
) -> JudgeVerdict:
    required = {
        "schema",
        "judge_model",
        "executor_model",
        "score",
        "confidence",
        "verdict",
        "rationale",
        "evidence_refs",
        "human_review_required",
    }
    if set(value) != required or value.get("schema") != 1:
        raise JudgeError("SCHEMA_INVALID")
    if not isinstance(value["judge_model"], str) or value["judge_model"] == executor_model:
        raise JudgeError("JUDGE_MUST_DIFFER_FROM_EXECUTOR")
    if value["executor_model"] != executor_model:
        raise JudgeError("EXECUTOR_BINDING_MISMATCH")
    if type(value["score"]) is not int or value["score"] not in range(1, 6):
        raise JudgeError("SCORE_INVALID")
    confidence = value["confidence"]
    if type(confidence) not in (float, int) or not 0 <= confidence <= 1:
        raise JudgeError("CONFIDENCE_INVALID")
    if value["verdict"] not in {"pass", "fail", "uncertain"}:
        raise JudgeError("VERDICT_INVALID")
    if not isinstance(value["rationale"], str) or not value["rationale"].strip():
        raise JudgeError("RATIONALE_REQUIRED")
    refs = value["evidence_refs"]
    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
        raise JudgeError("EVIDENCE_REFS_INVALID")
    normalized_refs = _normalize_evidence_refs(
        refs, allowed_evidence=allowed_evidence, evidence_values=evidence_values
    )
    # A verdict without a citation cannot be grounded in the supplied evidence.
    # Treat it as unresolved instead of letting the model infer failure from
    # missing observations (or pass from unsupported confidence).
    verdict = value["verdict"] if normalized_refs else "uncertain"
    if (verdict == "pass" and value["score"] < 4) or (verdict == "fail" and value["score"] > 2):
        verdict = "uncertain"
    requires_human = verdict == "uncertain" or confidence <= 0.75
    if type(value["human_review_required"]) is not bool:
        raise JudgeError("HUMAN_ESCALATION_REQUIRED")
    return JudgeVerdict(
        schema=1,
        judge_model=value["judge_model"],
        executor_model=executor_model,
        score=value["score"],
        confidence=float(confidence),
        verdict=verdict,
        rationale=value["rationale"].strip(),
        evidence_refs=tuple(normalized_refs),
        # Enforce escalation in code even when the model omits the flag.
        human_review_required=value["human_review_required"] or requires_human,
    )


class OllamaJudge:
    """Ask a distinct local model for scored review or binary evidence acceptance."""

    def __init__(self, *, base_url: str, model: str, timeout_seconds: float = 60) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise JudgeError("OLLAMA_URL_MUST_BE_LOOPBACK")
        if timeout_seconds <= 0:
            raise JudgeError("JUDGE_TIMEOUT_INVALID")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def _complete(
        self, *, prompt: str, output_schema: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "format": output_schema,
                    "think": False,
                    "options": {"temperature": 0, "seed": 7},
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.timeout_seconds,
                trust_env=False,
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            parsed = json.loads(content)
        except httpx.HTTPError as exc:
            raise JudgeError("OLLAMA_REQUEST_FAILED") from exc
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise JudgeError("JUDGE_RESPONSE_INVALID") from exc
        if not isinstance(parsed, dict):
            raise JudgeError("JUDGE_RESPONSE_INVALID")
        return content, parsed

    def judge(
        self, *, executor_model: str, answer: str, evidence: dict[str, str], rubric: dict[str, Any]
    ) -> JudgeVerdict:
        if self.model == executor_model:
            raise JudgeError("JUDGE_MUST_DIFFER_FROM_EXECUTOR")
        prompt = build_judge_prompt(
            executor_model=executor_model, answer=answer, evidence=evidence, rubric=rubric
        )
        output_schema = {
            "type": "object",
            "properties": {
                "schema": {"type": "integer", "const": 1},
                "judge_model": {"type": "string", "const": self.model},
                "executor_model": {"type": "string", "const": executor_model},
                "score": {
                    "type": "integer",
                    "enum": [1, 2, 3, 4, 5],
                    "description": (
                        "5 fully supported; 4 minor gaps; 3 uncertain; 2 substantial gap; "
                        "1 contradicted."
                    ),
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "verdict": {"type": "string", "enum": ["pass", "fail", "uncertain"]},
                "rationale": {"type": "string"},
                "evidence_refs": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(evidence)},
                },
                "human_review_required": {"type": "boolean"},
            },
            "required": [
                "schema",
                "judge_model",
                "executor_model",
                "score",
                "confidence",
                "verdict",
                "rationale",
                "evidence_refs",
                "human_review_required",
            ],
            "additionalProperties": False,
        }
        content, parsed = self._complete(prompt=prompt, output_schema=output_schema)
        verdict = validate_verdict(
            parsed,
            allowed_evidence=set(evidence),
            executor_model=executor_model,
            evidence_values=evidence,
        )
        return replace(
            verdict,
            prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
            response_sha256=hashlib.sha256(content.encode()).hexdigest(),
            raw_response=content,
        )

    def accept(
        self, *, executor_model: str, answer: str, evidence: dict[str, str], rubric: dict[str, Any]
    ) -> AcceptanceVerdict:
        if self.model == executor_model:
            raise JudgeError("JUDGE_MUST_DIFFER_FROM_EXECUTOR")
        prompt = build_acceptance_prompt(
            executor_model=executor_model, answer=answer, evidence=evidence, rubric=rubric
        )
        output_schema = acceptance_output_schema(
            judge_model=self.model, executor_model=executor_model, evidence_refs=list(evidence)
        )
        content, parsed = self._complete(prompt=prompt, output_schema=output_schema)
        verdict = validate_acceptance_verdict(
            parsed,
            allowed_evidence=set(evidence),
            executor_model=executor_model,
            evidence_values=evidence,
        )
        return replace(
            verdict,
            prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
            response_sha256=hashlib.sha256(content.encode()).hexdigest(),
            raw_response=content,
        )


def calibration_metrics(gold: list[str], judged: list[str]) -> dict[str, float | int]:
    if len(gold) != len(judged) or not gold:
        raise JudgeError("CALIBRATION_DATASET_INVALID")
    positives = sum(label == "pass" for label in gold)
    true_positive = sum(
        expected == actual == "pass" for expected, actual in zip(gold, judged, strict=True)
    )
    false_positive = sum(
        expected != "pass" and actual == "pass"
        for expected, actual in zip(gold, judged, strict=True)
    )
    accuracy = sum(expected == actual for expected, actual in zip(gold, judged, strict=True)) / len(
        gold
    )
    return {
        "cases": len(gold),
        "accuracy": accuracy,
        "false_positive_rate": false_positive / max(1, len(gold) - positives),
        "recall": true_positive / max(1, positives),
    }
