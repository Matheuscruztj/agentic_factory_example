# LangGraph persistence spike

Status: Python packages pinned; PostgreSQL checkpointer and pause/reopen/resume
acceptance passed against the local PostgreSQL service.

- The architecture requires a durable PostgreSQL checkpointer; an in-memory saver does not meet restart recovery.
- `langgraph==1.0.10` and `langgraph-checkpoint-postgres==3.2.0` are selected.
- The adapter requires `DATABASE_URL`, calls `PostgresSaver.setup()`, and rejects
  in-memory savers. It never falls back to RAM persistence.
- Acceptance test closes and reopens `PostgresSaver`, resumes a human interrupt
  with stable `thread_id=run_id`, and cleans up its unique fixture thread.
- Retry/DLQ idempotency for external side effects remains pending in FAC-058.

This spike made no network calls and created no remote resources.
