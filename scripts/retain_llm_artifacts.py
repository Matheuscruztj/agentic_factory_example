#!/usr/bin/env python3
"""Prune expired raw trial JSONL while retaining summaries and audit receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRIALS = ROOT / ".runtime" / "evals" / "trials"
DEFAULT_AUDIT = ROOT / ".runtime" / "artifacts" / "retention"


def plan_retention(trials_dir: Path, *, max_age_days: int, now: datetime) -> dict:
    if not 1 <= max_age_days <= 3650:
        raise ValueError("RETENTION_DAYS_OUT_OF_RANGE")
    cutoff = now - timedelta(days=max_age_days)
    candidates = []
    if trials_dir.is_symlink():
        raise ValueError("TRIALS_DIRECTORY_SYMLINK")
    for path in sorted(trials_dir.glob("*.jsonl")) if trials_dir.exists() else []:
        if path.is_symlink() or not path.is_file():
            continue
        stat = path.stat()
        if datetime.fromtimestamp(stat.st_mtime, UTC) >= cutoff:
            continue
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        candidates.append(
            {
                "path": path.name,
                "size_bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": content_hash,
            }
        )
    return {
        "schema": 1,
        "created_at": now.isoformat(),
        "cutoff": cutoff.isoformat(),
        "max_age_days": max_age_days,
        "candidates": candidates,
        "protected": ["*.json", "*.md", "manifest.json", "*.receipt.json", "source datasets"],
    }


def apply_retention(plan: dict, trials_dir: Path) -> list[str]:
    deleted = []
    for item in plan["candidates"]:
        if not isinstance(item.get("path"), str) or Path(item["path"]).name != item["path"]:
            raise ValueError("TRIAL_PATH_INVALID")
        if not item["path"].endswith(".jsonl"):
            raise ValueError("TRIAL_PATH_INVALID")
        path = trials_dir / item["path"]
        if path.is_symlink() or not path.is_file():
            continue
        if (
            path.stat().st_mtime_ns != item.get("mtime_ns")
            or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]
        ):
            raise ValueError("TRIAL_CHANGED_AFTER_PLAN")
        path.unlink()
        deleted.append(item["path"])
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials-dir", type=Path, default=DEFAULT_TRIALS)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--max-age-days", type=int, default=30)
    parser.add_argument("--apply", action="store_true", help="delete expired raw JSONL trials")
    args = parser.parse_args()
    now = datetime.now(UTC)
    try:
        plan = plan_retention(args.trials_dir, max_age_days=args.max_age_days, now=now)
        deleted = apply_retention(plan, args.trials_dir) if args.apply else []
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "code": str(exc)}))
        return 2
    plan["mode"] = "apply" if args.apply else "dry_run"
    plan["deleted"] = deleted
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    output = args.audit_dir / f"retention-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    output.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "mode": plan["mode"],
                "candidates": len(plan["candidates"]),
                "deleted": deleted,
                "manifest": str(output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
