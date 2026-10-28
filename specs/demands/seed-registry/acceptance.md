# Seed demand: Customer Registry

## Problem
The local monorepo needs a small real application that can safely demonstrate future software changes.

## Acceptance
- An operator can create, search/list, update, and deactivate a user through the API and React UI.
- Username and email are required and unique without case sensitivity.
- Deactivation preserves the record and inactive users are hidden by default.
- API responses and errors are stable and field validation is explicit.
- The app runs locally without GitHub, an LLM, or provider credentials; SQLite is the default development store and PostgreSQL is supported by migrations.
- Test fixtures contain only synthetic identities.

## Out of scope
CPF, multi-tenant access, remote hosting, hard delete, and production personal data.

## Demo extension (FAC-088)
An optional synthetic phone number is supported in the API and UI. It is validated,
searchable, editable, and omitted when blank. CPF remains out of scope and is not
persisted by the registry.
