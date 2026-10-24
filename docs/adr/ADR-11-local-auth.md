# ADR-11: Local operator sessions

- Status: accepted for the local starter implementation.
- Decision: authenticate the single operator with an scrypt password hash from `.env`; issue a short-lived HMAC-signed, HttpOnly, SameSite=Strict cookie; require a matching CSRF token for state-changing authenticated routes.
- Secret ownership: the API process reads `APP_SECRET_KEY` and `OPERATOR_PASSWORD_HASH`; the browser receives neither.
- Limits: cookie `Secure` is false only because the development server binds to loopback HTTP. Do not expose these servers beyond localhost. Authentication must use TLS and cookie hardening before any remote deployment.
- Rate limit: five failed logins per five-minute window per local process, reset on successful login/restart.
