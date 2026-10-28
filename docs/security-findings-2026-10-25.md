# Triagem de achados de segurança

## Snapshot atual

O scan final pós-override é `quality-security` run
`20261026T020723Z-4355d0af/security.json`, source SHA-256
`a4eddb55f4efd0f7348a73cb90e862773d629926a7cdca9944c6439aa57573e7`:
passou 7/7, com quatro achados Bandit médios, zero advisories PNPM e zero
high/critical. A repetição isolada equivalente é
`20261026T020649Z-9ab83faf`.

## Bandit

O snapshot atual encontrou quatro achados médios:

| Regra | Local | Triagem e tratamento |
|---|---|---|
| B108 | `packages/agent-runtime/src/agent_runtime/sandbox.py:59` | `/tmp` do executor está em tmpfs dedicado com `noexec,nosuid`; rootfs read-only e rede isolada. Controle concreto; prova operacional segue FAC-104/116. |
| B108 | `scripts/quality_security.py:150` | tmpfs Semgrep com `noexec,nosuid,nodev`, limite 512 MiB, container sem rede, read-only e sem capabilities. |
| B108 | `scripts/quality_security.py:191` | Mesmo isolamento no container dos canários. |
| B104 | `scripts/quality_target.py:49` | Uvicorn escuta no namespace do container para os scanners; publicação de portas da stack é loopback no host e rede isolada. |

Os seis B310 do snapshot anterior foram eliminados substituindo `urlopen` por
`httpx` com timeout limitado, redirects e proxies de ambiente desativados em
GitHub, Telegram, doctor e preflight. B108/B104 permanecem como controles
compensatórios rastreados, sem `nosec` ou relaxamento de regras. Ainda exigem
revisão do risco residual e prova operacional antes de fechar FAC-153.

## PNPM audit

A inspeção via `pnpm audit --json` revelou cinco advisories moderados no
snapshot inicial:

| ID | Pacote/correção | Aplicação e resultado |
|---|---|---|
| 1241232 | `postcss-selector-parser <7.1.6` | Factory: override no `pnpm-workspace.yaml` para 7.1.6; a árvore agora contém uma versão e o audit retornou zero. |
| 1242767 | `@vitest/mocker <4.1.12` | Vitest atualizado 4.1.11 → 4.1.12 nas duas aplicações. |
| 1242769 | `@vitest/mocker <4.1.12` | Mesmo upgrade; audit Registry retornou zero. |

Após o override, `pnpm audit` Factory e Registry não retornaram advisories.
Build, teste (3/3) e lint da Factory passaram com a nova resolução; Registry
teste (3/3), build e lint também passaram. `pnpm why` confirmou somente
`postcss-selector-parser@7.1.6` na árvore Factory.

## Evidências e estado

- Scan final pós-override: `.runtime/quality/runs/20261026T020723Z-4355d0af/security/` (7/7 checks; Bandit 4 médios; PNPM Factory/Registry 0).
- Scan anterior: `.runtime/quality/runs/20261026T020333Z-154f7712/security/` (7/7 checks, antes da remediação do parser).
- Regressão direcionada: 53 testes Python passaram; `ruff`, `py_compile` e `git diff --check` passaram.
- Quality-fast final no mesmo snapshot: `.runtime/quality/runs/20261026T020649Z-9bd57c9d/fast.json`, 11/11 passou.
- `quality-full`: `.runtime/quality/runs/20261026T020723Z-4355d0af/aggregate.json` passou 5/5 gates obrigatórios; DAST 4/4 superfícies sem high/critical. Sonar adicional falhou no Quality Gate e deixou `quality-full` em erro; Locust passou 23 requisições sem falha.

O gate `quality-security` aplica limiar high/critical e pode passar mesmo com
avisos médios. FAC-153 recebeu aceite técnico por IA (receipt HMAC) para o
escopo da atividade: triagem dos quatro médios B108/B104 com controles
compensatórios e dono via `owner_role`, remediação dos advisories, filtros
inválidos, browsers e DAST. O Sonar falho é relatado separadamente e mantém o
conjunto global fora de estado verde; FAC-139 e scorecard global permanecem
pendentes.
