#!/usr/bin/env python3
"""Start the standalone local customer registry API and web UI."""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-only", action="store_true")
    parser.add_argument("--web-only", action="store_true")
    parser.add_argument("--factory", action="store_true", help="Start Factory API and dashboard")
    args = parser.parse_args()
    if args.api_only and args.web_only:
        print(
            json.dumps(
                {
                    "schema": 1,
                    "check": "local-boot",
                    "status": "error",
                    "ok": 0,
                    "reason": "CONFLICTING_OPTIONS",
                },
                separators=(",", ":"),
            )
        )
        return 2

    api_dir = ROOT / ("apps/factory-api" if args.factory else "apps/customer-registry/api")
    web_dir = ROOT / ("apps/factory-web" if args.factory else "apps/customer-registry/web")
    processes: list[subprocess.Popen] = []
    try:
        if args.factory and not (ROOT / ".env").is_file():
            print(
                json.dumps(
                    {
                        "schema": 1,
                        "check": "local-boot",
                        "status": "error",
                        "ok": 0,
                        "reason": "LOCAL_ENV_NOT_INITIALIZED",
                        "hint": (
                            "Run python scripts/setup_local_env.py in an interactive terminal first"
                        ),
                    },
                    separators=(",", ":"),
                )
            )
            return 2
        if not args.web_only:
            if args.factory:
                processes.append(
                    subprocess.Popen(
                        [
                            "uv",
                            "run",
                            "--frozen",
                            "--all-packages",
                            "--group",
                            "api",
                            "uvicorn",
                            "factory_api.main:app",
                            "--app-dir",
                            str(api_dir / "src"),
                            "--host",
                            "127.0.0.1",
                            "--port",
                            "8001",
                            "--env-file",
                            str(ROOT / ".env"),
                        ],
                        cwd=ROOT,
                    )
                )
            else:
                command = [
                    "uv",
                    "run",
                    "--frozen",
                    "--all-packages",
                    "--group",
                    "api",
                    "uvicorn",
                    "customer_registry.main:app",
                    "--app-dir",
                    str(api_dir / "src"),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8010",
                ]
                if (ROOT / ".env").is_file():
                    command.extend(["--env-file", str(ROOT / ".env")])
                processes.append(subprocess.Popen(command, cwd=ROOT))
        if not args.api_only:
            if not (web_dir / "node_modules").exists():
                print(
                    json.dumps(
                        {
                            "schema": 1,
                            "check": "local-boot",
                            "status": "error",
                            "ok": 0,
                            "reason": "WEB_DEPENDENCIES_MISSING",
                            "hint": f"Run pnpm install --dir {web_dir.relative_to(ROOT)}",
                        },
                        separators=(",", ":"),
                    )
                )
                return 2
            processes.append(subprocess.Popen(["pnpm", "dev"], cwd=web_dir))
        time.sleep(1)
        if any(process.poll() not in (None, 0) for process in processes):
            print(
                json.dumps(
                    {
                        "schema": 1,
                        "check": "local-boot",
                        "status": "error",
                        "ok": 0,
                        "reason": "SERVICE_FAILED_TO_START",
                    },
                    separators=(",", ":"),
                )
            )
            return 2
        print(
            json.dumps(
                {
                    "schema": 1,
                    "check": "local-boot",
                    "status": "pass",
                    "ok": 1,
                    "services": {
                        "api": "http://127.0.0.1:8001" if args.factory else "http://127.0.0.1:8010",
                        "web": "http://127.0.0.1:5173" if args.factory else "http://127.0.0.1:5174",
                    },
                    "detail": "Press Ctrl+C to stop",
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
        while True:
            for process in processes:
                code = process.poll()
                if code is not None:
                    return code if code else 0
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    except OSError:
        print(
            json.dumps(
                {
                    "schema": 1,
                    "check": "local-boot",
                    "status": "error",
                    "ok": 0,
                    "reason": "PROCESS_START_FAILED",
                },
                separators=(",", ":"),
            )
        )
        return 2
    finally:
        for process in processes:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
