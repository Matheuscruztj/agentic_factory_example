#!/usr/bin/env python3
"""Prepare trusted, frozen tooling separately from untrusted model execution."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    lock_hash = hashlib.sha256(
        (ROOT / "apps/customer-registry/web/pnpm-lock.yaml").read_bytes()
    ).hexdigest()
    context = ROOT / ".runtime" / ("runner-image-" + lock_hash[:12])
    context.mkdir(parents=True, exist_ok=True)
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("NODE_REQUIRED")
    shutil.copy2(node, context / "node")
    shutil.copy2(ROOT / "infra/quality/Runner.Dockerfile", context / "Dockerfile")
    shutil.copy2(ROOT / "infra/quality/frontend-gate", context / "frontend-gate")
    if not (context / "node_modules").exists():
        shutil.copytree(
            ROOT / "apps/customer-registry/web/node_modules",
            context / "node_modules",
            symlinks=True,
        )
    for package in ("playwright", "playwright-core"):
        installed = sorted(
            (context / "node_modules/.pnpm").glob(f"{package}@*/node_modules/{package}")
        )
        if not installed:
            raise RuntimeError("PLAYWRIGHT_DEPENDENCY_REQUIRED")
        target = context / "node_modules" / package
        if not target.exists():
            target.symlink_to(
                installed[-1].relative_to(context / "node_modules"), target_is_directory=True
            )
    if not (context / "browsers").exists():
        shutil.copytree(Path.home() / ".cache/ms-playwright", context / "browsers", symlinks=True)
    result = subprocess.run(
        ["docker", "build", "-t", "agentic-factory-runner:local", str(context)], check=False
    )
    if result.returncode:
        return 2
    image = subprocess.check_output(
        ["docker", "image", "inspect", "agentic-factory-runner:local", "--format", "{{.Id}}"],
        text=True,
    ).strip()
    manifest = {
        "schema": 1,
        "image": image,
        "node_sha256": hashlib.sha256((context / "node").read_bytes()).hexdigest(),
        "lock_sha256": lock_hash,
    }
    (ROOT / ".runtime/runner-image.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
