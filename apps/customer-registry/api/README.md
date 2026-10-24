# Customer Registry API

Standalone local CRUD API. It uses SQLite at `.runtime/customer-registry.sqlite3` by default and PostgreSQL when `REGISTRY_DATABASE_URL` is set. SQLite creates its schema on startup for a zero-setup demo. PostgreSQL schema is managed by Alembic.

## Run

From the repository root:

```bash
uv sync --group api --group dev
python scripts/local_boot.py --api-only
```

Or start the API and UI together with `python scripts/local_boot.py`. API docs are at `http://127.0.0.1:8010/docs`.

For PostgreSQL, set `REGISTRY_DATABASE_URL` in `.env`, start `infra/compose/base.yml`, then run:

```bash
uv run alembic -c apps/customer-registry/api/alembic.ini upgrade head
python scripts/local_boot.py --api-only
```

## User contract

- Create: `POST /api/v1/users` with required `username`, `name`, and `email`.
- Username: 3–32 ASCII letters/digits plus `.`, `_`, `-`; starts with a letter or digit; unique case-insensitively.
- Email: validated and unique case-insensitively, including inactive accounts.
- Search/list active users: `GET /api/v1/users?search=...`.
- Include deactivated users: `GET /api/v1/users?include_inactive=true`.
- Update: `PATCH /api/v1/users/{id}`.
- Deactivate: `DELETE /api/v1/users/{id}` (soft delete; history remains).
- Duplicate username/email returns `409`; malformed fields return `422`.

Seed only synthetic examples with `uv run python scripts/seed_customer_registry.py`. Never store production or sensitive personal data in this development database.
