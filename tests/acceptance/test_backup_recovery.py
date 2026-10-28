import hashlib
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.backup import backup, restore_sqlite_copy, verify


def test_backup_restore_dry_run_preserves_integrity_and_hash(tmp_path):
    source = tmp_path / "source.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO demo(value) VALUES ('synthetic-record')")
    manifest = backup(f"sqlite:////{source.as_posix().lstrip('/')}", tmp_path / "backups")
    archive = tmp_path / "backups" / manifest["artifact"]
    result = verify(archive)
    assert result["status"] == "verified"
    assert result["sha256"] == manifest["sha256"]
    assert "restore copy" in result["method"]
    restored = tmp_path / "restored.sqlite3"
    assert restore_sqlite_copy(archive, restored) == "ok"
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT value FROM demo").fetchone() == ("synthetic-record",)


def test_backup_verification_detects_tampering(tmp_path):
    source = tmp_path / "source.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE demo (value TEXT)")
    manifest = backup(f"sqlite:////{source.as_posix().lstrip('/')}", tmp_path / "backups")
    archive = tmp_path / "backups" / manifest["artifact"]
    archive.write_bytes(archive.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="BACKUP_HASH_MISMATCH"):
        verify(archive)


def test_postgres_docker_catalog_check_reads_archive_from_stdin(tmp_path):
    archive = tmp_path / "factory.dump"
    archive.write_bytes(b"synthetic-postgres-custom-archive")
    manifest = {
        "database_type": "postgresql",
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }
    archive.with_suffix(".dump.json").write_text(json.dumps(manifest), encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    def find_executable(name):
        return "/usr/bin/docker" if name == "docker" else None

    with (
        patch("scripts.backup.shutil.which", side_effect=find_executable),
        patch("scripts.backup.subprocess.run", side_effect=fake_run),
    ):
        result = verify(archive)

    assert result["status"] == "verified"
    assert calls[0][0][-2:] == ["--list", "-"]
    assert calls[0][1]["input"] == archive.read_bytes()
