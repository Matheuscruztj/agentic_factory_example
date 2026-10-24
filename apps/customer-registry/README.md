# Customer Registry

A local-first user registry built as the first application in the Agentic Factory monorepo. It needs no GitHub, Ollama, OpenBot, or provider credentials.

## Start locally

Install the Python workspace and UI dependencies once:

```bash
uv sync --group api --group dev
pnpm install --dir apps/customer-registry/web
```

Start API and UI together:

```bash
python scripts/local_boot.py
```

Open `http://127.0.0.1:5174`; API docs are at `http://127.0.0.1:8010/docs`. Stop both with Ctrl+C. `--api-only` and `--web-only` start one service.

SQLite is stored in `.runtime/customer-registry.sqlite3`. PostgreSQL is supported through `REGISTRY_DATABASE_URL` and the Alembic migration under `api/alembic/`. Start PostgreSQL/Redis with the local Compose runbook after creating `.env`.

## Implemented behavior

- Create, search, edit, and soft-deactivate users.
- Required username, name, and email; username and email are case-insensitively unique.
- Active-only list by default; inactive rows remain queryable through the API.
- Loading, empty, error, and success feedback in the responsive UI.
- Synthetic idempotent demo seed: `uv run python scripts/seed_customer_registry.py`.
- Offline API/Vitest tests and a Playwright create/search/edit/deactivate flow.

Keep both development servers bound to loopback. Do not use real customer personal data in this demo database.
