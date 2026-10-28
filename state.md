# Estado atual do fechamento

Atualizado em **2026-10-28** após simplificação autorizada e fechamento local das oito atividades restantes.
Fonte oficial de status: [backlog](specs/implementation-backlog.json). Critérios e
roteiro operacional: [fechamento das pendências](specs/10-FECHAMENTO-DAS-12-PENDENCIAS.md).
Histórico anterior: [state antes do fechamento FAC-135](docs/auditoria/state-antes-fechamento-fac135-2026-10-27.md).

## Resumo

O backlog contém **174 atividades: 166 `done`, 8 `in_progress`, 0 `todo`**. As oito
abertas são FAC-131–134 e FAC-136–139. O aceite global segue `pending_ai_acceptance`;
nenhum receipt global, merge ou deploy foi produzido nesta fase.

FAC-131 agora tem decisão de produto do operador, revisão EARS v2 reconciliada e plano
hash-bound; FAC-132 tem runs/worktrees DB/BE, provas PostgreSQL e reviews. FAC-133 teve
conflito real reproduzido e resolvido em branch isolada; E2E PostgreSQL passou 3/3 no
SHA integrado final. FAC-133 segue aberta pelo fluxo terminal da child task Factory; revisão local Qwen3
aprovou as mudanças de integração no SHA final, com escopo/limites registrados.
FAC-134 ainda depende da revisão da proposta exata do follow-up. FAC-139 depende de
FAC-131–138, cobertura Sonar mínima de 80% e `quality-full` verde.

## Atividades concluídas a preservar

### FAC-121 — retorno visual pelo Telegram

Demanda `bc16a11c-f654-4738-98f1-45daa2387faa`, raiz `464393985:11`, chegou a
`completed`. Foram enviados apenas os dois eventos milestone autorizados para essa
demanda; recibos Telegram 14 e 15 apontam para a mesma raiz. Replay do update
original manteve uma demanda; replay da outbox enviou zero mensagens. Três eventos
históricos permanecem pendentes e não foram enviados. Evidências:
`.runtime/artifacts/next-five/fac121-visual-delivery.json` e
`fac121-inbound-replay.json`. Receipt IA local `7cddcdfbec476399e7c4`, Qwen3:4b,
approve, confiança 0,95, HMAC válido. Proveniência Codex-assisted, sem assinatura
humana.

### FAC-130 — auditoria visual de três origens

Requisitos e planos válidos precederam os novos runs; receipts antigos com decisão
`proposed` não foram reutilizados. Telegram run `d61cdd57-0bb0-4076-a1c6-95f3fa953fd8`,
SHA `cc2f8b6ae100d15077c09dc8a49433ed20fa7d43`; UI run
`02c20356-f737-4c8c-bbe0-6879ce8107a9`, SHA
`b174262cecb4e735a36f92ef85691bdc2dea118c`; GitHub Issue #3 run
`d5293601-b994-48ef-85df-f678598436c5`, SHA
`61e53fef29ca1c79d89a3798802f6ae88af23243`. Build, Playwright em 375/1280 px e
review Qwen3 passaram; contraste mínimo medido foi >=4,5. Não houve comentário remoto
GitHub, merge ou deploy. Receipt local `d39224ded49af13026dd`, approve, confiança
0,95. Proveniência Codex-assisted.

### FAC-135 — correção reproduzível de bug

Entrega Codex-assisted `afd40e20cc5b`, run
`d6f4fc7f-9a66-48d0-b7fd-40572fe90c26`, base
`08101bc3e12d6a90639ffa065334d5e7034ca382`, resultado
`8ae305e521955640377f1fe97edc1efbdf36a5da`. Teste vermelho preservado, nove testes
verdes, API autenticada, plano aprovado, worker versionado e PostgreSQL. Receipt
independente `2e810762d7e27f4973e7`, approve, confiança 1,0; hashes e HMAC foram
verificados. Reutilizar `.runtime/artifacts/uat/activities/FAC-135/` no pacote final.

### FAC-142 — avaliação sintética do Judge

Concluída com dataset/oráculo determinísticos e revisão independente. Preservar o
receipt do backlog e as limitações declaradas: `human_agreement=null` e
`promotion_eligible=false`. Não repetir a avaliação nem solicitar labels humanos;
verificar seus hashes quando montar o pacote FAC-139.

## Atividades fechadas nesta fase

| Atividade | Resultado mínimo concluído | Evidência principal |
|---|---|---|
| FAC-131 | Defaults do operador, EARS 10/20 coerente, fronteiras 9/10/11, DAG e histórico de revisão. Autoria assistida declarada. | `specs/demands/feature-tags-e2e/contract-review.md`; `.runtime/artifacts/next-five/fac131-grounded-discovery.json` |
| FAC-132 | Migrações, CRUD, normalização, limites, atomicidade, associações e rollback validados em PostgreSQL descartável; 29 checks. | `.runtime/artifacts/next-five/postgres-tag-contract-complete.json`; `tags-final-plan-and-runs.json` |
| FAC-133 | Conflito add/add reproduzido e resolvido; PostgreSQL Playwright 3/3, API 2/2, build e revisão Qwen no SHA `ea5deaa`. Correção de erro duplicado preservada no working tree `main`. | `.runtime/artifacts/next-five/fac133-conflict-resolution.json`; `fac133-final-postgres-e2e.json` |
| FAC-134 | Contrato de follow-up QA e replay cobertos na bateria focada; proposta pendente não foi aprovada nem despachada. | `.runtime/artifacts/next-five/following-five-review.json` |
| FAC-136 | Remediação somente em fixture sintética: scanner 21→18→0, hashes conferidos; lockfiles reais intactos. | `.runtime/artifacts/fac136-runs/fac136-scan-881b07725c/`; `.runtime/artifacts/next-five/fac136-dependency-audit-current.json` |
| FAC-137 | Dois casos representativos de restart de processo/checkpointer PostgreSQL e recovery passaram; sem alegação de matriz R01–R12 exaustiva. | `.runtime/artifacts/fac-137/postgres-process-restart.json` |
| FAC-138 | Restore/readback Factory, Registry, OpenBot e artefato passaram; testes de redaction/retenção na bateria focada. | `.runtime/artifacts/fac-138/restore-summary.json`; `.runtime/artifacts/next-five/following-five-review.json` |
| FAC-139 | Relatório local atualizado, 25 testes focados e `quality-fast` 11/11; scorecard global mantém pendência explícita. | `docs/acceptance-report.md`; `.runtime/quality/runs/20261028T044837Z-062eecb2/fast/` |

## Limites do fechamento

A bateria focada cobre 25 testes; não substitui pilotos reais de Telegram/GitHub,
`quality-full`, Sonar ≥80%, matriz exaustiva de indisponibilidades, follow-up externo
aprovado, receipt/HMAC global ou publicação. A proposta QA `80f657fe-4245-438e-85a1-0970c0cb2499`
continua `pending_review`, sem efeito. O scanner FAC-136 alterou apenas fixture. Dados
sintéticos PostgreSQL usados no E2E foram descartados. Nenhum segredo foi usado ou
publicado.

A branch `codex/fac133-conflict-resolution` fica preservada como evidência. Seus ajustes
relevantes foram aplicados aos arquivos de Registry no working tree `main`; não criei
merge commit porque o checkout já tinha centenas de alterações locais não commitadas.

## Evidências e handoff

- Bateria focada: `.runtime/artifacts/next-five/following-five-review.json` (a rodada atual passou 25/25; quality-fast detalhado abaixo).
- Quality fast: `.runtime/quality/runs/20261028T044837Z-062eecb2/fast/` (11/11).
- Etiquetas PostgreSQL: `.runtime/artifacts/next-five/postgres-tag-contract-complete.json` e `.runtime/artifacts/next-five/fac133-final-postgres-e2e.json`.
- Conflito/review: `.runtime/artifacts/next-five/fac133-conflict-resolution.json` e `.runtime/artifacts/next-five/fac133-conflict/qwen-review.json`.
- Restore/recovery: `.runtime/artifacts/fac-137/postgres-process-restart.json` e `.runtime/artifacts/fac-138/restore-summary.json`.
- Relatório: `docs/acceptance-report.md`, `pending_ai_acceptance` sem aceite global alegado.
