# Ollama host spike

Status: service not enabled or verified in this environment; provider/model values remain opt-in.

- Local preflight probes only `GET /api/tags`; it does not run inference or download a model.
- Container connectivity uses a separate `OLLAMA_CONTAINER_BASE_URL`; the default points to `host.docker.internal`.
- Model availability is checked only for names explicitly configured; no quality or VRAM claim is made without a benchmark.
- Before enabling: run the live read-only preflight, record Ollama/model versions and GPU placement, then benchmark a small fixed fixture.

No model was downloaded and no inference request was made.
