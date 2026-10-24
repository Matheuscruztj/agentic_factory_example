# Estado do projeto

Atualizado em 2026-10-24. `specs/fases/` contém o status por fase; este arquivo é o controle operacional único das atividades ainda pendentes, waves, dependências e bloqueios. A especificação original e os critérios de aceite permanecem em `specs/03-TASKS-POR-FASES.md`.

## Concluído recentemente

- P05 / FAC-035: normalização de intake externo e reconciliação idempotente em `packages/task-engine/src/task_engine/intake.py`; 14 testes do Task Engine e Ruff aprovados. Texto externo é preservado como dado não confiável; URLs/anexos aceitam HTTPS e metadados têm limites.
- P05 / FAC-036–040 e P06 / FAC-041–045: implementação local feita em `packages/integrations/`, `workers/`, `packages/context-engine/`, `packages/task-engine/src/task_engine/refinement.py` e `agents/`. Inclui contratos opt-in, polling com cursores injetáveis, discovery/refinamento, manifests, skills, router, context pack e log compaction. Ruff passou nos módulos; testes de aceite especificados continuam pendentes. Nenhum serviço externo foi chamado.
- P02 / FAC-014–020: Customer Registry local com API, UI, migrações, seed sintético idempotente e fluxo Playwright.
- P03 / FAC-021–023: modelos de demandas e revisões, tarefas/DAG e máquina de estados com auditoria e idempotência.
- P03 / FAC-024–027: leases e fencing tokens, outbox/inbox, audit/artifact/snapshot registry e scheduler fake Analyst → Backend → QA sem LLM.
- P04 / FAC-028–034: API de demandas/tarefas, client TypeScript com verificação de drift OpenAPI, painel/Kanban, detalhe e DAG, approvals com hash e decisão humana, SSE com cursor/reconexão e Playwright.
- Validação: 37 testes pytest, Ruff, client OpenAPI sem drift, lint/build/Vitest/Playwright Factory Web, Playwright do Registry e migrações SQLite em upgrade/downgrade/upgrade.

## Pendências por fase

### P00 — segurança, inventário e operação

- [ ] FAC-001: repetir baseline em checkout Git real e registrar SHA/estado.
- [ ] FAC-002: registrar/revisar ADRs e Definition of Done conforme os critérios da fase.
- [ ] FAC-003: operador gerar `.env` com senha escolhida localmente e confirmar que o arquivo está ignorado, sem expor o conteúdo.
- [ ] FAC-005: executar e fixar os spikes OpenBot, LangGraph e Ollama quando as ferramentas/serviços estiverem disponíveis.
- [ ] FAC-006: executar doctor com Factory API, Registry, PostgreSQL e Redis ativos.

### P01 — bootstrap da stack local

- [ ] FAC-009: com `.env` criado pelo operador, iniciar PostgreSQL/Redis e validar persistência após restart.
- [ ] FAC-010–013: executar smoke da Factory API/UI com configuração local, incluindo health, autenticação e status.

### P03 — persistência operacional e Task Engine

Concluído: FAC-024–027. Evidências: 9 testes `packages/task-engine/tests` aprovados, Ruff aprovado e migration validada em SQLite temporário com upgrade/downgrade/upgrade. A reserva concorrente foi exercitada com dois workers e sessões distintas.

### P05 — intake e integrações controladas

- [x] FAC-035: normalizador e reconciliação idempotente implementados; evidência: `uv run pytest packages/task-engine/tests -q` (14 passed) e Ruff nos arquivos tocados.
- [~] FAC-036–040: implementação local feita, testes de aceite pendentes. Conectores reais continuam opt-in; FAC-037 recebe callbacks de cursor para persistência e o operador ainda precisa configurar credenciais/allowlists para live. Ruff passou.

### P06 — Context Engine, personas, skills e orçamento

- [~] FAC-041–045: implementação local feita; executar os testes de aceite definidos em `specs/03-TASKS-POR-FASES.md`. Ruff passou. FAC-046 permanece pendente.

### P04 — Factory API e UI operacional inicial

Concluído: FAC-028–034. Evidências: rotas autenticadas e tipadas, controle de revisão por hash/versão, replay de decisão rejeitado, stream sem dados sensíveis, client verificado contra OpenAPI e fluxo Playwright com scheduler fake.

## Próxima wave

**Próxima atividade: executar os testes de aceite FAC-036–045** com os comandos de `specs/03-TASKS-POR-FASES.md`; então implementar FAC-046. Os testes não foram executados nesta sessão.

Não iniciar integrações externas até as dependências e gates anteriores estarem atendidos.

## Bloqueios ambientais (não impedem trabalho local)

- Não há checkout Git neste diretório; FAC-001 requer o repositório Git real.
- `.env` não foi criado, pois sua senha deve ser escolhida pelo operador; os smokes que exigem credencial e PostgreSQL/Redis ativos continuam pendentes.
- OpenBot, LangGraph e Ollama reais não foram configurados; manter seus adapters opt-in conforme as specs.
