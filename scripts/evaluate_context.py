#!/usr/bin/env python3
"""Run deterministic router/context regression fixtures against a recorded baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/context-engine/src"))

from context_engine.discovery import EvidenceStatus, discover_demand  # noqa: E402
from context_engine.evals import (  # noqa: E402
    ContextEvalCase,
    compare_context_reports,
    evaluate_context,
)
from context_engine.pack import build_context_pack  # noqa: E402
from context_engine.router import route_skills  # noqa: E402
from context_engine.skill_registry import load_registry  # noqa: E402


def _legacy_skills(text: str, demand_type: str, registry) -> frozenset[str]:
    lowered = text.lower()
    matches = []
    for skill in registry:
        count = sum(trigger.lower() in lowered for trigger in skill.triggers)
        if count:
            matches.append((count / max(skill.weight, 1), skill.id))
    if demand_type == "question" and not any(
        word in lowered for word in ("implement", "build", "test", "plan", "api", "ui")
    ):
        return frozenset()
    matches.sort(key=lambda row: (-row[0], row[1]))
    return frozenset(skill_id for _, skill_id in matches[:2])


def _cases(data: dict, skills, *, hardened: bool) -> list[ContextEvalCase]:
    rows = []
    for item in data["cases"]:
        inventory = {path: "fixture" for path in item["repository_files"]}
        discovery = discover_demand(
            item["text"], repository_files=inventory, sha="a" * 40
        )
        selected_files = frozenset(
            evidence.source
            for evidence in discovery.evidence
            if evidence.status is EvidenceStatus.VERIFIED and evidence.source
        )
        if hardened:
            try:
                selected_skills = frozenset(
                    route_skills(
                    item["text"],
                    demand_type=item["demand_type"],
                    role=item["role"],
                    paths=tuple(selected_files),
                    registry=skills,
                )
                )
            except ValueError as exc:
                if str(exc) != "UNTRUSTED_SKILL_ACTIVATION_REJECTED":
                    raise
                selected_skills = frozenset()
        else:
            selected_skills = _legacy_skills(item["text"], item["demand_type"], skills)
        snippets = [
            {"path": path, "sha": "a" * 40, "text": inventory[path]}
            for path in selected_files
        ]
        task = {"id": item["id"], "title": item["text"], "git_commit": "a" * 40}
        if hardened:
            pack = build_context_pack(
                task=task,
                skills=[{"id": skill_id} for skill_id in sorted(selected_skills)],
                snippets=snippets,
                allowed_paths=set(item["repository_files"]),
                max_tokens=item["max_tokens"],
            )
            output = json.dumps(pack.content, sort_keys=True)
            token_count = pack.estimated_tokens
        else:
            payload = {
                "L0": task,
                "L1": [{"id": skill_id} for skill_id in sorted(selected_skills)],
                "L2": snippets,
                "L3": [],
                "sources": [snippet["path"] for snippet in snippets],
            }
            encoded = json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            output = json.dumps(payload, sort_keys=True)
            token_count = max(1, (len(encoded) + 3) // 4)
        rows.append(
            ContextEvalCase(
                id=item["id"],
                expected_files=frozenset(item["expected_files"]),
                selected_files=selected_files,
                relevant_skills=frozenset(item["expected_skills"]),
                selected_skills=selected_skills,
                output=output,
                leakage_canaries=tuple(item["canaries"]),
                estimated_tokens=token_count,
                max_tokens=item["max_tokens"],
            )
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=ROOT / "evals/fixtures/context/regression-v1.json",
    )
    parser.add_argument("--router-version", default="context-router-v1")
    args = parser.parse_args()
    try:
        fixtures = json.loads(args.fixtures.read_text(encoding="utf-8"))
        if (
            not isinstance(fixtures, dict)
            or fixtures.get("schema") != 1
            or not isinstance(fixtures.get("cases"), list)
            or not fixtures["cases"]
        ):
            raise ValueError("INVALID_CONTEXT_FIXTURES")
        registry = load_registry(ROOT / "agents/skills/registry.yaml")
        baseline = evaluate_context(
            _cases(fixtures, registry, hardened=False),
            router_version="context-router-v0-baseline",
        )
        candidate = evaluate_context(
            _cases(fixtures, registry, hardened=True), router_version=args.router_version
        )
        accepted, reasons = compare_context_reports(baseline, candidate)
        result = candidate.as_dict()
        result["status"] = "pass" if accepted else "fail"
        result["ok"] = int(accepted)
        result["baseline_router_version"] = baseline.router_version
        result["reasons"] = list(reasons)
        print(json.dumps(result, separators=(",", ":")))
        return 0 if accepted else 1
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "schema": 1,
                    "check": "context-eval",
                    "status": "error",
                    "ok": 0,
                    "reason": str(exc) or "EVALUATION_ERROR",
                },
                separators=(",", ":"),
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
