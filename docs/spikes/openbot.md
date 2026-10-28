# OpenBot integration spike

Status: **accepted locally** (2026-10-24).

- Upstream source pinned to `regnull/openbot` commit
  `11753662edea33cc90fd1f85fd9ec5793a572fc6`. Run
  `python scripts/prepare_openbot.py` before building the Compose service.
- The local patch set disables `run_shell` in the global tool registry and maps
  the Ollama reasoning option through the upstream `ChatOllama` adapter.
- Compose starts OpenBot without demo bots. The only configured bot is `qa`;
  `tool_names` and `approval_tools` are empty. `/api/v1/tools` does not expose
  `run_shell`, so an API request cannot add it to a bot.
- OpenBot itself has only the internal Docker network and can reach Ollama there.
  A minimal Nginx gateway publishes the API at `127.0.0.1:8002`; it has no
  application tools. The API key is in the mode-600 local `.env`.
- Live acceptance: `/api/v1/health` returned 200, authenticated
  `/api/v1/providers` returned 200, and the same provider route without a key
  returned 401. A new thread addressed `qa`, used `qwen3:4b`, and received a
  bot message in 9.30 s. The bot remained tool-free. A separate attempt to
  create a bot with `run_shell` was rejected with HTTP 422 before persistence.
- Preflight command: `python scripts/validate_env.py --env .env --mode live
  --require ollama,openbot` (pass; six services passed, no failures/errors).

The startup warning that `models.dev` cannot resolve is expected: OpenBot has no
direct egress. It does not affect local provider/model discovery or chat.
FAC-052 remains separate: the Factory React chat still needs authenticated API
and browser end-to-end integration.
