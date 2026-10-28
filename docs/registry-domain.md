# Customer Registry domain contract

Status: current implementation inventory, updated 2026-10-27. Phone and shared client tags are implemented in the assisted feature branch;
FAC-107 verifies omission/null/empty/invalid behavior in the API and phone removal in
the browser flow. Original version 1 deferred phone and no longer describes the
complete code. The tag defaults used here are the delegated contract recorded in the feature demand. This inventory is not a claim of human sign-off.

## User fields

| Field | Rule |
|---|---|
| `id` | Server-generated UUID; immutable. |
| `username` | Required, 3–32 characters, starts with an ASCII letter or digit; remaining characters may be letters, digits, dot, underscore, or hyphen. Uniqueness is case-insensitive. |
| `name` | Required, trimmed, 1–120 characters. |
| `email` | Required valid email, trimmed, at most 254 characters. Uniqueness is case-insensitive, including inactive records. |
| `phone` | Optional; null on creation or 7–32 characters matching an optional leading plus followed by digits, spaces, parentheses and hyphens. Whitespace is normalized. Format validation does not prove a reachable number. |
| `tags` | Zero to ten shared catalog entries per user. Names are trimmed to 1–32 characters; duplicate names compare using Unicode casefold without accent folding. API responses include tag IDs and names. |
| `status` | `active` or `inactive`; deletion is a soft deactivation and preserves history. |
| `created_at`, `updated_at` | UTC timestamps set by the service. |

## API behavior

- `POST /api/v1/users` creates an active user; duplicate normalized username/email returns HTTP 409 with a stable field code.
- `GET /api/v1/users` searches name, username, email and phone, lists active users by default, and can include inactive records.
- `PATCH /api/v1/users/{id}` changes supplied username/name/email/phone values; omitted values stay unchanged, `phone: null` clears the optional number, empty updates return 400, and an empty phone string returns 422. Null for required username/name/email fields is ignored. Missing IDs return 404.
- `DELETE /api/v1/users/{id}` deactivates the record and returns 204.
- `GET /api/v1/tags` lists the shared catalog; `POST /api/v1/tags` creates a trimmed name and returns 409 `TAG_ALREADY_EXISTS` for a normalized duplicate.
- User create accepts `tag_ids` (default `[]`). Update omission or `null` preserves current associations; `[]` clears them. Unknown or repeated IDs and more than ten IDs return 422 without a partial update.
- `GET /api/v1/users?tag_id=<uuid>` filters by an existing tag ID; normal search and active/inactive rules still apply.
- Invalid payloads use FastAPI/Pydantic 422 responses. CPF remains a synthetic validation helper/fixture and is not persisted in User. Phone exists in API/UI and migration `0002_add_optional_user_phone`.

## Verification boundary

Tag API tests use isolated SQLite, while the integrated browser gate exercised React → API → SQLite. Separate Codex-assisted API and browser runs against disposable PostgreSQL passed CRUD, associations/filtering, atomic invalid updates, normalized duplicate handling under concurrency (201/409), a mobile tag flow with reload, SQL readback, and schema constraints. Migration evidence on empty and populated databases is also available. These proofs validate the current API/schema behavior, but do not prove authorship by the versioned worker, conflict resolution, performance, extended security scans, or human product acceptance. Evidence: `.runtime/artifacts/next-five/postgres-tag-api-proof.json`, `.runtime/artifacts/next-five/tags-browser-postgres-e2e.json`, and `.runtime/artifacts/next-five/postgres-migration-proof.json`. See the [tag acceptance matrix](../specs/demands/feature-tags-e2e/acceptance.md) for remaining gaps.

All demo data is synthetic. Do not place real personal or production customer data in local fixtures.
