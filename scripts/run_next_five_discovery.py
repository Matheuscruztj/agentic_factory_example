#!/usr/bin/env python3
"""Run one grounded Analyst discovery for the already approved tag demand."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory_workers.planning import plan_pending  # noqa: E402
from factory_workers.runner import LocalWorker, WorkerConfig  # noqa: E402
from sqlalchemy import select  # noqa: E402

from scripts.run_next_five import BASE, context, request, save  # noqa: E402

DEMAND = "5719882c-1e1d-49b9-a0d4-1f965762489e"
PATHS = [
    "apps/customer-registry/api/src/customer_registry/models/user.py",
    "apps/customer-registry/api/src/customer_registry/main.py",
    "apps/customer-registry/api/src/customer_registry/repositories/users.py",
    "apps/customer-registry/web/src/App.tsx",
    "apps/customer-registry/api/alembic/versions/0001_create_users.py",
]


async def run_git_grep(*args: str) -> subprocess.CompletedProcess[str]:
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return subprocess.CompletedProcess(
        args,
        process.returncode,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )


async def main():
    with context() as (cfg, sessions, client):
        inv = await run_git_grep(
            [
                "git",
                "grep",
                "-n",
                "-i",
                "-e",
                "tag_id",
                "-e",
                "class Tag",
                "-e",
                "/api/v1/tags",
                BASE,
                "--",
                "apps/customer-registry/api",
                "apps/customer-registry/web",
            ],
            cwd=ROOT,
        )
        if inv.returncode == 0:
            raise ValueError("BASELINE_TAG_IMPLEMENTATION_FOUND")
        detail = request(client, "GET", f"/demands/{DEMAND}")
        rev = max(detail["revisions"], key=lambda item: item["version"])
        assert rev["decision"] == "approved"
        request(
            client,
            "POST",
            f"/demands/{DEMAND}/discovery",
            {
                "base_git_sha": BASE,
                "context_paths": PATHS,
                "idempotency_key": "fac131-grounded-discovery-v1",
                "profile": "registry-fullstack",
                "max_attempts": 1,
            },
        )
        worker = LocalWorker(
            sessions,
            WorkerConfig(
                ROOT,
                ROOT.parent / ".next-five-worktrees",
                ROOT / ".runtime",
                "sha256:" + "0" * 64,
                ollama_url=cfg.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
                planning_model=cfg.get("OLLAMA_MODEL_CHAT") or cfg.get("OLLAMA_MODEL_CODING"),
            ),
        )
        result = await plan_pending(worker, demand_id=DEMAND, limit=1)
        if not result or result[0]["status"] != "grounded":
            raise ValueError("ANALYST_DISCOVERY_NOT_GROUNDED:" + json.dumps(result))
        artifact_id = result[0]["artifact_id"]
        with sessions() as session:
            artifacts = session.scalars(
                select(__import__("task_engine.models", fromlist=["Artifact"]).Artifact).where(
                    __import__("task_engine.models", fromlist=["Artifact"]).Artifact.subject_type
                    == "demand",
                    __import__("task_engine.models", fromlist=["Artifact"]).Artifact.subject_id
                    == DEMAND,
                )
            ).all()
            artifact = next(item for item in artifacts if item.id == artifact_id)
            raw = (ROOT / ".runtime" / artifact.relative_path).read_bytes()
            record = {
                "status": "grounded",
                "demand_id": DEMAND,
                "revision_id": rev["id"],
                "decision": "delegated_codex_assisted",
                "base_sha": BASE,
                "baseline_search": "no tag model/endpoint found",
                "event_id": result[0]["event_id"],
                "artifact_path": artifact.relative_path,
                "artifact_sha256": artifact.sha256,
                "artifact_hash_valid": __import__("hashlib").sha256(raw).hexdigest()
                == artifact.sha256,
                "fact_count": result[0]["fact_count"],
                "provenance": "local Ollama Analyst, reviewer not implied",
            }
        save("tags-discovery.json", record)
        print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    print(asyncio.run(main()))
