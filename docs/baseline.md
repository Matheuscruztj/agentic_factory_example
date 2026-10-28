# Repository baseline

Date: 2026-10-24

## Observed state

- Git root: `/home/matheus/zona_de_teste/agentic/a-fabric`.
- Branch: `main`; observed HEAD: `00d1a782ece691ad510fb4ef318590eea3540fff`.
- The checkout has substantial pre-existing modifications and untracked implementation artifacts; the baseline was recorded without changing or discarding them. The raw status snapshot is `.runtime/baseline-git-status.txt` (ignored local evidence).
- The repository now contains the application source, Python and frontend manifests, Compose configuration, migrations, local tests, operational scripts, and the implementation backlog.
- The plan lives in `specs/`; runtime source is distributed across `apps/`, `packages/`, `workers/`, and `scripts/`. Existing modules were inspected before implementation, consistent with the architecture's migration rule.

## Reuse and migration

- Preserve the supplied specifications and preflight implementation. The canonical runtime and test paths are present; do not duplicate modules solely to match reference paths.
- Continue implementation from verified backlog state and `state.md`; bootstrap tasks are not evidence of runtime acceptance by themselves.

## Baseline limitation

This is a point-in-time inventory of a dirty checkout. The observed HEAD is the baseline commit; current working-tree changes are pre-existing and are not attributed to this audit. Reproduction in a clean checkout remains separate validation.
