"""Disposable PostgreSQL/API/UI targets; never inherit the operational .env."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess

import httpx

from scripts.quality_common import QUALITY, ROOT, QualityContext, source_manifest

PRIVATE = QUALITY / "private"
SERVICES = ["quality-postgres", "factory-api", "registry-api", "factory-web", "registry-web"]


def credentials() -> dict:
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = PRIVATE / "credentials.json"
    if not path.exists():
        password, salt = secrets.token_urlsafe(32), secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
        values = {
            "password": password,
            "QUALITY_DB_PASSWORD": secrets.token_hex(24),
            "QUALITY_APP_SECRET": secrets.token_hex(48),
            "QUALITY_OPERATOR_HASH": f"scrypt:16384:8:1:{salt.hex()}:{digest}",
        }
        path.write_text(json.dumps(values))
        path.chmod(0o600)
    return json.loads(path.read_text())


def compose(ctx: QualityContext) -> tuple[list[str], dict]:
    values = credentials()
    auth = PRIVATE / "auth"
    auth.mkdir(exist_ok=True, mode=0o700)
    dast = ctx.run_dir / "dast"
    dast.mkdir(exist_ok=True)
    # ZAP runs as uid 1000. This workspace and its test artifacts have the same owner.
    env_path = PRIVATE / "stack.env"
    env_path.write_text("".join(f"{k}={v}\n" for k, v in values.items() if k != "password"))
    env_path.chmod(0o600)
    env = ctx.environment()
    env.update({k: v for k, v in values.items() if k != "password"})
    env.update(
        QUALITY_RUN_ID=ctx.run_id,
        QUALITY_SOURCE_SHA256=ctx.manifest["source_sha256"],
        QUALITY_SOURCE_PATH=str(ctx.snapshot()),
        QUALITY_FACTORY_DIST=str(ctx.run_dir / "frontend/factory-dist"),
        QUALITY_REGISTRY_DIST=str(ctx.run_dir / "frontend/registry-dist"),
        QUALITY_DAST_DIR=str(dast),
        QUALITY_AUTH_DIR=str(auth),
    )
    return [
        "docker",
        "compose",
        "-p",
        "factory-quality-local",
        "--env-file",
        str(env_path),
        "-f",
        str(ROOT / "infra/compose/quality.yml"),
    ], env


def start(ctx: QualityContext) -> list[dict]:
    command, env = compose(ctx)
    steps = []
    for label, args, timeout in [
        ("reset-test-stack", ["down", "--remove-orphans"], 180),
        ("build-api-image", ["build", "factory-api"], 900),
        ("start-test-stack", ["up", "-d", "--wait", "--wait-timeout", "180", *SERVICES], 300),
    ]:
        step, _ = ctx.execute(label, command + args, env=env, timeout=timeout)
        steps.append(step)
        if step["exit_code"]:
            break
    if all(step["status"] == "pass" for step in steps):
        (QUALITY / "active-run.json").write_text(json.dumps({"run_id": ctx.run_id}))
    return steps


def active_context(check: str) -> QualityContext:
    run_id = os.getenv("FACTORY_QUALITY_RUN_ID")
    if not run_id:
        try:
            run_id = json.loads((QUALITY / "active-run.json").read_text())["run_id"]
        except (OSError, ValueError, KeyError) as exc:
            raise RuntimeError("RUN_QUALITY_UP_FIRST") from exc
    ctx = QualityContext(check, run_id=run_id)
    if source_manifest()["source_sha256"] != ctx.manifest["source_sha256"]:
        raise RuntimeError("SOURCE_CHANGED_RESTART_QUALITY_STACK")
    for service in ["factory-api", "registry-api", "factory-web", "registry-web"]:
        try:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    f"factory-quality-local-{service}-1",
                    "--format",
                    '{{ index .Config.Labels "factory.quality.run_id" }}:'
                    '{{ index .Config.Labels "factory.quality.source_sha256" }}',
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
        except subprocess.SubprocessError as exc:
            raise RuntimeError("RUNNING_QUALITY_TARGET_UNAVAILABLE") from exc
        if result.stdout.strip() != f"{ctx.run_id}:{ctx.manifest['source_sha256']}":
            raise RuntimeError("RUNNING_TARGET_PROVENANCE_MISMATCH")
    return ctx


def prepare_dast(ctx: QualityContext) -> dict:
    """Verify authentication/CSRF and record the API surfaces selected for active scan."""
    with httpx.Client(base_url="http://127.0.0.1:18801", timeout=15) as client:
        if client.get("/api/v1/demands").status_code != 401:
            raise RuntimeError("UNAUTHENTICATED_REQUEST_NOT_REJECTED")
        response = client.post("/api/v1/auth/login", json={"password": credentials()["password"]})
        response.raise_for_status()
        csrf = response.json()["csrf_token"]
        if client.get("/api/v1/demands").status_code != 200:
            raise RuntimeError("AUTHENTICATED_READ_FAILED")
        if client.post("/api/v1/demands", json={}).status_code != 403:
            raise RuntimeError("CSRF_PROTECTION_FAILED")
        token = client.cookies.get("factory_session")
        auth = PRIVATE / "auth/factory.json"
        auth.write_text(json.dumps({"cookie": f"factory_session={token}", "csrf": csrf}))
        auth.chmod(0o600)
        factory = client.get("/openapi.json").json()
    registry = httpx.get("http://127.0.0.1:18810/openapi.json", timeout=10).json()
    allowed = {
        "/api/v1/demands",
        "/api/v1/demands/{demand_id}",
        "/api/v1/demands/{demand_id}/tasks",
        "/api/v1/tasks",
        "/api/v1/tasks/{task_id}/transition",
        "/api/v1/approvals",
        "/api/v1/approvals/{approval_id}/decision",
    }
    excluded = sorted(path for path in factory["paths"] if path not in allowed)
    factory["paths"] = {k: v for k, v in factory["paths"].items() if k in allowed}
    for name, spec in [("factory", factory), ("registry", registry)]:
        spec["servers"] = [{"url": f"http://{name}-api:8000"}]
        (ctx.run_dir / "dast" / f"{name}-openapi.json").write_text(json.dumps(spec))
    result = {
        "authentication_required": True,
        "authenticated_read": True,
        "csrf_enforced": True,
        "factory_paths": sorted(factory["paths"]),
        "registry_paths": sorted(registry["paths"]),
        "factory_excluded_paths": excluded,
        "exclusion_reason": (
            "External integrations, LLM, publishing and long-lived SSE "
            "are separate acceptance work."
        ),
    }
    (ctx.run_dir / "dast/coverage.json").write_text(json.dumps(result, indent=2))
    return result


def redact_artifacts(ctx: QualityContext) -> None:
    values = list(credentials().values())
    auth = PRIVATE / "auth/factory.json"
    if auth.exists():
        values.extend(json.loads(auth.read_text()).values())
        values.append(json.loads(auth.read_text())["cookie"].removeprefix("factory_session="))
    for path in ctx.artifacts.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".html", ".log", ".md"}:
            raw = path.read_text(errors="replace")
            for value in values:
                raw = raw.replace(value, "[REDACTED]")
            path.write_text(raw)
