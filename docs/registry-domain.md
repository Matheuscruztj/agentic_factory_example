# Customer Registry domain contract

Status: initial demo contract, version 1.

## User fields

| Field | Rule |
|---|---|
| `id` | Server-generated UUID; immutable. |
| `username` | Required, 3–32 characters, starts with an ASCII letter or digit; remaining characters may be letters, digits, dot, underscore, or hyphen. Uniqueness is case-insensitive. |
| `name` | Required, trimmed, 1–120 characters. |
| `email` | Required valid email, trimmed, at most 254 characters. Uniqueness is case-insensitive, including inactive records. |
| `status` | `active` or `inactive`; deletion is a soft deactivation and preserves history. |
| `created_at`, `updated_at` | UTC timestamps set by the service. |

## API behavior

- `POST /api/v1/users` creates an active user; duplicate normalized username/email returns HTTP 409 with a stable field code.
- `GET /api/v1/users` searches name, username, and email, lists active users by default, and can include inactive records.
- `PATCH /api/v1/users/{id}` changes any supplied username/name/email; empty updates return 400 and missing IDs return 404.
- `DELETE /api/v1/users/{id}` deactivates the record and returns 204.
- Invalid payloads use FastAPI/Pydantic 422 responses. CPF and phone are explicitly deferred features.

All demo data is synthetic. Do not place real personal or production customer data in local fixtures.
