# Local base services

Start PostgreSQL and Redis after generating a local `.env` with `python scripts/setup_local_env.py`:

```bash
docker compose --env-file .env -f infra/compose/base.yml up -d
docker compose --env-file .env -f infra/compose/base.yml ps
```

Both published ports bind only to `127.0.0.1`. PostgreSQL keeps persistent data in a named volume and creates `customer_registry` on first initialization. Redis is optional for app readiness and is an accelerator, never the source of truth.

Do not use `docker compose down -v` unless intentionally deleting local database data.
