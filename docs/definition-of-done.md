# Definition of Done

A task is complete when:

1. Its acceptance criteria map to observable behavior or a specific artifact.
2. Code changes stay within the task's declared paths and preserve protected-file policy.
3. Deterministic checks run locally and report their command, exit code, and concise result; infrastructure failure is recorded as exit 2, not a code failure.
4. Tests use isolated synthetic data and do not require live providers unless the task explicitly concerns that provider.
5. Secrets, password values, private keys, and personal data do not appear in source, browser payloads, logs, or test output.
6. Database changes have a forward migration and a repeatable upgrade path.
7. User-visible flows include accessible labels plus loading, empty, and error states where applicable.
8. Actions that change scope, publish, merge, deploy, or edit secrets/policies require a recorded human decision.
9. `state.md` lists only unfinished work; completed items are removed after their acceptance evidence is recorded.
