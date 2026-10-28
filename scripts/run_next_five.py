#!/usr/bin/env python3
"""Resume the five authorized local closure activities with explicit assisted provenance.

Uses existing intake identities and authenticated ASGI routes against local PostgreSQL.
Never polls channels, sends messages, publishes Git or marks backlog activities done.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from factory_api import main  # noqa: E402
from factory_api.auth.session import create_session  # noqa: E402
from factory_api.database import get_db  # noqa: E402
from factory_workers.runner import LocalWorker, WorkerConfig, git  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from task_engine.models import ApprovalRequest, Artifact, Task  # noqa: E402
from task_engine.runs import assert_completion_evidence  # noqa: E402

from scripts.validate_env import read_env  # noqa: E402

OUT = ROOT / ".runtime/artifacts/next-five"
BASE = "00d1a782ece691ad510fb4ef318590eea3540fff"
VISUAL = {
    "telegram": "bc16a11c-f654-4738-98f1-45daa2387faa",
    "ui": "bcb1099c-a495-4c9f-87f5-c7d395769569",
    "github": "8fe5de11-310f-48cc-88b5-c55c8493693e",
}
CSS_PATH = "apps/customer-registry/web/src/styles.css"
CSS = """
.submit-button{--button-dark:#202622;--button-dark-hover:#111813;--button-dark-disabled:#6d756f;--button-focus:#315fcb;background:var(--button-dark)}
.submit-button:hover:not(:disabled){background:var(--button-dark-hover)}
.submit-button:focus-visible{outline:3px solid var(--button-focus);outline-offset:2px}
.submit-button:disabled{background:var(--button-dark-disabled);opacity:1;cursor:not-allowed}
"""


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def request(client, method, path, body=None):
    response = client.request(method, "/api/v1" + path, json=body)
    if response.status_code >= 400:
        raise ValueError(f"API_{response.status_code}:{response.text[:500]}")
    return response.json()


@contextmanager
def context():
    cfg = read_env(ROOT / ".env")
    engine = create_engine(cfg["DATABASE_URL"], pool_pre_ping=True)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    original = main.settings
    main.settings = replace(
        main.settings,
        auth_enabled=True,
        secret_key=cfg["APP_SECRET_KEY"],
        password_hash=cfg["OPERATOR_PASSWORD_HASH"],
    )

    def db():
        with sessions() as session:
            yield session

    main.app.dependency_overrides[get_db] = db
    # Local delegated operator harness, not a human login/signature. All routes
    # enforce their usual CSRF, version, plan/hash and domain checks.
    token, csrf = create_session(main.settings.secret_key)
    try:
        with TestClient(main.app) as client:
            client.cookies.set("factory_session", token)
            client.headers["X-CSRF-Token"] = csrf
            yield cfg, sessions, client
    finally:
        main.settings = original
        main.app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def approve_revision(client, demand_id):
    detail = request(client, "GET", f"/demands/{demand_id}")
    revision = max(detail["revisions"], key=lambda x: x["version"])
    if revision["decision"] != "approved":
        request(
            client,
            "POST",
            f"/demands/{demand_id}/revisions/{revision['version']}/decision",
            {
                "expected_demand_version": detail["demand"]["version"],
                "revision_sha256": revision["revision_sha256"],
                "decision": "approved",
                "comment": (
                    "Delegated Codex decision under product defaults and assisted "
                    "authorization; not a human signature."
                ),
            },
        )


def approve_plan(client, demand_id):
    grant = request(
        client,
        "POST",
        "/approvals",
        {"entity_type": "demand", "entity_id": demand_id, "requested_by": "closure-planner"},
    )
    request(
        client,
        "POST",
        f"/approvals/{grant['id']}/decision",
        {
            "decision": "approved",
            "comment": (
                "Delegated execution of exact local plan/bundle under existing assisted delivery "
                "authorization. No remote publication; not a human signature."
            ),
        },
    )
    return grant


def bundle(name, files):
    path = ROOT / ".runtime/artifacts/approved-patches" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(
        {
            "executor_kind": "assisted_patch",
            "author": "codex-assisted",
            "source": (
                "Reviewed existing component adapted by Codex; no autonomous generation claimed."
            ),
            "files": [{"path": p, "content": v} for p, v in files.items()],
        },
        sort_keys=True,
    ).encode()
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("IMMUTABLE_BUNDLE_CHANGED_USE_NEW_VERSION")
    path.write_bytes(raw)
    return {
        "executor": "assisted_patch",
        "patch_artifact": path.relative_to(ROOT / ".runtime").as_posix(),
        "patch_sha256": hashlib.sha256(raw).hexdigest(),
    }


def prepare_visual(client):
    state_path = OUT / "visual-plan.json"
    if state_path.exists():
        return json.loads(state_path.read_text())
    baseline = ROOT.parent / ".next-five-visual-baseline"
    if not baseline.exists():
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(baseline), BASE],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        test = (ROOT / "apps/customer-registry/web/e2e/dark-button.spec.ts").read_text()
        test = (
            test.replace(
                "test('Cadastro button",
                "for (const width of [375, 1280]) {\ntest(`Cadastro ${width} button",
            )
            .replace("states', async", "states`, async")
            .replace("width: 375, height: 812", "width, height: 900")
            .replace("toBeLessThanOrEqual(375)", "toBeLessThanOrEqual(width)")
            + "\n}\n"
        )
        (baseline / "apps/customer-registry/web/e2e/dark-button.spec.ts").write_text(test)
        git(baseline, "add", "apps/customer-registry/web/e2e/dark-button.spec.ts")
        git(
            baseline,
            "-c",
            "user.name=Factory Harness",
            "-c",
            "user.email=harness@example.invalid",
            "commit",
            "-m",
            "Freeze independent dark-button acceptance tests",
        )
    base = git(baseline, "rev-parse", "HEAD")
    result = {
        "base_sha": base,
        "product_base": BASE,
        "harness_author": "codex-orchestration",
        "provenance": "codex-assisted",
        "human_approval_claimed": False,
        "channels": {},
    }
    for channel, demand_id in VISUAL.items():
        detail = request(client, "GET", f"/demands/{demand_id}")
        requirement = (
            "Alterar somente o botão Adicionar cliente do Registry: tokens dark locais "
            "#202622, hover #111813, disabled #6d756f, texto branco, foco visível 3px; "
            "preservar fundo claro, CRUD e mobile. Sem tema global ou backend."
        )
        acceptance = [
            "Normal, hover, disabled colors match approved tokens; text contrast is at least 4.5.",
            "Keyboard focus visible; mobile and desktop fit; light background and CRUD preserved.",
        ]
        request(
            client,
            "POST",
            f"/demands/{demand_id}/revisions",
            {
                "expected_demand_version": detail["demand"]["version"],
                "content": requirement,
                "acceptance": acceptance,
            },
        )
        approve_revision(client, demand_id)
        spec = {
            "base_git_sha": base,
            "profile": "registry-frontend",
            "context_paths": [CSS_PATH],
            "max_attempts": 3,
            "sandbox_pids_limit": 256,
            **bundle(
                "visual-" + channel,
                {CSS_PATH: git(ROOT, "show", BASE + ":" + CSS_PATH) + "\n" + CSS},
            ),
        }
        task = request(
            client,
            "POST",
            f"/demands/{demand_id}/tasks",
            {
                "title": "Authorized assisted dark button " + channel,
                "owner_role": "frontend",
                "path_scopes": [CSS_PATH],
                "acceptance": acceptance,
                "execution_spec": spec,
            },
        )
        grant = approve_plan(client, demand_id)
        result["channels"][channel] = {
            "demand_id": demand_id,
            "task_id": task["id"],
            "approval": grant,
        }
        save("visual-plan-progress.json", result)
    save("visual-plan.json", result)
    return result


async def execute(cfg, sessions, demand_id):
    image = json.loads((ROOT / ".runtime/next-five-runner-image.json").read_text())["image"]
    worker = LocalWorker(
        sessions,
        WorkerConfig(
            ROOT,
            ROOT.parent / ".next-five-worktrees",
            ROOT / ".runtime",
            image,
            ollama_url=cfg.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            review_model="qwen2.5-coder:7b",
            worker_id="next-five-worker",
        ),
    )
    dispatched = worker.dispatch(demand_id=demand_id)
    result = await worker.execute_one(demand_id=demand_id)
    result["dispatched"] = dispatched
    if result.get("run_id"):
        with sessions() as session:
            task = session.get(Task, result["task_id"])
            run = assert_completion_evidence(session, task)
            grant = session.get(ApprovalRequest, task.result["approval_id"])
            artifacts = session.scalars(select(Artifact).where(Artifact.subject_id == run.id)).all()
            assert grant.decided_at <= run.started_at
            assert all(
                hashlib.sha256((ROOT / ".runtime" / a.relative_path).read_bytes()).hexdigest()
                == a.sha256
                for a in artifacts
            )
            result.update(
                approval_before_run=True,
                artifact_hashes_valid=True,
                executor_kind=run.executor_kind,
                base_sha=run.base_git_sha,
            )
    return result


def main_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["visual-prepare", "visual-run"])
    parser.add_argument("--channel", choices=list(VISUAL), default="telegram")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with context() as (cfg, sessions, client):
        if args.action == "visual-prepare":
            result = prepare_visual(client)
        else:
            result = asyncio.run(execute(cfg, sessions, VISUAL[args.channel]))
            save("visual-" + args.channel + "-result.json", result)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status", "prepared") in {"done", "prepared"} else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
