#!/usr/bin/env python3
"""Backup local DBs and verify recoverability without touching the source database."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit


def backup(database_url: str, directory: Path, *, retention: int = 10) -> dict:
    if not 1 <= retention <= 1000:
        raise ValueError("RETENTION_INVALID")
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    parsed = urlsplit(database_url)
    if parsed.scheme in {"sqlite", "sqlite+pysqlite"}:
        source_path = parsed.path
        if source_path.startswith("/") and not source_path.startswith("//"):
            source_path = source_path[1:]
        source = Path(unquote(source_path))
        if not source.is_file():
            raise ValueError("SQLITE_SOURCE_NOT_FOUND")
        artifact = directory / f"factory-{timestamp}.sqlite3"
        with sqlite3.connect(source) as src, sqlite3.connect(artifact) as dest:
            src.backup(dest)
            integrity = dest.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            artifact.unlink(missing_ok=True)
            raise ValueError("SQLITE_BACKUP_INTEGRITY_FAILED")
        database_type = "sqlite"
    elif parsed.scheme.startswith("postgresql"):
        executable = shutil.which("pg_dump")
        artifact = directory / f"factory-{timestamp}.dump"
        env = {**os.environ}
        if parsed.password:
            env["PGPASSWORD"] = unquote(parsed.password)
        database_name = unquote(parsed.path.lstrip("/"))
        username = unquote(parsed.username or "")
        if executable:
            command = [
                executable,
                "--no-owner",
                "--no-acl",
                "--format=custom",
                "--file",
                str(artifact),
                "--host",
                parsed.hostname or "127.0.0.1",
                "--port",
                str(parsed.port or 5432),
                "--username",
                username,
                database_name,
            ]
            result = subprocess.run(
                command, env=env, capture_output=True, timeout=300, check=False
            )
        elif shutil.which("docker"):
            result = subprocess.run(
                [
                    "docker", "compose", "--env-file", ".env", "-f", "infra/compose/base.yml",
                    "exec", "-T", "postgres", "pg_dump", "--no-owner", "--no-acl",
                    "--format=custom", "--username", username, database_name,
                ],
                capture_output=True,
                timeout=300,
                check=False,
            )
            if result.returncode == 0:
                artifact.write_bytes(result.stdout)
        else:
            raise ValueError("PG_DUMP_NOT_INSTALLED")
        env.pop("PGPASSWORD", None)
        if result.returncode:
            artifact.unlink(missing_ok=True)
            raise ValueError("POSTGRES_BACKUP_FAILED")
        database_type = "postgresql"
    else:
        raise ValueError("DATABASE_SCHEME_UNSUPPORTED")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = {
        "schema": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "database_type": database_type,
        "artifact": artifact.name,
        "size_bytes": artifact.stat().st_size,
        "sha256": digest,
        "source_url_recorded": False,
    }
    sidecar = artifact.with_suffix(artifact.suffix + ".json")
    sidecar.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    archives = sorted(directory.glob("factory-*.sqlite3")) + sorted(
        directory.glob("factory-*.dump")
    )
    for old in archives[:-retention]:
        old.unlink(missing_ok=True)
        old.with_suffix(old.suffix + ".json").unlink(missing_ok=True)
    return manifest


def verify(
    artifact: Path,
    manifest_path: Path | None = None,
    *,
    restore_postgres_disposable: bool = False,
    database_url: str | None = None,
) -> dict:
    sidecar = manifest_path or artifact.with_suffix(artifact.suffix + ".json")
    manifest = json.loads(sidecar.read_text(encoding="utf-8"))
    actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if actual != manifest.get("sha256"):
        raise ValueError("BACKUP_HASH_MISMATCH")
    if manifest.get("database_type") == "sqlite":
        with tempfile.TemporaryDirectory() as temp_dir:
            restored = Path(temp_dir) / "restore.sqlite3"
            integrity = restore_sqlite_copy(artifact, restored)
        if integrity != "ok":
            raise ValueError("RESTORE_DRY_RUN_INTEGRITY_FAILED")
        method = "read-only restore copy and SQLite integrity_check"
    elif manifest.get("database_type") == "postgresql":
        executable = shutil.which("pg_restore")
        if executable:
            result = subprocess.run(
                [executable, "--list", str(artifact)],
                capture_output=True,
                timeout=30,
                check=False,
            )
        elif shutil.which("docker"):
            result = subprocess.run(
                [
                    "docker", "compose", "--env-file", ".env", "-f", "infra/compose/base.yml",
                    "exec", "-T", "postgres", "pg_restore", "--list", "-",
                ],
                input=artifact.read_bytes(),
                capture_output=True,
                timeout=30,
                check=False,
            )
        else:
            raise ValueError("PG_RESTORE_NOT_INSTALLED")
        if result.returncode:
            raise ValueError("POSTGRES_ARCHIVE_INVALID")
        method = "pg_restore archive catalog"
        if restore_postgres_disposable:
            if not database_url:
                raise ValueError("DATABASE_URL_REQUIRED_FOR_RESTORE")
            restore_postgres_to_disposable_db(artifact, database_url)
            method = "archive catalog and disposable database restore"
    else:
        raise ValueError("BACKUP_TYPE_INVALID")
    return {"status": "verified", "sha256": actual, "method": method}


def restore_postgres_to_disposable_db(artifact: Path, database_url: str) -> None:
    """Restore into a uniquely named temporary local DB, then remove it."""
    parsed = urlsplit(database_url)
    if not parsed.scheme.startswith("postgresql") or not shutil.which("docker"):
        raise ValueError("LOCAL_COMPOSE_POSTGRES_REQUIRED")
    database_name = f"factory_restore_{secrets.token_hex(6)}"
    username = unquote(parsed.username or "")
    prefix = [
        "docker", "compose", "--env-file", ".env", "-f", "infra/compose/base.yml",
        "exec", "-T", "postgres",
    ]
    created = subprocess.run(
        [*prefix, "createdb", "--username", username, database_name],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if created.returncode:
        raise ValueError("DISPOSABLE_DATABASE_CREATE_FAILED")
    try:
        restored = subprocess.run(
            [
                *prefix, "pg_restore", "--exit-on-error", "--no-owner", "--no-acl",
                "--username", username, "--dbname", database_name,
            ],
            input=artifact.read_bytes(),
            capture_output=True,
            timeout=300,
            check=False,
        )
        if restored.returncode:
            raise ValueError("DISPOSABLE_DATABASE_RESTORE_FAILED")
    finally:
        dropped = subprocess.run(
            [*prefix, "dropdb", "--if-exists", "--username", username, database_name],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if dropped.returncode:
            raise ValueError("DISPOSABLE_DATABASE_CLEANUP_FAILED")


def restore_sqlite_copy(artifact: Path, destination: Path) -> str:
    """Restore to a new isolated path; refuse to overwrite any existing database."""
    if destination.exists():
        raise ValueError("RESTORE_DESTINATION_EXISTS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(artifact) as source, sqlite3.connect(destination) as target:
        source.backup(target)
        return target.execute("PRAGMA integrity_check").fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["backup", "verify"])
    parser.add_argument("artifact", nargs="?", type=Path)
    parser.add_argument("--directory", type=Path, default=Path(".runtime/backups"))
    parser.add_argument("--retention", type=int, default=10)
    parser.add_argument("--restore-disposable", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            url = os.getenv("DATABASE_URL", "")
            if not url:
                raise ValueError("DATABASE_URL_REQUIRED")
            result = backup(url, args.directory, retention=args.retention)
        else:
            if args.artifact is None:
                raise ValueError("BACKUP_ARTIFACT_REQUIRED")
            result = verify(
                args.artifact,
                restore_postgres_disposable=args.restore_disposable,
                database_url=os.getenv("DATABASE_URL"),
            )
        print(json.dumps({"schema": 1, "check": "backup", **result}, separators=(",", ":")))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": 1, "check": "backup", "status": "error", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
