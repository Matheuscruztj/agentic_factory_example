# Estado do projeto

Atualizado em 2026-10-24. `specs/fases/` contém o status por fase; este arquivo é o controle operacional único das atividades ainda pendentes, waves, dependências e bloqueios. Status: `[x]` concluída, `[~]` em andamento, `[!]` bloqueada, `[ ]` não iniciada. A especificação original e os critérios de aceite permanecem em `specs/03-TASKS-POR-FASES.md`.

## Concluído recentemente

- Configuração e integração inicial (2026-10-24): `.env` criado com permissão 600 e ignorado pelo Git; Telegram autenticado, Jira desativado. Compose, migrações e persistência foram validados em PostgreSQL; intake Telegram segue pendente.
- P01 / FAC-009 e FAC-011 (2026-10-24): Compose/PostgreSQL/Redis saudáveis após restart; migrações Factory (`8a91b4d72c10`) e Registry (`0001_create_users`) no head em PostgreSQL; três usuários sintéticos do Registry persistiram após restart. Preflight live `core,postgres,redis,telegram` exit 0 (4 pass, 0 fail/error). Evidência sanitizada: `.runtime/integration-infra.json`.
- P00 / FAC-006 e P01 smoke parcial (2026-10-24): doctor exit 0 com Factory API, Registry, PostgreSQL e Redis ativos; health/live e health/ready das duas APIs retornaram 200. Login real do operador, cookie HttpOnly, sessão, endpoint protegido, bloqueio sem CSRF e logout com CSRF aprovados; Factory reportou Registry disponível sem expor segredos. Evidência: `.runtime/integration-api-smoke.json`. APIs seguem ativas em loopback.
- FAC-036–046 (2026-10-24): critérios locais de GitHub, polling, discovery, refinamento, Telegram, Context Engine e evals passaram em testes fake/determinísticos. FAC-037 agora persiste cursor UTC atomicamente, reconcilia demandas no banco e passa replay/restart com provider fake; GitHub live segue sem credencial/repositório autorizados. Evidência anterior em `.runtime/acceptance-validation.json` e teste em `tests/integrations/test_github_cursor_and_publisher.py`.
- FAC-047–055 (2026-10-24): FAC-047 passou ao vivo com OpenBot seguro, API key e `run_shell` removido; contratos OpenBot, bindings, roteamento, Tool Gateway, limites de colaboração e LangGraph também passaram. FAC-048–053 e FAC-054/055/057/059/060 concluídas; FAC-052 agora integra o chat React à API autenticada e exibe TaskProposal no detalhe da demanda.
- FAC-056–067 (2026-10-24): proposals aceitas por API após aprovação humana vinculada ao hash, escopo explícito e dependências same-demand criam task e evento outbox; dispatcher é idempotente. Retry/DLQ e reconciliação persistente foram adicionados. Probe Docker confirmou que caminho host não montado não fica visível. Review independente valida reviewer distinto, evidências e severidade; publisher GitHub exige aprovações separadas push/PR vinculadas ao repo e SHA. Sem push live. Evidências em testes `tests/workflows/`, `tests/agents/`, `tests/integrations/` e `.runtime/quality/python/`.
- P11 / FAC-077: validator agora força `human_review_required` em código para respostas incertas, baixa confiança ou sem evidência, mesmo quando o judge omite o sinalizador. `tests/unit/test_judge_schema.py` passou (3); calibração Ollama local passou 3/3, sem alterar approval/gates. Rótulos ainda são provisórios e aguardam revisão independente.
- Intake Telegram (live): allowlists autorizadas configuradas no `.env`; um ciclo do worker importou 4 mensagens em 4 demandas no PostgreSQL e persistiu offset modo 600. Evidência sanitizada `.runtime/integration-telegram-intake.json`; não enviou mensagem ao bot.
- P01/FAC-012–013 e P04/FAC-028–034: client envia CSRF e limpa token no logout; smoke Playwright live criou demanda em PostgreSQL, recebeu SSE de auditoria e registrou aprovação humana. Evidência de execução mais recente: `apps/factory-web/e2e/factory-live.spec.ts` (1 passed).

- P05 / FAC-035: normalização de intake externo e reconciliação idempotente em `packages/task-engine/src/task_engine/intake.py`; 14 testes do Task Engine e Ruff aprovados. Texto externo é preservado como dado não confiável; URLs/anexos aceitam HTTPS e metadados têm limites.
- P05 / FAC-036–040 e P06 / FAC-041–046: implementação local e testes fake/determinísticos passaram; Ruff aprovado. Validação live autenticou Telegram sem enviar mensagem; intake real e GitHub seguem sem allowlist/credencial.
- P02 / FAC-014–020: Customer Registry local com API, UI, migrações, seed sintético idempotente e fluxo Playwright.
- P03 / FAC-021–023: modelos de demandas e revisões, tarefas/DAG e máquina de estados com auditoria e idempotência.
- P03 / FAC-024–027: leases e fencing tokens, outbox/inbox, audit/artifact/snapshot registry e scheduler fake Analyst → Backend → QA sem LLM.
- P04 / FAC-028–034: API de demandas/tarefas, client TypeScript com verificação de drift OpenAPI, painel/Kanban, detalhe e DAG, approvals com hash e decisão humana, SSE com cursor/reconexão e Playwright.
- Validação atual: 63 testes pytest passaram; Ruff, eval de contexto (4/4), Vitest/build/ESLint, E2E Factory e E2E Registry passaram. Preflight live, doctor e Alembic PostgreSQL head/check sem drift passaram. Evidências e limitações em `.runtime/acceptance-validation.json`.

## Pendências por fase

### P00 — segurança, inventário e operação

- [x] FAC-001: baseline refeito no checkout Git; HEAD `00d1a782ece691ad510fb4ef318590eea3540fff`, branch `main`, working tree com alterações preexistentes. Inventário em `docs/baseline.md`; snapshot local ignorado em `.runtime/baseline-git-status.txt`.
- [x] FAC-002: revisão do material existente concluída; ADR-01–10 estão em `specs/02-DESIGN-ARQUITETURA.md`, ADR-11 em `docs/adr/ADR-11-local-auth.md`, e Definition of Done/invariantes estão documentados.
- [x] FAC-003: `.env.example`, `.gitignore` e segredo local existem; `.env` e `.runtime` estão ignorados e o `.env` valida sem revelar valores. Gitleaks com imagem fixada encontrou zero findings após allowlist estreita de dois falsos positivos sintéticos.
- [x] FAC-005: spikes OpenBot/Ollama executados ao vivo com versões, endpoints, GPU e limitações registrados em `docs/spikes/`; LangGraph restart está validado em P08.
- [x] FAC-006: doctor com Factory API, Registry, PostgreSQL e Redis ativos; evidência em `.runtime/integration-api-smoke.json`.

### P01 — bootstrap da stack local

- [x] FAC-009: PostgreSQL/Redis ativos e saudáveis após restart; persistência comprovada. Evidência: `.runtime/integration-infra.json`.
- [x] FAC-011: migrações Factory e Registry no head usando PostgreSQL real. Evidência: `.runtime/integration-infra.json`.
- [x] FAC-010 e FAC-012: APIs/health e autenticação/CSRF aprovados ao vivo; migration PG alinhada e sem drift.
- [x] FAC-013: smoke browser live conecta à API/PostgreSQL, cria demanda, recebe evento SSE de auditoria e finaliza aprovação humana.

### P03 — persistência operacional e Task Engine

Concluído: FAC-024–027. Evidências: 9 testes `packages/task-engine/tests` aprovados, Ruff aprovado e migration validada em SQLite temporário com upgrade/downgrade/upgrade. A reserva concorrente foi exercitada com dois workers e sessões distintas.

### P05 — intake e integrações controladas

- [x] FAC-035: normalizador e reconciliação idempotente implementados; evidência: `uv run pytest packages/task-engine/tests -q` (14 passed) e Ruff nos arquivos tocados.
- [x] FAC-036, FAC-038–040: contratos fake, cursor pós-sucesso, evidência, histórico de refinamento, allowlist e flag passaram.
- [x] FAC-037: cursor UTC atômico modo 600 e reconciliação idempotente persistem através de reinicialização; replay fake não duplica demanda. GitHub live segue sem credencial/repositório autorizado.

### P06 — Context Engine, personas, skills e orçamento

- [x] FAC-041–046: manifests/skills, router, pack, compaction e avaliação passaram; 4 casos eval, métricas 1.0, sem regressão do baseline.

### P04 — Factory API e UI operacional inicial

Concluído: FAC-028–034. Evidências: rotas autenticadas e tipadas, controle de revisão por hash/versão, replay de decisão rejeitado, stream sem dados sensíveis, client verificado contra OpenAPI e fluxo Playwright com scheduler fake.

### P07 — OpenBot e conversas por contexto

- [x] FAC-048–051 e FAC-053: contratos passaram em testes fake/security.
- [x] FAC-052: chat React inicia e carrega conversa autenticada por demanda, envia mensagens com CSRF e mostra TaskProposal no detalhe do card.
- [x] FAC-047: OpenBot upstream fixado; API e chave testadas ao vivo; `run_shell` removido do registry e persona QA sem ferramentas. Evidência em `docs/spikes/openbot.md` e `.runtime/acceptance-validation.json`.

### P08 — workflows duráveis

- [x] FAC-054/055/057/059/060: checkpointer persistente passou pause-reopen-resume em PostgreSQL; grafo, HITL, limite concorrente e fakes passaram.
- [x] FAC-056/058: API registra proposta, aceite humano hash-bound, task de follow-up e evento outbox; dispatcher valida snapshot/scope e processa uma vez. RetryQueue persistente tem lease, backoff/DLQ e reconciliador não repete side effect já confirmado.

### P09 — worktree e execução isolada

- [x] FAC-061/063/064/065: worktree independente, patch escopado, classificação de gates e merge isolado com regressão passaram.
- [x] FAC-062: sandbox rejeita segredos e symlinks escapando da raiz; imagem Docker real confirmou que um caminho host não montado não fica visível ao container.
- [x] FAC-066: reviewer read-only distinto do executor valida SHA, evidências, paths e findings por severidade; manifest/rubrica e testes determinísticos adicionados.
- [x] FAC-067: publisher fail-closed exige aprovações humanas separadas de push e PR para repo/SHA exatos; contrato fake passou. Nenhuma publicação live foi iniciada.

### P10 — Quality gates locais

- [x] FAC-068–074: contrato JSON, runners Python/React, Playwright local, scanners locais, agregador determinístico e perfis opcionais concluídos. Python: Ruff 0 erros, mypy 28 arquivos/0 erros, pytest 122 passed/2 skipped. Frontend: Vitest 3 passed, typecheck, ESLint e build passaram. Playwright Factory/Registry passou (1 teste cada). Security gates sem findings high/critical. Perf Locust e ZAP Baseline no build estático passaram (6 alertas: 0 high/critical, 2 medium, 2 low). Sonar Community ficou preparado opt-in sem `SONAR_TOKEN`.

### P11 — Agent evals, feedback e prompts

- [x] FAC-075: scorecard objetivo com proveniência por persona, modelo/prompt/context/skill, latência, tokens, custo e aceite.
- [~] FAC-076: 11 casos sintéticos mais 3 de calibração têm hashes congelados; 10 rótulos seguem provisórios aguardando revisão humana independente.
- [~] FAC-077: judge Ollama usa modelo separado, schema estrito e escalação enforced pelo validator; calibração local mais recente passou (accuracy/recall 1.0, FPR 0), sem qualquer alteração de gate/aprovação. Aceite segue pendente de revisão humana independente dos rótulos provisórios.
- [x] FAC-078: feedback autenticado e imutável vincula run, task, hash do prompt, modelo, versão de requisito, comentário e evidências; resumo de primeira aprovação/retrabalho disponível na UI.
- [x] FAC-079: comparação pareada de prompts registra hashes, diff, custo, latência, regressões críticas e recomendação humana; auto-promoção desabilitada.
- [x] FAC-080: promoção/rollback de prompt exige sessão autenticada, CSRF, hashes de prompt/experimento e trilha imutável; UI pede ação explícita do operador.

### P12 — observabilidade local

- [x] FAC-081–086 — IDs de correlação, redaction, Ollama, NVIDIA, OpenTelemetry/Phoenix opt-in e dashboard medido vs estimado. A coleta NVIDIA foi validada ao vivo; Phoenix/Collector seguem opcionais; sem fonte de preços, custo estimado fica indisponível.

### P13 — demonstrações e segurança adversarial

- [x] FAC-087 — CPF sintético: reproduz falso aceite por comprimento e valida checksum; CPF não é armazenado no modelo.
- [x] FAC-088 — telefone opcional em API/UI do Registry, migration `0002`, E2E passou; grafo/auditoria registra dependência entre tarefas.
- [x] FAC-089 — QA follow-up usa snapshot existente, outbox é idempotente, demanda/revisões originais preservadas.
- [x] FAC-090 — upgrade de dependência vira proposta evidenciada, sem alterar lockfile; publicação requer aprovação.
- [x] FAC-091 — retry/evento duplicado recuperados após reabrir banco, com chave idempotente preservada.
- [x] FAC-092 — testes red-team negam tools inventadas, leitura de secrets e execução de proposta.
- [~] FAC-093 — scorecard draft gerado como `pending_independent_human_review`; falta assinatura de reviewer humano independente.

### P14 — opcionais e hardening

- [x] FAC-094–099 — Projects/Jira opt-in com contratos fakes; webhook HMAC; propostas de upgrade; backup SQLite restore e PostgreSQL restore em DB temporário; roadmap CI/deploy não habilitado.

O backlog registra 96 atividades concluídas, 3 em andamento, 0 bloqueadas e 0
ainda não iniciadas; os detalhes e critérios permanecem por atividade em
[`implementation-backlog.json`](specs/implementation-backlog.json).

## Próxima wave

**Pendências de conclusão:** FAC-076/077 aguardam rótulos e revisão humana da
calibração; FAC-093 aguarda assinatura de aceite independente. As atividades de
código restantes do backlog foram implementadas e verificadas.

Evidências da wave P10/P11: `.runtime/quality/` e `.runtime/evals/`. FAC-076/077
aguardam julgamento humano independente dos 10 rótulos provisórios e revisão da
calibração (última execução local: 3/3). FAC-093 aguarda assinatura humana independente.
Pacote preparado em `docs/human-review-packet.md` e `evals/human-review-packet.json`;
scorecard regenerado e permanece `pending_independent_human_review`.

Autenticação Telegram já validada ao vivo via `getMe`, sem enviar mensagens.
O fluxo live foi executado com os IDs autorizados; evidência em
`.runtime/integration-telegram-intake.json` (4 mensagens/demandas, offset persistido).

## Dependências ambientais

- FAC-001 concluída: checkout Git confirmado, HEAD observado `00d1a782ece691ad510fb4ef318590eea3540fff`; baseline e limitações registrados em `docs/baseline.md`.
- FAC-009/011 concluídas em 2026-10-24; evidência operacional detalhada em `.runtime/integration-infra.json`.
- `.env` disponível; senha gerada em `.runtime/operator-password.txt`.
- Intake Telegram live exercitado com allowlists locais configuradas em `.env`; não repetir a mensagem de teste sem necessidade, pois cria demanda.
- GitHub sem credencial/repositório de validação. Jira desativado e adiado.
- OpenBot e Ollama estão configurados em Compose local e validados ao vivo; LangGraph segue validado no checkpointer PostgreSQL. GitHub e Telegram intake ainda dependem de destinos autorizados.

- GitHub sem token/repositório de validação; Telegram sem chat/user IDs autorizados.
