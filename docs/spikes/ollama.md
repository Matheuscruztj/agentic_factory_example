# Ollama local spike

Status: **accepted locally** (2026-10-24).

- Docker image: `ollama/ollama:0.40.11`, pinned in Compose by digest
  `sha256:dea72d1e22270fe095b68fdf756d2b489d615643c5a2eaebbc5f569181e322d8`.
- Models installed: `qwen3:4b` (`359d7dd4bcda`) and
  `qwen2.5-coder:7b` (`dae161e27b0e`). The optional Judge model remains unset
  to avoid occupying the RTX 4060 Ti's 8 GB VRAM.
- Docker exposes Ollama only at `127.0.0.1:11434`; the runtime is limited to one
  parallel request and one loaded model. `ollama ps` reported `qwen3:4b` at
  `100% GPU`, context 4096. The host reports an NVIDIA GeForce RTX 4060 Ti with
  8188 MiB total memory.
- Fixed smoke fixture: POST `/api/chat` with model `qwen3:4b`, prompt
  `Responda somente OK.`, `think: false`, and `num_predict: 512`. It returned a
  response ending in `OK` in 11.93 s (17 prompt tokens, 98 completion tokens,
  66.01 generated tokens/s). This is a connectivity/GPU smoke measurement, not
  a quality or production latency benchmark.
- `python scripts/validate_env.py --env .env --mode live --require ollama,openbot`
  passed and found both configured model tags. The OpenBot thread smoke also
  exercised Ollama through the internal Docker network.

`OLLAMA_MODEL_JUDGE` is deliberately blank. Run a representative quality and
latency benchmark before enabling more models or concurrent inference.
