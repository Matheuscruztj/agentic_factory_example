# Backup and recovery runbook

Backups are written under `.runtime/backups/`, use timestamped filenames, SHA-256
sidecars, and default retention of 10 archives. `.env` and credential material are
not included. SQLite uses the online backup API and restore-to-new-path refuses
to overwrite existing files. PostgreSQL uses `pg_dump` or the local Compose
container; `--restore-disposable` creates a random temporary database, runs
`pg_restore --exit-on-error`, and drops the database in `finally`.

```sh
uv run --env-file .env python scripts/backup.py backup
uv run --env-file .env python scripts/backup.py verify .runtime/backups/<archive>.dump --restore-disposable
```

The PostgreSQL restore verification requires the local Compose `postgres`
service. Never point the disposable restore at a production server; the helper
is intentionally pinned to `infra/compose/base.yml`. The SQLite acceptance test
restores an isolated synthetic database, checks integrity, and reads back its
record.
