# Factory API

Local control-plane starter with liveness/readiness, operator login, session status, and a sanitized service dashboard endpoint. It uses PostgreSQL via SQLAlchemy when `DATABASE_URL` is configured; SQLite is available for isolated local development and migration checks.

Initialize the local operator secret in an interactive terminal with `python scripts/setup_local_env.py`. The API refuses startup when local authentication is enabled but the secret or scrypt password hash is missing. No provider credential is required.

Start the factory API and dashboard with `python scripts/local_boot.py --factory`; open `http://127.0.0.1:5173`. API docs are at `http://127.0.0.1:8001/docs`. The React app receives only service status and login results; it never receives provider tokens or the application secret.

Routes: `/health/live`, `/health/ready`, `/api/v1/auth/{login,logout,session}`, and authenticated `/api/v1/config/status`. State-changing authenticated requests require the session CSRF token in `X-CSRF-Token`; login attempts are limited to five per five minutes in this local process.
