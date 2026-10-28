#!/usr/bin/env python3
"""Consume approved execution plans using the versioned local worker."""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import time
from pathlib import Path

from factory_workers.runner import LocalWorker, WorkerConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scripts.validate_env import read_env


async def run(args, cfg: dict) -> int:
    engine = create_engine(cfg["DATABASE_URL"], pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    root = Path(__file__).resolve().parents[1]
    worker = LocalWorker(
        factory,
        WorkerConfig(
            repository=root,
            worktree_root=args.worktree_root.resolve(),
            runtime_root=root / ".runtime",
            sandbox_image=args.sandbox_image,
            ollama_url=cfg.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            coding_model=cfg.get("OLLAMA_MODEL_CODING", "qwen2.5-coder:7b"),
            review_model=(
                cfg.get("EVAL_JUDGE_MODEL") or cfg.get("OLLAMA_MODEL_JUDGE") or "qwen3:4b"
            ),
            worker_id=args.worker_id,
            planning_model=cfg.get("OLLAMA_MODEL_CHAT") or None,
        ),
    )
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, stop)
    try:
        while not stopped:
            from factory_workers.planning import plan_pending

            planning = await plan_pending(worker, demand_id=args.demand_id)
            dispatched = worker.dispatch(demand_id=args.demand_id)
            result = await worker.execute_one(demand_id=args.demand_id)
            print(
                json.dumps({"planning": planning, "dispatched": dispatched, **result}), flush=True
            )
            if args.once:
                failed_planning = any(
                    item["status"] in {"blocked", "retry_wait"} for item in planning
                )
                return 0 if result["status"] in {"done", "idle"} and not failed_planning else 1
            if result["status"] == "idle":
                await asyncio.sleep(args.interval)
    finally:
        engine.dispose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--demand-id")
    parser.add_argument("--worker-id", default="local-worker")
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--worktree-root", type=Path, required=True)
    parser.add_argument("--sandbox-image", required=True, help="Immutable Docker digest/image ID")
    args = parser.parse_args()
    if not 0.1 <= args.interval <= 60:
        parser.error("interval must be between 0.1 and 60 seconds")
    try:
        return asyncio.run(run(args, read_env(args.env)))
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"status": "error", "error_type": type(exc).__name__, "timestamp": time.time()}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
