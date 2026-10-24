# LangGraph persistence spike

Status: deferred until the PostgreSQL service is initialized and the LangGraph/checkpointer version is selected.

- The architecture requires a durable PostgreSQL checkpointer; an in-memory saver does not meet restart recovery.
- No LangGraph package or API is currently assumed in runtime code.
- Validate pause/resume across process restart, stable `thread_id=run_id`, and idempotent replay before adding the dependency.
- Current `uv.lock` locks the implemented workspace only; it does not claim a LangGraph integration.

This spike made no network calls and created no remote resources.
