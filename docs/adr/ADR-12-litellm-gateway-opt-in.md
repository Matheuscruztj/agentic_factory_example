# ADR-12: LiteLLM gateway opt-in

- Status: accepted by local AI technical review on 2026-10-25
- Owners: Platform / AI
- Scope: optional local model routing and evaluation

## Context

The factory uses local Ollama models on a single 8 GB GPU. A gateway could add
aliases, request accounting, and a stable endpoint, but it also adds a service,
configuration, and another failure point. The gateway must not become a
prerequisite for local work or silently route requests to a cloud provider.

## Decision

Keep the direct Ollama adapter as the default and supported path. LiteLLM is an
explicit Compose profile, disabled unless selected. Gateway calls use only the
configured local Ollama provider. There is no automatic direct-to-proxy or
proxy-to-cloud fallback: an unavailable selected route returns an operational
error and leaves the task retryable.

The initial container candidate is
`ghcr.io/berriai/litellm:v1.106.4@sha256:c169fb3adc514fcf210377c203f3de406d54f10bfdacf13948a4a839db9af7de`.
The version and digest were checked against the upstream
[LiteLLM container package](https://github.com/berriai/litellm/pkgs/container/litellm)
on 2026-10-25. Compose implementation must verify that the selected platform
supports this manifest digest before enabling the profile.

Current local model inventory (Ollama tags API, 2026-10-25):

| Role | Model | Ollama digest |
| --- | --- | --- |
| Chat / Judge candidate | `qwen3:4b` | `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7` |
| Coding | `qwen2.5-coder:7b` | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |

Aliases are configuration names, not model identity. Run records continue to
store the resolved provider model and digest. Direct mode and proxy mode must
remain distinguishable in provenance and benchmark reports.

## Security and operational constraints

- Bind the gateway to the internal Compose network; publish no host port.
- Require an internal gateway credential and keep it out of logs and reports.
- Do not record raw prompts or completions by default.
- Serialize inference requests to respect the single-GPU memory limit.
- Keep prompt approval, quality gates, task acceptance, and publication
  authorization independent from gateway routing.
- Pin image version and digest. Upgrades require configuration validation,
  offline contract tests, a local smoke test, and a reversible rollback.

## Alternatives considered

1. **Ollama direct only:** remains the default; simplest and lowest risk, but
   does not provide a shared proxy endpoint for comparative experiments.
2. **LiteLLM always on:** rejected because it makes local work depend on an
   optional service and adds a failure point to every inference.
3. **Automatic fallback between direct and proxy:** rejected because it hides
   the selected route and makes latency, model identity, and failure evidence
   ambiguous.
4. **Cloud provider fallback:** out of scope; it would add external data flow,
   credentials, and cost without explicit per-task authorization.

## Non-goals

This ADR does not select a winning model, claim a quality or performance gain,
enable a public endpoint, authorize cloud inference, or automatically promote
prompts or models. Benchmark conclusions require paired runs with sufficient
samples and the same fixture, task budget, and acceptance gates.

## Consequences

The first implementation may be used only when the profile is explicitly
enabled. Direct mode must pass its own tests while the gateway is stopped. The
selected image digest and Ollama model digests must be captured in each run or
benchmark record. Unsupported LiteLLM/Ollama capabilities must be reported as
unavailable rather than inferred from the proxy response.
