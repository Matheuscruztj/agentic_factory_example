# Definition of Done

A task is complete when:

1. Its acceptance criteria map to observable behavior or a specific artifact.
2. Code changes stay within the task's declared paths and preserve protected-file policy.
3. Deterministic checks run locally and report their command, exit code, and concise result; infrastructure failure is recorded as exit 2, not a code failure.
4. Tests use isolated synthetic data and do not require live providers unless the task explicitly concerns that provider.
5. Secrets, password values, private keys, and personal data do not appear in source, browser payloads, logs, or test output.
6. Database changes have a forward migration and a repeatable upgrade path.
7. User-visible flows include accessible labels plus loading, empty, and error states where applicable.
8. Technical implementation acceptance may use the independent local-AI reviewer described in [AI acceptance policy](ai-acceptance-policy.md), with evidence and hashes bound to the exact source snapshot. Publishing, merge, deploy, secrets/policies, and other protected external effects still require their separate persisted HITL decision.
9. `state.md` lists only unfinished work; completed items are removed after their acceptance evidence is recorded.

## Evidence and end-to-end acceptance

The [2026-10-24 audit](auditoria-projeto-2026-10-24.md) found that component tests
had been counted as completed operational journeys. Apply these distinctions:

- A helper or fake contract can complete a component milestone; it cannot certify a live integration or an autonomous journey.
- Delivery evidence identifies requirement revision, approved plan/scope, task, run/attempt, model/prompt/context, tested Git commit/tree, suite/configuration and verified artifact hashes. Another run or commit cannot authorize completion.
- A workflow demonstration uses the real coordinator, local inference/tools, isolated execution, gates, review and applicable human decisions. A supplied patch or callback returning a run ID does not prove agent implementation.
- Independent AI acceptance requires complete evidence and a verifiable reviewer decision bound to that snapshot. The decision must identify a reviewer model distinct from the executor and cite verified artifacts; an unsigned text or an advisory Judge score is insufficient.
- Missing, skipped, unavailable, simulated, historical and live results remain distinguishable. Optional integrations outside the release scope remain explicitly deferred.

These are requirements for future work, not claims that the current runtime
already enforces them. The operator explicitly authorized AI acceptance in
place of human UAT for now; no completed activity or final report may claim a
human signature. See [FAC-100–139](../specs/08-PLANO-CONCLUSAO-E2E.md).

## Local secret handling

- Generate local credentials with `python scripts/setup_local_env.py`; keep `.env` mode `0600` and ignored by Git.
- To rotate credentials, stop the local API and Compose services, create a fresh `.env` from `.env.example`, run the setup utility, then restart services and revalidate login/database access.
- Revoke any external token at its provider before replacing it locally. Never record old or new values in artifacts or issue text.
- `gitleaks` is the required local repository scan for FAC-003; if unavailable, record the scan as not run rather than claiming a clean result.
