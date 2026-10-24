# OpenBot integration spike

Status: blocked on a local OpenBot installation and its pinned upstream version.

- No endpoint or message API has been assumed or called.
- The preflight supports configurable `OPENBOT_HEALTH_PATH` and optional `OPENBOT_AUTH_PROBE_PATH`; the latter is required to claim API key validation.
- Current local check is read-only and never sends a chat message. Without the auth probe, a live result is explicitly partial.
- Before enabling the adapter: record upstream commit/tag, confirm auth header and health/message contracts, disable unrestricted shell/network tools, and add a contract fixture for that exact version.

No external credential or network request was used in this spike.
