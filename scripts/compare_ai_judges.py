#!/usr/bin/env python3
"""Compare two binary Judge reports with confusion, critical misses, and uncertainty."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _case_index(path: Path) -> dict[str, dict]:
    items = [
        json.loads(line) for line in path.read_text().splitlines() if line.strip()
    ]
    if any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in items):
        raise ValueError("JUDGE_CASE_SCHEMA_INVALID")
    indexed = {item["id"]: item for item in items}
    if len(indexed) != len(items):
        raise ValueError("JUDGE_CASE_ID_DUPLICATE")
    return indexed


_VERDICTS = {"pass", "fail", "uncertain"}


def _rates(case_ids: list[str], cases: dict[str, dict], labels: dict, reviews: dict) -> dict:
    """Report operational denominators explicitly; None means no applicable cases."""
    critical_positive = [
        case_id
        for case_id in case_ids
        if cases[case_id].get("severity") == "critical" and labels[case_id] == "fail"
    ]
    negative = [case_id for case_id in case_ids if labels[case_id] == "pass"]
    critical_misses = [case_id for case_id in critical_positive if reviews[case_id] == "pass"]
    false_rejections = [case_id for case_id in negative if reviews[case_id] == "fail"]
    covered = [case_id for case_id in case_ids if reviews[case_id] != "uncertain"]
    return {
        "judgments": len(case_ids),
        "coverage": len(covered) / len(case_ids) if case_ids else None,
        "abstentions": len(case_ids) - len(covered),
        "false_rejects": len(false_rejections),
        "false_reject_denominator": len(negative),
        "false_reject_rate": len(false_rejections) / len(negative) if negative else None,
        "critical_false_negatives": len(critical_misses),
        "critical_positive_denominator": len(critical_positive),
        "critical_false_negative_rate": (
            len(critical_misses) / len(critical_positive) if critical_positive else None
        ),
    }


def compare(source: dict, *, train_path: Path, holdout_path: Path) -> dict:
    case_data = {"train": _case_index(train_path), "holdout": _case_index(holdout_path)}
    splits = {}
    for split_name in ("train", "holdout"):
        split = source[split_name]
        labels = split["labels"]
        reviewers = split["reviewers"]
        model_names = list(reviewers)
        if len(model_names) != 2 or model_names[0] == model_names[1]:
            raise ValueError("TWO_DISTINCT_JUDGES_REQUIRED")
        case_ids = list(case_data[split_name])
        expected_ids = set(case_ids)
        if set(labels) != expected_ids or any(label not in _VERDICTS for label in labels.values()):
            raise ValueError("JUDGE_LABEL_COVERAGE_INVALID")
        per_model = {}
        by_model = {}
        for model in model_names:
            review_items = reviewers[model]["reviews"]
            if not isinstance(review_items, list) or any(
                not isinstance(item, dict)
                or not isinstance(item.get("id"), str)
                or item.get("verdict") not in _VERDICTS
                for item in review_items
            ):
                raise ValueError("JUDGE_REVIEW_SCHEMA_INVALID")
            reviews = {item["id"]: item for item in review_items}
            if len(reviews) != len(review_items) or set(reviews) != expected_ids:
                raise ValueError("JUDGE_REVIEW_COVERAGE_INVALID")
            verdicts = {case_id: reviews[case_id]["verdict"] for case_id in case_ids}
            confusion = {
                gold: {pred: 0 for pred in ("pass", "fail", "uncertain")}
                for gold in ("pass", "fail", "uncertain")
            }
            critical_false_negative = []
            for case_id, case in case_data[split_name].items():
                gold, predicted = labels[case_id], verdicts[case_id]
                confusion[gold][predicted] += 1
                if case["severity"] == "critical" and gold == "fail" and predicted == "pass":
                    critical_false_negative.append(case_id)
            per_model[model] = {
                "confusion_matrix": confusion,
                "accuracy_vs_synthetic_oracle": sum(
                    labels[item["id"]] == reviews[item["id"]]["verdict"]
                    for item in case_data[split_name].values()
                )
                / max(1, len(reviews)),
                "critical_false_negative_ids": critical_false_negative,
                "rates": _rates(case_ids, case_data[split_name], labels, verdicts),
                "latency_ms": reviewers[model].get("latency_ms"),
                "calibration_metrics": reviewers[model]["metrics"],
            }
            by_model[model] = reviews
        divergences = [
            {
                "case_id": case["id"],
                "expected": labels[case["id"]],
                model_names[0]: by_model[model_names[0]][case["id"]]["verdict"],
                model_names[1]: by_model[model_names[1]][case["id"]]["verdict"],
            }
            for case in case_data[split_name].values()
            if by_model[model_names[0]][case["id"]]["verdict"]
            != by_model[model_names[1]][case["id"]]["verdict"]
        ]
        split_agreement = 1 - len(divergences) / max(1, len(case_data[split_name]))
        splits[split_name] = {
            "cases": len(case_data[split_name]),
            "reviewers": per_model,
            "agreement": split_agreement,
            "divergences": divergences,
            "human_agreement": None,
            "human_agreement_status": "unavailable_no_human_labels",
        }
    return {
        "schema": 1,
        "dataset": source["dataset"],
        "review_protocol": source["review_protocol"],
        "human_gold_claimed": False,
        "splits": splits,
        "status": "comparison_report_only",
        "promotion_eligible": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--train", type=Path, default=Path("evals/goldsets/judge-candidates-v1.jsonl")
    )
    parser.add_argument("--holdout", type=Path, default=Path("evals/hidden/judge-holdout-v1.jsonl"))
    parser.add_argument("--output", type=Path, default=Path(".runtime/evals/judge-comparison.json"))
    args = parser.parse_args()
    try:
        report = compare(
            json.loads(args.source.read_text()), train_path=args.train, holdout_path=args.holdout
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"check": "judge-comparison", "ok": 0, "error": type(exc).__name__}))
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "check": "judge-comparison",
                "ok": 1,
                "train_divergences": len(report["splits"]["train"]["divergences"]),
                "holdout_divergences": len(report["splits"]["holdout"]["divergences"]),
                "human_agreement": "unavailable",
                "report": str(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
