#!/usr/bin/env python3
"""Reproduce the CPF journey through authenticated APIs, planner and real local worker.

Uses a disposable PostgreSQL database and a synthetic operator for the controlled
pilot. It is not a human signature or authority to publish any remote change.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import psycopg
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory_api import main  # noqa: E402
from factory_api.auth.session import create_session  # noqa: E402
from factory_api.database import get_db  # noqa: E402
from factory_workers.planning import plan_pending  # noqa: E402
from factory_workers.runner import LocalWorker, WorkerConfig, git  # noqa: E402
from task_engine.models import AgentRun, Task  # noqa: E402

from scripts.validate_env import read_env  # noqa: E402


async def run_subprocess(*args: str, cwd: Path = ROOT, check: bool = False):
    """Run a local command without blocking the async journey event loop."""
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    result = subprocess.CompletedProcess(
        args,
        process.returncode,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )
    if check:
        result.check_returncode()
    return result


def request(client, path, body):
    response = client.post(path, json=body)
    if response.status_code >= 400:
        raise RuntimeError(f"API_{response.status_code}:" + response.text[:250])
    return response.json()


async def journey() -> dict:
    cfg = read_env(ROOT / ".env")
    output = ROOT / ".runtime/artifacts/closure-20261027/cpf-journey"
    output.mkdir(parents=True, exist_ok=True)
    run_key = uuid4().hex[:12]
    # This branch contains only the deliberately defective fixture, never a supplied fix.
    baseline = ROOT.parent / f".closure-cpf-baseline-{run_key}"
    await run_subprocess(
        [
            "git",
            "worktree",
            "add",
            "--detach",
            str(baseline),
            "00d1a782ece691ad510fb4ef318590eea3540fff",
        ],
        check=True,
        capture_output=True,
    )
    fixture = baseline / "evals/fixtures/bug-cpf/baseline"
    fixture.mkdir(parents=True)
    for name in ("cpf.py", "test_cpf.py"):
        shutil.copy2(ROOT / "evals/fixtures/bug-cpf/baseline" / name, fixture / name)
    assisted = os.getenv("CLOSURE_EXECUTOR_KIND") == "assisted_patch"
    if assisted:
        (fixture / "test_independent_contract.py").write_text(
            "import pytest\nfrom cpf import is_valid_cpf\n"
            "@pytest.mark.parametrize('value', [None, '', '123', 'a'*11, '0'*11, "
            "'52998224725suffix', '529.982.247-25'])\n"
            "def test_rejects_malformed_or_repeated_values(value):\n"
            "    assert is_valid_cpf(value) is False\n"
        )
    git(baseline, "add", "--", "evals/fixtures/bug-cpf/baseline")
    git(
        baseline,
        "-c",
        "user.name=Factory Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "Seed deliberately defective synthetic CPF fixture",
    )
    base_sha = git(baseline, "rev-parse", "HEAD")
    image = json.loads((ROOT / ".runtime/runner-image.json").read_text())["image"]
    from agent_runtime.sandbox import SandboxProfile, run_sandboxed

    red = run_sandboxed(
        baseline,
        [
            "python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "evals/fixtures/bug-cpf/baseline",
        ],
        profile=SandboxProfile(image),
    )
    if red.returncode != 1:
        raise RuntimeError("CPF_BASELINE_MUST_FAIL")
    (output / f"{run_key}-before.log").write_bytes(red.stdout + red.stderr)
    db_name = "closure_" + run_key
    url = make_url(cfg["DATABASE_URL"])
    admin_url = url.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(admin_url, autocommit=True) as conn:
        from psycopg import sql

        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
    database_created = True
    database_url = url.set(database=db_name).render_as_string(hide_password=False)
    # Migrations, not create_all: prove the installed schema the actual worker consumes.
    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(Config(str(ROOT / "apps/factory-api/alembic.ini")), "head")
    finally:
        if old_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_url
    engine = create_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    original_settings = main.settings
    main.settings = replace(
        main.settings,
        auth_enabled=True,
        secret_key=secrets.token_hex(32),
        password_hash="synthetic-pilot-not-real-password",
    )

    def db():
        with factory() as session:
            yield session

    main.app.dependency_overrides[get_db] = db
    token, csrf = create_session(main.settings.secret_key)
    worker = LocalWorker(
        factory,
        WorkerConfig(
            ROOT,
            ROOT.parent / ".closure-worktrees",
            ROOT / ".runtime",
            image,
            coding_model=os.getenv("CLOSURE_CODING_MODEL")
            or cfg.get("OLLAMA_MODEL_CODING")
            or "qwen2.5-coder:7b",
            review_model=os.getenv("CLOSURE_REVIEW_MODEL")
            or cfg.get("EVAL_JUDGE_MODEL")
            or "qwen3:4b",
            worker_id="closure-cpf-worker",
            planning_model=os.getenv("CLOSURE_PLANNING_MODEL"),
        ),
    )
    try:
        with TestClient(main.app) as client:
            client.cookies.set("factory_session", token)
            client.headers["X-CSRF-Token"] = csrf
            demand = request(
                client,
                "/api/v1/demands",
                {
                    "source": "manual",
                    "external_id": "closure-cpf-" + run_key,
                    "title": "Reject invalid synthetic CPF check digit",
                    "demand_type": "bug",
                    "requirement": "Fix only evals/fixtures/bug-cpf/baseline/cpf.py: "
                    "is_valid_cpf must verify Brazilian CPF check digits, reject repeated digits "
                    "and malformed input. Preserve the existing synthetic tests unchanged. "
                    "No CPF field or persistence in the Registry. Use one backend task. "
                    "Checksum contract: first digit uses 9 digits with weights 10 down to 2; "
                    "second digit uses 10 digits with weights 11 down to 2. Each check digit "
                    "is zero when sum modulo 11 is less than 2, otherwise 11 minus remainder. "
                    "Compute separate weighted sums for the 9-digit and 10-digit prefixes. "
                    "The second sum must include position 9 (the first check digit).",
                    "acceptance": [
                        "52998224725 is valid and 52998224726 is invalid.",
                        "Repeated digits and malformed values are rejected.",
                        "Only cpf.py may change; existing tests remain unchanged.",
                    ],
                },
            )
            spec = {
                "base_git_sha": base_sha,
                "profile": "python-fixture",
                "fixture_path": "evals/fixtures/bug-cpf/baseline",
                "max_output_tokens": 8192,
                "context_paths": [
                    "evals/fixtures/bug-cpf/baseline/cpf.py",
                    "evals/fixtures/bug-cpf/baseline/test_cpf.py",
                ],
            }
            if assisted:
                discovery = [
                    {
                        "stage": "discovery",
                        "status": "grounded_assisted",
                        "provenance": "codex-assisted",
                        "evidence": [f"{base_sha}:evals/fixtures/bug-cpf/baseline/cpf.py:4"],
                        "finding": "Baseline checks length/digits only; checksum is absent.",
                    }
                ]
            else:
                request(
                    client,
                    f"/api/v1/demands/{demand['id']}/discovery",
                    {**spec, "idempotency_key": "discovery-" + run_key},
                )
                discovery = await plan_pending(worker)
            detail = client.get(f"/api/v1/demands/{demand['id']}").json()
            revision = detail["revisions"][0]
            request(
                client,
                f"/api/v1/demands/{demand['id']}/revisions/{revision['version']}/decision",
                {
                    "expected_demand_version": detail["demand"]["version"],
                    "revision_sha256": revision["revision_sha256"],
                    "decision": "approved",
                    "comment": "Synthetic operator decision for the authorized local pilot.",
                },
            )
            if assisted:
                approved = ROOT / ".runtime/artifacts/approved-patches"
                approved.mkdir(parents=True, exist_ok=True)
                bundle_path = approved / ("cpf-" + run_key + ".json")
                bundle = {
                    "executor_kind": "assisted_patch",
                    "author": "codex-assisted",
                    "source": "Helper reviewed and tightened by Codex; assisted authorship.",
                    "files": [
                        {
                            "path": spec["context_paths"][0],
                            "content": (
                                ROOT
                                / "apps/customer-registry/api/src/customer_registry/services/cpf.py"
                            ).read_text(),
                        }
                    ],
                }
                bundle_path.write_text(json.dumps(bundle, sort_keys=True))
                spec.update(
                    executor="assisted_patch",
                    patch_artifact=bundle_path.relative_to(ROOT / ".runtime").as_posix(),
                    patch_sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
                )
                task_view = request(
                    client,
                    f"/api/v1/demands/{demand['id']}/tasks",
                    {
                        "title": "Fix synthetic CPF checksum and malformed input",
                        "owner_role": "backend",
                        "path_scopes": [spec["context_paths"][0]],
                        "acceptance": [
                            "Valid checksum accepted; invalid and malformed inputs rejected.",
                            "Existing and independent tests remain unchanged.",
                        ],
                        "execution_spec": spec,
                    },
                )
                planned = [
                    {
                        "stage": "plan",
                        "status": "proposed",
                        "provenance": "codex-assisted",
                        "task_ids": [task_view["id"]],
                    }
                ]
            else:
                request(
                    client,
                    f"/api/v1/demands/{demand['id']}/plan",
                    {**spec, "idempotency_key": "plan-" + run_key},
                )
                planned = await plan_pending(worker)
            with factory() as session:
                tasks = session.scalars(select(Task).where(Task.demand_id == demand["id"])).all()
                if len(tasks) != 1 or tasks[0].path_scopes != [spec["context_paths"][0]]:
                    raise RuntimeError("CPF_PLAN_REQUIRES_SCOPE_REVIEW")
            grant = request(
                client,
                "/api/v1/approvals",
                {"entity_type": "demand", "entity_id": demand["id"], "requested_by": "planner"},
            )
            request(
                client,
                f"/api/v1/approvals/{grant['id']}/decision",
                {
                    "decision": "approved",
                    "comment": "Synthetic operator authorizes this exact local fixture plan.",
                },
            )
            dispatched = worker.dispatch()
            result = await worker.execute_one(demand_id=demand["id"])
            while result["status"] == "retry_wait":
                result = await worker.execute_one(demand_id=demand["id"])
            with factory() as session:
                runs = session.scalars(select(AgentRun)).all()
                records = [
                    {
                        "run_id": x.id,
                        "base_sha": x.base_git_sha,
                        "result_sha": x.result_git_sha,
                        "status": x.status,
                        "executor_kind": x.executor_kind,
                        "model_digest": x.model_digest,
                    }
                    for x in runs
                ]
            run_ids = [x["run_id"] for x in records]
            receipt = {
                "schema": 1,
                "scenario": "cpf",
                "demand_id": demand["id"],
                "database": db_name,
                "baseline_sha": base_sha,
                "before_exit_code": red.returncode,
                "discovery": discovery,
                "planned": planned,
                "dispatched": dispatched,
                "result": result,
                "runs": records,
                "operator_provenance": "controlled_synthetic_operator",
                "human_approval_claimed": False,
                "external_writes": False,
                "implementation_provenance": "codex-assisted" if assisted else "local_ollama",
            }
            (output / f"{run_key}-receipt.json").write_text(json.dumps(receipt, indent=2))
            return receipt
    finally:
        if "original_settings" in locals():
            main.settings = original_settings
        main.app.dependency_overrides.pop(get_db, None)
        if "engine" in locals():
            engine.dispose()
        if "run_ids" in locals():
            for run_id in run_ids:
                worktree = ROOT.parent / ".closure-worktrees" / run_id
                if worktree.exists():
                    await run_subprocess(
                        ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(worktree)],
                        check=False,
                        capture_output=True,
                    )
        if "database_created" in locals() and database_created:
            with psycopg.connect(admin_url, autocommit=True) as conn:
                from psycopg import sql

                conn.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                        sql.Identifier(db_name)
                    )
                )
        if baseline.exists():
            await run_subprocess(
                ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(baseline)],
                check=False,
                capture_output=True,
            )


def main_cli() -> int:
    try:
        result = asyncio.run(journey())
        print(json.dumps(result))
        return 0 if result["result"]["status"] == "done" else 1
    except Exception as exc:
        print(
            json.dumps(
                {"status": "blocked", "error_type": type(exc).__name__, "reason": str(exc)[:250]}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main_cli())
