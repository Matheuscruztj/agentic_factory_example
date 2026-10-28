# Local observability runbook

Observability is best-effort. If the collector, Phoenix, GPU tools, or a metric
recorder is unavailable, task execution and quality gates continue without those
measurements. Request logs omit bodies and headers; prompt/response content and
credential values are not telemetry fields.

## Structured logs and correlation

The Factory API accepts a validated `X-Correlation-ID` and optional `X-Task-ID`,
returns the correlation ID in its response, and emits a compact JSON request
record containing only method, route, status, correlation ID, and task ID.
Downstream services can pass `CorrelationContext.fields()` to the shared JSON
logger. `redact_fields()` masks sensitive keys recursively and scrubs common
bearer/JWT/key-value formats from strings.

## Ollama measurements

Use `observability.instrumented_ollama_generate` around local `/api/generate`
calls. It records model, queue wait when supplied, model load, generation time,
total time, and prompt/completion token counts. Missing metrics are `null`; no
prompt or response is retained. A telemetry recorder failure does not turn a
successful generation into a task failure.

## OpenTelemetry and Phoenix (opt-in)

Validate without starting services:

```sh
docker compose -f infra/compose/observability.yml --profile observability --profile phoenix config -q
```

Start collector or Phoenix only when needed:

```sh
docker compose -f infra/compose/observability.yml --profile observability up -d
docker compose -f infra/compose/observability.yml --profile phoenix up -d
```

Both bind to loopback, run on an internal network, and have resource limits.
Phoenix data is stored in the named `phoenix-data` volume. Turn either service
off independently with `docker compose ... stop`; application operation does
not depend on them. GPU readings are optional and report unavailable if NVIDIA
utilities are missing.
