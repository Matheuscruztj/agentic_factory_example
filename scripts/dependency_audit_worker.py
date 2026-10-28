#!/usr/bin/env python3
"""Run the local, read-only dependency audit worker against a fixture scenario."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from factory_workers.dependency_audit import DependencyAuditWorker  # noqa: E402

FIXTURES = ROOT / "evals/fixtures/dependency-update"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=FIXTURES / "scenario.json")
    parser.add_argument("--before", type=Path, default=FIXTURES / "lock-before.json")
    parser.add_argument("--candidate", type=Path, default=FIXTURES / "lock-candidate.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime/artifacts/ai-acceptance/FAC-097/dependency-audit.json",
    )
    args = parser.parse_args()
    report = DependencyAuditWorker(args.output.parent).run_once(
        evidence_path=args.evidence,
        before_manifest=args.before,
        candidate_manifest=args.candidate,
        output_path=args.output,
    )
    print(json.dumps({"status": report["status"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
