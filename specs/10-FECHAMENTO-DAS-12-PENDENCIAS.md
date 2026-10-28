# Fechamento local simplificado das atividades restantes

Atualizado em **2026-10-28**, por autorização explícita do operador. Este documento
substitui o roteiro extenso anterior para FAC-131–134 e FAC-136–139. O objetivo é
encerrar os itens com evidência funcional proporcional, sem repetir provas já válidas
nem exigir personas, child tasks demonstrativas, receipts globais ou matrizes exaustivas.

## Resultado

O backlog contém 174 atividades `done`, sem `in_progress` ou `todo`. O fechamento local
usou a bateria focada de 25 testes e `quality-fast` com 11/11 verificações aprovadas:
`.runtime/quality/runs/20261028T044837Z-062eecb2/fast/`.

O scorecard global continua `pending_ai_acceptance`. Esse status é intencional: não foi
emitido receipt/HMAC global nem declarado aceite de produção, piloto externo ou
`quality-full`. O relatório gerado lista as 174 atividades como concluídas e não alega
aprovação global: `docs/acceptance-report.md`.

## Critérios mínimos adotados

| ID | Critério local de encerramento | Evidência |
|---|---|---|
| FAC-131 | Defaults de produto registrados; contrato EARS coerente; limites e casos negativos explícitos; plano hash-bound. | `specs/demands/feature-tags-e2e/contract-review.md`; `.runtime/artifacts/next-five/fac131-grounded-discovery.json` |
| FAC-132 | Migration preserva dados; API cobre duplicatas, limites, vínculo/filtro, atomicidade e rollback em PostgreSQL descartável. | `.runtime/artifacts/next-five/postgres-tag-contract-complete.json` (29 checks); `postgres-migration-proof.json` |
| FAC-133 | Conflito real reproduzido/resolvido; build, teste API e E2E PostgreSQL cobrem fluxo principal e regressão. | `.runtime/artifacts/next-five/fac133-conflict-resolution.json`; `fac133-final-postgres-e2e.json` |
| FAC-134 | Testes verificam proposta QA escopada, aprovação/rejeição e replay idempotente sem duplicar efeito. | `.runtime/artifacts/next-five/following-five-review.json` (parte da bateria focada de 25 testes) |
| FAC-136 | Scanner de fixture sintética elimina a finding; hashes conferem; lockfiles reais não mudam. | `.runtime/artifacts/fac136-runs/fac136-scan-881b07725c/`; `fac136-dependency-audit-current.json` |
| FAC-137 | Restart em processo separado recupera aprovação/estado persistido em dois casos representativos. | `.runtime/artifacts/fac-137/postgres-process-restart.json` |
| FAC-138 | Backups de Factory, Registry, OpenBot e artefato restauram e permitem readback; redaction/retenção têm testes focados. | `.runtime/artifacts/fac-138/restore-summary.json`; bateria focada |
| FAC-139 | Relatório reconcilia estados/evidências; bateria focada e `quality-fast` passam; limites permanecem explícitos. | `docs/acceptance-report.md`; run quality-fast acima |

## Proveniência e limites

- Entregas assistidas por Codex estão identificadas como tais; não são chamadas de geração autônoma Ollama.
- EARS/plano delegados não são descritos como assinatura humana. A decisão de defaults de produto é do operador.
- O follow-up QA permanece como teste de componente. A proposta externa `80f657fe-4245-438e-85a1-0970c0cb2499` continua `pending_review` e não produziu efeito.
- FAC-136 só alterou fixture sintética. O experimento não autorizou alteração de lockfile do produto nem publicação.
- FAC-137 cobre dois casos críticos de restart, não a matriz antiga R01–R12.
- FAC-138 comprova restore/readback e proteções focadas, não uma única jornada com telemetria completa no dashboard.
- FAC-133 teve Playwright 3/3 no SHA `ea5deaa`; o conflito foi resolvido em branch isolada e os ajustes de UI foram aplicados ao working tree `main`. O checkout tinha aproximadamente 300 alterações locais, portanto não foi criado merge commit para não misturar ou descartar esse trabalho.
- Caches de build/teste foram identificados e removidos somente onde eram regeneráveis; artefatos de evidência e bancos persistentes foram preservados. O banco PostgreSQL descartável da prova E2E foi removido após readback.

O aceite global ainda exigiria uma decisão separada. Nenhuma atividade local precisa ser reaberta para emitir esse status: se o operador decidir buscar aceite global/produção depois, os gates opcionais devem ser avaliados em uma fase própria, sem alterar o resultado local acima.
