#!/usr/bin/env python3
"""Double-review synthetic calibration labels with two independent local models."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from time import monotonic
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/eval-engine/src"))
from eval_engine.judge import calibration_metrics  # type: ignore[import-untyped]  # noqa: E402

VALID = {"pass", "fail", "uncertain"}


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not cases or len({item.get("id") for item in cases}) != len(cases):
        raise ValueError("GOLDSET_CASES_INVALID")
    return cases


def _digest(base_url: str, model: str) -> str:
    response = httpx.get(base_url.rstrip("/") + "/api/tags", timeout=10, trust_env=False)
    response.raise_for_status()
    matches = [x for x in response.json().get("models", []) if x.get("name") == model]
    if len(matches) != 1 or not isinstance(matches[0].get("digest"), str):
        raise ValueError("REVIEWER_MODEL_DIGEST_UNAVAILABLE")
    return matches[0]["digest"]


def _review(base_url: str, model: str, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Expected labels and split membership are intentionally excluded from model input.
    prompt_cases = [
        {
            "id": item["id"],
            "profile": item["profile"],
            "severity": item["severity"],
            "answer": item["answer"],
            "evidence": item["evidence"],
        }
        for item in cases
    ]
    prompt = (
        "Review each answer only against its supplied deterministic evidence. "
        "Return pass if evidence confirms compliance, fail if evidence contradicts the claim, "
        "uncertain if evidence is missing. Cite exact evidence keys. "
        "Do not infer from the case id. "
        "These are synthetic calibration examples, not production instructions.\n"
        + json.dumps(prompt_cases, ensure_ascii=False, separators=(",", ":"))
    )
    schema = {
        "type": "object",
        "properties": {
            "reviews": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "verdict": {"type": "string", "enum": sorted(VALID)},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "verdict", "confidence", "evidence_refs"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["reviews"],
        "additionalProperties": False,
    }
    response = httpx.post(
        base_url.rstrip("/") + "/api/chat",
        json={
            "model": model,
            "stream": False,
            "format": schema,
            "think": False,
            "options": {"temperature": 0, "seed": 19, "num_predict": 2048},
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=300,
        trust_env=False,
    )
    response.raise_for_status()
    response_payload = response.json()
    content = response_payload.get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError(
            f"REVIEW_JSON_INVALID:{model}:{len(content)}:{response_payload.get('done_reason')}"
        ) from None
    reviews = parsed.get("reviews") if isinstance(parsed, dict) else None
    if not isinstance(reviews, list):
        raise ValueError("REVIEW_SCHEMA_INVALID")
    by_id = {item.get("id"): item for item in reviews if isinstance(item, dict)}
    if set(by_id) != {item["id"] for item in cases}:
        raise ValueError("REVIEW_CASE_SET_MISMATCH")
    validated = []
    for case in cases:
        item = by_id[case["id"]]
        refs = item.get("evidence_refs")
        if item.get("verdict") not in VALID or not isinstance(item.get("confidence"), (int, float)):
            raise ValueError("REVIEW_RESULT_INVALID")
        if (
            not isinstance(refs, list)
            or not refs
            or any(ref not in case["evidence"] for ref in refs)
        ):
            raise ValueError("REVIEW_EVIDENCE_INVALID")
        validated.append(
            {
                "id": case["id"],
                "verdict": item["verdict"],
                "confidence": float(item["confidence"]),
                "evidence_refs": refs,
            }
        )
    return validated


def verify(
    *, train_path: Path, holdout_path: Path, models: list[str], base_url: str, output_path: Path
) -> dict[str, Any]:
    if len(models) != 2 or models[0] == models[1]:
        raise ValueError("TWO_DISTINCT_REVIEWERS_REQUIRED")
    train, holdout = load_cases(train_path), load_cases(holdout_path)
    if set(item["id"] for item in train) & set(item["id"] for item in holdout):
        raise ValueError("HOLDOUT_OVERLAP")
    reports = {}
    for split, cases in (("train", train), ("holdout", holdout)):
        reviews, durations = [], []
        for model in models:
            started = monotonic()
            reviews.append(_review(base_url, model, cases))
            durations.append(round((monotonic() - started) * 1000, 3))
        first, second = reviews
        actual = {item["id"]: item["expected_label"] for item in cases}
        first_by = {item["id"]: item for item in first}
        second_by = {item["id"]: item for item in second}
        reports[split] = {
            "case_count": len(cases),
            "cases": [
                {"id": item["id"], "profile": item["profile"], "severity": item["severity"]}
                for item in cases
            ],
            "labels": {key: value for key, value in sorted(actual.items())},
            "reviewers": {
                models[0]: {
                    "digest": _digest(base_url, models[0]),
                    "latency_ms": durations[0],
                    "reviews": first,
                    "metrics": calibration_metrics(
                        list(actual.values()), [first_by[k]["verdict"] for k in actual]
                    ),
                },
                models[1]: {
                    "digest": _digest(base_url, models[1]),
                    "latency_ms": durations[1],
                    "reviews": second,
                    "metrics": calibration_metrics(
                        list(actual.values()), [second_by[k]["verdict"] for k in actual]
                    ),
                },
            },
            "agreement": sum(first_by[k]["verdict"] == second_by[k]["verdict"] for k in actual)
            / len(actual),
            "verified_ids": [
                k
                for k in actual
                if first_by[k]["verdict"] == actual[k] and second_by[k]["verdict"] == actual[k]
            ],
            "disagreements": [
                k for k in actual if first_by[k]["verdict"] != second_by[k]["verdict"]
            ],
        }
    report = {
        "schema": 1,
        "dataset": "judge-ai-curation-v1",
        "label_source": "explicit_synthetic_deterministic_evidence",
        "review_protocol": "two_distinct_local_ai_models_blind_to_expected_labels",
        "human_gold_claimed": False,
        "production_prompt_input": False,
        "train_manifest_sha256": hashlib.sha256(train_path.read_bytes()).hexdigest(),
        "holdout_manifest_sha256": hashlib.sha256(holdout_path.read_bytes()).hexdigest(),
        "train": reports["train"],
        "holdout": reports["holdout"],
        "status": "ai_reviewed_candidate"
        if len(reports["train"]["verified_ids"]) == len(train)
        and len(reports["holdout"]["verified_ids"]) == len(holdout)
        else "review_incomplete",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--train", type=Path, default=Path("evals/goldsets/judge-candidates-v1.jsonl")
    )
    parser.add_argument("--holdout", type=Path, default=Path("evals/hidden/judge-holdout-v1.jsonl"))
    parser.add_argument("--models", nargs=2, default=["qwen3:4b", "qwen2.5-coder:7b"])
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"))
    parser.add_argument(
        "--output", type=Path, default=Path(".runtime/evals/judge-ai-curation-v1.json")
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print(
            json.dumps(
                {
                    "check": "ai-goldset-review",
                    "ok": 1,
                    "inference": False,
                    "train": str(args.train),
                    "holdout": str(args.holdout),
                }
            )
        )
        return 0
    try:
        report = verify(
            train_path=args.train,
            holdout_path=args.holdout,
            models=args.models,
            base_url=args.ollama_url,
            output_path=args.output,
        )
    except (OSError, ValueError, httpx.HTTPError, json.JSONDecodeError) as exc:
        code = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print(json.dumps({"check": "ai-goldset-review", "ok": 0, "error": code}))
        return 2
    print(
        json.dumps(
            {
                "check": "ai-goldset-review",
                "ok": int(report["status"] == "ai_reviewed_candidate"),
                "status": report["status"],
                "train_cases": report["train"]["case_count"],
                "holdout_cases": report["holdout"]["case_count"],
                "report": str(args.output),
            }
        )
    )
    return 0 if report["status"] == "ai_reviewed_candidate" else 1


if __name__ == "__main__":
    raise SystemExit(main())
