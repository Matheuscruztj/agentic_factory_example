# Quality gates and agent evaluations

Updated 2026-10-25: the deterministic quality stack is implemented; see the
[quality runbook](quality-gates-runbook.md) for commands, coverage, policy and
remaining work. The [original audit](auditoria-projeto-2026-10-24.md) preserves
its earlier snapshot. Working gates do not certify the autonomous agent workflow.

## Local deterministic gates

```bash
make quality
make quality-fast
make quality-full
make quality-up
make quality-down
```

`make quality` aliases `make quality-fast`: Ruff, ESLint, TypeScript/build,
OpenAPI contract, eval dataset validation, deterministic context eval and local
Judge calibration. This is the feedback loop for active feature work. Unit test
refactoring and broader test cleanup are reserved for the quality improvement
phase.

`make quality-full` runs Python/frontend tests, PostgreSQL-backed browser
acceptance, SAST/SCA/secrets, ZAP DAST, local Docker Sonar, then Locust. Full
runs retain source manifests, reports and artifact hashes; see the runbook for
blocking thresholds and remaining limitations. Defer this cycle until the
current feature wave is complete.
FAC-105/117 still cover authoritative agent runs, impact selection, broader
mypy coverage and the agent's bounded rework loop. FAC-153 covers scanner
hardening follow-ups. No model score can override a deterministic failure.

## Eval datasets, judge, and prompt experiments

The `dev`, `regression`, and `holdout` datasets contain synthetic cases and are
SHA-256 frozen in `evals/dataset-manifest.json`. Holdout cases are excluded from
production prompt input. Ten labels currently have provisional bootstrap
provenance and await independent human review. The validator reports 14 cases
across five datasets. Do not use these labels to claim human calibration.

`eval_engine.schema` records model/prompt/context/skill provenance, deterministic
checks, latency, token counts, accepted tasks, and cost per persona. Objective
checks remain separate from subjective judge scores. The optional Ollama judge
must use a model distinct from the executor, cite supplied evidence, validate
against a strict JSON schema, and escalate uncertainty. It cannot change
approvals, task state, quality gates, or prompt activation.

Prompt experiments consume paired evaluator observations with the same cases,
seed, and token budget. They report prompt hashes, diffs, quality/cost deltas,
and critical regressions. An eligible candidate only receives a human-review
recommendation; it is never activated automatically.

## Research extension: rubrics and evals v2 (draft only)

The [research review](pesquisa-fabricas-agenticas-evals-rubricas-2026-10-24.md)
and [specification](../specs/09-EVALS-RUBRICAS-E-HARNESS.md) add FAC-140–152.
The [design directory](../evals/design/README.md) contains eight proposed role
rubrics, 24 anchored criteria and 32 candidate scenarios. These files are not
registered in the active dataset manifest and contain no approved human labels
or measured benchmark results.

The extension covers grader validity, bias/abstention of the Judge, repeated
reliability, resource confounders, context handoffs, architecture ablations,
tool usability, dataset lifecycle and proportional interaction. CSV import,
filtered CSV export and compatible pagination are optional capability fixtures,
not newly committed MVP product requirements.

New rubric design uses an experimental 0–3 scale with per-criterion evidence and
explicit unassessable/N/A handling. The active Judge still uses its existing
1–5 schema. A versioned migration and independent calibration are required
before activation; no prompt, model or rubric release was changed by this research.

The current calibration treats `pass` as the positive class. Its recall is not
defect recall. New defect-detection reports must declare their positive class,
false critical acceptance, false rejection, abstention coverage and denominators.
Self-reported confidence is not empirical calibration.
