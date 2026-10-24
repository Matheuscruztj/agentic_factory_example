# Agentic Factory Local v2 — TASKS / Plano detalhado por fases

**Esta lista substitui o antigo plano W0-W11** (que ainda citava NiceGUI, multi-tenant e repositórios externos). É a ordem de implementação proposta, não um relatório de trabalho realizado. Código e testes ainda precisam ser implementados pela equipe/IA. Os caminhos são os *targets* de referência, ajustáveis após o inventário FAC-001.

## Protocolo obrigatório para toda tarefa

1. Ler SPECIFY, DESIGN, ADRs e arquivos reais; não criar pasta duplicada por conveniência. 2. Inspecionar dependências e prova de aceite antes de implementar. 3. Fazer alteração pequena, preferencialmente em branch/worktree própria, testável. 4. Executar validação automatizada com saída JSON uma linha, exit 0/1/2. 5. Anexar artifact, hashes, métricas e evidência à task. 6. Não marcar done sem gates, revisão e aprovação quando exigida. 7. Falha de configuração => preflight e exit 2, não gastar tokens em loop de LLM. 8. Respeitar permissões do perfil e NUNCA expor segredo.

## Resumo executivo das fases

| Fase | Prioridade | Atividades | Marco verificável |
|---|---|---:|---|
| P00 — Inventário, decisões, segurança e preflight | P0 | 6 | Preflight offline e suite de testes do validador verdes; matriz de decisões e segredos aprovada. |
| P01 — Bootstrap da stack local e serviços | P0 | 7 | API responde health, UI compila, migrations preparam bancos e doctor valida serviços locais. |
| P02 — Customer Registry: aplicação real de cadastro | P0 | 7 | Criar, buscar, editar e desativar usuário pela interface e API; testes verdes. |
| P03 — Persistência operacional e Task Engine | P0 | 7 | Teste de DAG, claim concorrente, dedupe, outbox e retomada simulada aprovado. |
| P04 — Factory API e UI operacional inicial | P0 | 7 | Criar demanda na interface e ver DAG/status, sem backdoor de escrita. |
| P05 — Entrada de demandas e integração externa controlada | P0 | 6 | GitHub Issue real vira Demand uma única vez; modo offline continua funcional. |
| P06 — Context Engine, personas, skills e orçamento | P0 | 6 | Skill router e context pack determinísticos economizam tokens sem omitir política. |
| P07 — OpenBot: agentes descentralizados e conversa por card | P0 | 7 | @qa em ISSUE existente responde com contexto e, se necessário, gera TaskProposal sem execução livre. |
| P08 — LangGraph: workflows duráveis, subflows e retomada | P0 | 7 | Workflows pausam/reiniciam/retomam sem duplicar ações e resolvem DAG de dependências. |
| P09 — Git worktree, sandbox e execução de código | P0 | 7 | Duas tasks isoladas geram patches auditáveis; arquivos protegidos rejeitados; integração testada. |
| P10 — Quality gates locais, scripts compactos e segurança | P0 | 7 | Todos os gates têm saída 0/1/2; falhas de código vs infra distinguidas. |
| P11 — Agent Evals, Judge, feedback e evolução de prompts | P0 | 6 | Baseline de eval reprodutível, candidato não promovido automaticamente. |
| P12 — Observabilidade local e otimização de recursos | P0 | 6 | Uma task possui traces resumidos correlacionados; falha Phoenix não bloqueia operação. |
| P13 — Demonstrações reais e testes adversariais | P0 | 7 | Matriz UAT assinada por humano com evidência, logs compactos e métricas. |
| P14 — Integrações opcionais e hardening pós-MVP | P1/P2 | 6 | Cada integração pode ser ligada/desligada isoladamente e possui testes de contrato. |

**Sequência crítica:** P00→P01→P02→P03→P04→P05/P06→P07→P08→P09→P10→P11→P12→P13. P05 entrada GitHub pode avançar em paralelo a P06 Context após P03; P07 e P08 podem avançar em ramos separados após seus spikes, integrados no P09. P10 qualidade básica inicia com P02; P11 Evals só mede ações comparáveis após contrato P10. P12 pode ter captura básica desde P01. P14 é opcional posterior ao MVP.

## Critérios transversais de aceite

- **DoR (Ready):** task tem origem, responsável, problema, contrato, aceites verificáveis, dependências, escopo de arquivos, riscos, política HITL e orçamento de execução.
- **DoD (Done):** diff controlado, testes feitos, scripts 0/1/2, logs/artifacts com SHA, review independente, estado persistido e documentação de mudança; aprovação humana onde aplicável.
- **Evidência:** comando, código de saída, resumo JSON, link local ao artefato, SHA base, SHA alterado, número de tentativas; proibir frases como “testei mentalmente”.
- **Paralelismo:** lanes diferentes são candidatas, não promessa; respeitar dependeOn, locks de paths, leases e limite LLM 1 de cada vez na GPU 8 GB.
- **Escopo:** P0 começa sem secrets externos e sem cloud; P1/P2 opt-in e não bloqueante.

## P00 — Inventário, decisões, segurança e preflight (P0)

**Objetivo:** Conseguir reproduzir estado atual, escolher versões e barrar falhas de configuração antes do primeiro agente.

**Gate de saída da fase:** Preflight offline e suite de testes do validador verdes; matriz de decisões e segredos aprovada.

**Pacotes de execução paralela:** core: FAC-001, FAC-002, FAC-003, FAC-004, research: FAC-005, platform: FAC-006. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-001 — Auditar repositório e congelar baseline

- **Responsável (persona):** Tech Lead; **lane:** `core`; **risco:** normal.
- **DependsOn:** nenhuma.
- **Arquivos/módulos previstos:** `docs/baseline.md; docs/adr/`.
- **Passos de implementação:**
  1. Listar árvores reais, branches, dependências e portas já usadas.
  2. Identificar código aproveitável vs material apenas de especificação.
  3. Registrar SHA inicial, gaps e migrações propostas.
- **Aceite verificável:** Nenhum arquivo legado é reescrito sem evidência do diagnóstico.
- **Validação / evidência mínima:** Revisão humana do inventário + git status sem alterações inesperadas; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-002 — Formalizar invariantes, ADRs e Definition of Done

- **Responsável (persona):** Architect; **lane:** `core`; **risco:** normal.
- **DependsOn:** `FAC-001`.
- **Arquivos/módulos previstos:** `docs/adr/*.md; docs/definition-of-done.md`.
- **Passos de implementação:**
  1. Registrar monorepo único, local-only e OpenBot/LangGraph/Task Engine.
  2. Definir permissões de leitura/escrita e critérios de aceite de etapa.
  3. Criar matriz de mudanças sensíveis que exigem HITL.
- **Aceite verificável:** ADRs explicitam owner de estados e proibições verificáveis.
- **Validação / evidência mínima:** Checklist de ADRs + auditoria humana; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-003 — Criar .env.example, .gitignore e segredo local

- **Responsável (persona):** Platform; **lane:** `core`; **risco:** high.
- **DependsOn:** `FAC-001`, `FAC-002`.
- **Arquivos/módulos previstos:** `.env.example; .env; .gitignore; config/`.
- **Passos de implementação:**
  1. Catalogar variáveis habilitadas/opt-in com placeholders seguros.
  2. Ignorar .env, chaves PEM, dumps, artefatos e worktrees no Git.
  3. Documentar rotação, geração do APP_SECRET_KEY e variantes host/contêiner.
- **Aceite verificável:** Nenhuma credencial real está no repositório; boot aceita integrações desabilitadas.
- **Validação / evidência mínima:** git check-ignore .env; Gitleaks scan local; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-004 — Integrar preflight offline e live read-only

- **Responsável (persona):** Platform; **lane:** `core`; **risco:** high.
- **DependsOn:** `FAC-003`.
- **Arquivos/módulos previstos:** `scripts/validate_env.py; tests/test_validate_env.py`.
- **Passos de implementação:**
  1. Executar syntax/required offline sem acessar rede.
  2. Implementar consultas read-only e classificação CONFIG/AUTH/NETWORK/SERVICE.
  3. Exibir uma linha JSON e exit 0/1/2 com masking de secrets.
- **Aceite verificável:** Diferencia chave inválida e rede indisponível sem enviar mensagens ou criar Issues.
- **Validação / evidência mínima:** python -m unittest discover -s tests -p test_validate_env.py -q; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-005 — Spikes OpenBot, LangGraph e Ollama host

- **Responsável (persona):** Architect/AI; **lane:** `research`; **risco:** normal.
- **DependsOn:** `FAC-002`, `FAC-003`.
- **Arquivos/módulos previstos:** `docs/spikes/{openbot,langgraph,ollama}.md`.
- **Passos de implementação:**
  1. Fixar versões e testar autenticação/endpoint reais OpenBot.
  2. Provar checkpoint LangGraph em storage persistente com restart.
  3. Testar alcance Ollama host↔Docker e registrar VRAM/modelos instalados.
- **Aceite verificável:** Contratos e limitações citados com versões, ou bloqueio técnico explícito.
- **Validação / evidência mínima:** Smoke manual por spike + resultados e comandos em Markdown; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-006 — Scripts de operação com status compacto

- **Responsável (persona):** Platform; **lane:** `platform`; **risco:** normal.
- **DependsOn:** `FAC-004`.
- **Arquivos/módulos previstos:** `scripts/{doctor,validate_checks,local_boot}.py; Makefile`.
- **Passos de implementação:**
  1. Criar entrypoints de bootstrap/doctor/stop e validação de JSON.
  2. Garantir que erros de script gerem exit 2 e stdout estruturado.
  3. Manter artefatos completos em .runtime/logs e limites de tail.
- **Aceite verificável:** Um comando devolve status claro sem ler milhares de linhas de log.
- **Validação / evidência mínima:** pytest tests/unit/test_script_contracts.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P01 — Bootstrap da stack local e serviços (P0)

**Objetivo:** Criar fundação reproduzível sem nuvem, incluindo API Python, React e Compose isolado.

**Gate de saída da fase:** API responde health, UI compila, migrations preparam bancos e doctor valida serviços locais.

**Pacotes de execução paralela:** platform: FAC-007, FAC-009, frontend: FAC-008, FAC-013, backend: FAC-010, database: FAC-011, security: FAC-012. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-007 — Configurar uv workspace e qualidade Python

- **Responsável (persona):** Platform; **lane:** `platform`; **risco:** normal.
- **DependsOn:** `FAC-002`, `FAC-006`.
- **Arquivos/módulos previstos:** `pyproject.toml; uv.lock; ruff.toml; packages/*/pyproject.toml`.
- **Passos de implementação:**
  1. Criar layout src para apps/packages.
  2. Configurar uv sync --frozen e Ruff/mypy/pytest com versões fixadas.
  3. Adicionar comandos por pacote e verificação de import circular.
- **Aceite verificável:** Workspace Python instala e roda lint/test em checkout limpo.
- **Validação / evidência mínima:** uv sync; uv run ruff check .; uv run pytest -q; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-008 — Configurar React/Vite/shadcn e tooling

- **Responsável (persona):** Frontend; **lane:** `frontend`; **risco:** normal.
- **DependsOn:** `FAC-002`, `FAC-006`.
- **Arquivos/módulos previstos:** `apps/factory-web/{package.json,vite.config.ts,src/}; pnpm-lock.yaml`.
- **Passos de implementação:**
  1. Criar Vite React TS, Tailwind e shadcn/ui com tokens semânticos.
  2. Configurar pnpm, ESLint, typecheck, Vitest e aliases.
  3. Criar shell mínimo com roteamento e empty/loading states.
- **Aceite verificável:** Frontend compila com design responsivo e sem erros TS.
- **Validação / evidência mínima:** pnpm --dir apps/factory-web build; pnpm --dir apps/factory-web test; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-009 — Definir Compose base e redes locais

- **Responsável (persona):** Platform; **lane:** `platform`; **risco:** normal.
- **DependsOn:** `FAC-003`, `FAC-007`.
- **Arquivos/módulos previstos:** `infra/compose/base.yml; infra/compose/README.md`.
- **Passos de implementação:**
  1. Subir Postgres e Redis com volumes/healthcheck e 127.0.0.1 bind.
  2. Configurar perfis opcionais OpenBot/Phoenix/Sonar sem exposição pública.
  3. Mapear endereços host vs container do Ollama e das APIs.
- **Aceite verificável:** Serviços base sobem e persistem dados com restart sem portas públicas.
- **Validação / evidência mínima:** docker compose -f infra/compose/base.yml config; docker compose ps; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-010 — Criar API FastAPI e injeção de configuração

- **Responsável (persona):** Backend; **lane:** `backend`; **risco:** normal.
- **DependsOn:** `FAC-007`, `FAC-009`.
- **Arquivos/módulos previstos:** `apps/factory-api/src/factory_api/{main,config,dependencies}.py`.
- **Passos de implementação:**
  1. Criar FastAPI app factory e schemas Pydantic Settings.
  2. Expor health/live e health/ready sem revelar segredos.
  3. Implementar error envelope e versionamento /api/v1.
- **Aceite verificável:** API fornece liveness e readiness distinto por dependência.
- **Validação / evidência mínima:** pytest tests/integration/test_api_health.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-011 — Configurar DB SQLAlchemy, Alembic e sessões

- **Responsável (persona):** Database; **lane:** `database`; **risco:** normal.
- **DependsOn:** `FAC-009`, `FAC-010`.
- **Arquivos/módulos previstos:** `packages/shared-contracts/src/shared_contracts/db.py; apps/factory-api/alembic/`.
- **Passos de implementação:**
  1. Configurar engine/sessions por request/worker.
  2. Criar migrations baseline sem manipular dados de produção.
  3. Adicionar teste upgrade/downgrade em banco descartável.
- **Aceite verificável:** Sessões fecham corretamente e migrations são reproduzíveis.
- **Validação / evidência mínima:** uv run alembic upgrade head; pytest tests/integration/test_db_migrations.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-012 — Estabelecer autenticação local do operador

- **Responsável (persona):** Security/Backend; **lane:** `security`; **risco:** high.
- **DependsOn:** `FAC-010`, `FAC-011`.
- **Arquivos/módulos previstos:** `apps/factory-api/src/factory_api/auth/; apps/factory-web/src/features/auth/`.
- **Passos de implementação:**
  1. Escolher sessão segura de single operator com credencial local e CSRF.
  2. Restringir mutações e endpoints de artifacts.
  3. Testar sessão expirada, origem não autorizada e rate limits.
- **Aceite verificável:** Acesso a 127.0.0.1 não substitui autenticação; segredo nunca vai para browser.
- **Validação / evidência mínima:** pytest tests/security/test_authz_local.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-013 — Health dashboard mínimo conectado à API

- **Responsável (persona):** Frontend; **lane:** `frontend`; **risco:** normal.
- **DependsOn:** `FAC-008`, `FAC-010`, `FAC-012`.
- **Arquivos/módulos previstos:** `apps/factory-web/src/features/dashboard/; src/lib/api/`.
- **Passos de implementação:**
  1. Criar client fetch tipado e tratamento uniforme de erro.
  2. Mostrar status DB/Redis/Ollama/integrações sem tokens.
  3. Validar estados indisponível/loading e navegação.
- **Aceite verificável:** UI distingue configuração pendente de falha operacional.
- **Validação / evidência mínima:** Vitest para status UI + Playwright smoke inicial; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P02 — Customer Registry: aplicação real de cadastro (P0)

**Objetivo:** Entregar alvo funcional e testado antes de automatizar agentes que mexem nele.

**Gate de saída da fase:** Criar, buscar, editar e desativar usuário pela interface e API; testes verdes.

**Pacotes de execução paralela:** product: FAC-014, backend: FAC-015, database: FAC-016, frontend: FAC-017, qa: FAC-018, FAC-019, docs: FAC-020. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-014 — Especificar domínio e regras do cadastro

- **Responsável (persona):** Analyst; **lane:** `product`; **risco:** normal.
- **DependsOn:** `FAC-002`.
- **Arquivos/módulos previstos:** `docs/registry-domain.md; specs/demands/seed-registry/`.
- **Passos de implementação:**
  1. Definir username, nome, email único, status e campos mínimos.
  2. Esclarecer política CPF/telefone como features posteriores.
  3. Definir aceites positivos e negativos e dados pessoais sintéticos.
- **Aceite verificável:** Contrato da demo claro, com dados sensíveis sintéticos e sem requisito indefinido.
- **Validação / evidência mínima:** Revisão humana + schema de aceites; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-015 — Criar FastAPI separado para cadastro

- **Responsável (persona):** Backend; **lane:** `backend`; **risco:** normal.
- **DependsOn:** `FAC-007`, `FAC-014`.
- **Arquivos/módulos previstos:** `apps/customer-registry/api/src/customer_registry/{main,routers,schemas}/`.
- **Passos de implementação:**
  1. Criar rotas /users POST GET PATCH e desativação com erros padronizados.
  2. Validar payloads com Pydantic e limites de tamanho.
  3. Separar handlers de services/repository e usar dependências de DB.
- **Aceite verificável:** API CRUD atende contrato e não depende da Factory API para funcionar.
- **Validação / evidência mínima:** pytest apps/customer-registry/api/tests/unit; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-016 — Criar tabelas e migrations cadastro

- **Responsável (persona):** Database; **lane:** `database`; **risco:** normal.
- **DependsOn:** `FAC-011`, `FAC-014`.
- **Arquivos/módulos previstos:** `apps/customer-registry/api/alembic/versions/; models/user.py`.
- **Passos de implementação:**
  1. Modelar users com ID, normalized_email unique, status e timestamps.
  2. Criar migration forward/back e testes de unicidade.
  3. Construir repositório SQLAlchemy com concorrência segura.
- **Aceite verificável:** Email duplicado gera conflito 409 e schema tem constraints.
- **Validação / evidência mínima:** pytest apps/customer-registry/api/tests/integration/test_users_db.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-017 — Criar frontend de cadastro React

- **Responsável (persona):** Frontend; **lane:** `frontend`; **risco:** normal.
- **DependsOn:** `FAC-008`, `FAC-014`.
- **Arquivos/módulos previstos:** `apps/customer-registry/web/src/features/users/`.
- **Passos de implementação:**
  1. Configurar Vite React Tailwind e shadcn/ui seguindo os padrões do factory-web.
  2. Implementar lista, criação, edição, desativação e feedback de erro.
  3. Garantir labels, validação e estados de loading.
- **Aceite verificável:** Fluxos cadastro funcionam desktop/mobile, com acessibilidade básica.
- **Validação / evidência mínima:** Vitest + Playwright create/edit/list + axe smoke; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-018 — Cobrir API com testes de unidade e integração

- **Responsável (persona):** QA; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-015`, `FAC-016`.
- **Arquivos/módulos previstos:** `apps/customer-registry/api/tests/{unit,integration}/`.
- **Passos de implementação:**
  1. Testar email duplicado, inválido, limites, usuário inexistente e desativação.
  2. Gerar fixtures independentes e DB isolado.
  3. Adicionar matriz de resposta esperada por endpoint.
- **Aceite verificável:** Bug reproduzível possui teste e execução não depende de modelos LLM.
- **Validação / evidência mínima:** pytest -q apps/customer-registry/api/tests; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-019 — Cobrir UI com smoke E2E

- **Responsável (persona):** QA/Frontend; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-017`, `FAC-018`.
- **Arquivos/módulos previstos:** `apps/customer-registry/web/e2e/`.
- **Passos de implementação:**
  1. Subir frontend/backend de testes em ambiente efêmero.
  2. Testar fluxo criar/editar/desativar com Playwright.
  3. Capturar screenshot e trace apenas em falha, resumindo resultado.
- **Aceite verificável:** E2E aprovado com dados sintéticos; artefatos por execução.
- **Validação / evidência mínima:** pnpm playwright test --reporter=line; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-020 — Documentar runbook e fixtures base

- **Responsável (persona):** Docs/QA; **lane:** `docs`; **risco:** normal.
- **DependsOn:** `FAC-015`, `FAC-019`.
- **Arquivos/módulos previstos:** `apps/customer-registry/README.md; tests/fixtures/`.
- **Passos de implementação:**
  1. Escrever comandos locais de start, reset e migration.
  2. Adicionar seed idempotente de usuários fictícios.
  3. Fixar bugs intencionais somente em fixtures branches separadas.
- **Aceite verificável:** Outro dev reproduz demo e fixtures sem credencial externa.
- **Validação / evidência mínima:** Follow README em checkout limpo; smoke do cadastro; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P03 — Persistência operacional e Task Engine (P0)

**Objetivo:** Criar autoridade transacional de atividades, DAG, locks, retries e histórico independente dos frameworks de agentes.

**Gate de saída da fase:** Teste de DAG, claim concorrente, dedupe, outbox e retomada simulada aprovado.

**Pacotes de execução paralela:** database: FAC-021, backend: FAC-022, FAC-023, core: FAC-024, FAC-025, platform: FAC-026, qa: FAC-027. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-021 — Implementar schema de demandas e revisões

- **Responsável (persona):** Database; **lane:** `database`; **risco:** normal.
- **DependsOn:** `FAC-011`, `FAC-020`.
- **Arquivos/módulos previstos:** `packages/task-engine/src/task_engine/models.py; migrations/`.
- **Passos de implementação:**
  1. Criar Demand, RequirementRevision, Decision e índices (source,external_id).
  2. Implementar optimistic version e snapshots imutáveis.
  3. Criar APIs transacionais para revisões.
- **Aceite verificável:** Mesmo evento/Issue não cria duas demandas e versão aprovada é imutável.
- **Validação / evidência mínima:** pytest tests/integration/test_demand_repository.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-022 — Implementar Task e dependency DAG

- **Responsável (persona):** Backend; **lane:** `backend`; **risco:** normal.
- **DependsOn:** `FAC-021`.
- **Arquivos/módulos previstos:** `packages/task-engine/src/task_engine/{tasks,dependencies}.py`.
- **Passos de implementação:**
  1. Criar Task, TaskDependency, critérios, escopos e perfil responsável.
  2. Implementar detecção de ciclos e deps inexistentes.
  3. Calcular readiness a partir de resultados e approvals.
- **Aceite verificável:** Tarefa bloqueada não é liberada e ciclos geram erro tipado.
- **Validação / evidência mínima:** pytest tests/unit/test_task_dag.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-023 — Implementar state machine determinística

- **Responsável (persona):** Backend; **lane:** `backend`; **risco:** normal.
- **DependsOn:** `FAC-022`.
- **Arquivos/módulos previstos:** `packages/task-engine/src/task_engine/transitions.py`.
- **Passos de implementação:**
  1. Declarar allowed transitions para Demand/Task/Run.
  2. Exigir expected_version, actor, reason e idempotency key.
  3. Persistir log de transições e rejeitar saltos inválidos.
- **Aceite verificável:** LLM não altera status diretamente; transição inválida gera erro estável.
- **Validação / evidência mínima:** pytest tests/unit/test_state_transitions.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-024 — Leases, fencing tokens e reserva atômica

- **Responsável (persona):** Backend/Database; **lane:** `core`; **risco:** high.
- **DependsOn:** `FAC-022`, `FAC-023`.
- **Arquivos/módulos previstos:** `packages/task-engine/src/task_engine/{leases,scheduler}.py`.
- **Passos de implementação:**
  1. Usar claim atômico por task com lock de banco.
  2. Gerar fencing token e heartbeat/expiração.
  3. Rejeitar commit tardio de worker cujo lease foi perdido.
- **Aceite verificável:** Duas instâncias não executam mesma task simultaneamente.
- **Validação / evidência mínima:** pytest tests/integration/test_concurrent_claims.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-025 — Outbox transacional e idempotência de eventos

- **Responsável (persona):** Backend; **lane:** `core`; **risco:** high.
- **DependsOn:** `FAC-021`, `FAC-023`.
- **Arquivos/módulos previstos:** `packages/task-engine/src/task_engine/{outbox,inbox}.py`.
- **Passos de implementação:**
  1. Criar EventInbox/Outbox com event_id e dedupe.
  2. Publicar somente após commit com retries.
  3. Testar delivery duplicado e rede temporariamente falha.
- **Aceite verificável:** Processamento at-least-once não vira efeitos duplicados no domínio.
- **Validação / evidência mínima:** pytest tests/integration/test_outbox_idempotency.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-026 — Audit trail, artifact registry e snapshots

- **Responsável (persona):** Platform; **lane:** `platform`; **risco:** normal.
- **DependsOn:** `FAC-021`, `FAC-023`.
- **Arquivos/módulos previstos:** `packages/task-engine/src/task_engine/audit.py; specs/demands/`.
- **Passos de implementação:**
  1. Persistir decisões, evidence hashes e mudanças de state.
  2. Salvar artefatos sob path allowlisted com SHA-256.
  3. Gerar docs Markdown de requisitos/planos a partir de revisões aprovadas.
- **Aceite verificável:** Toda task/run tem links a evidências, sem credenciais ou dumps de prompts.
- **Validação / evidência mínima:** pytest tests/unit/test_audit_artifacts.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-027 — Scheduler fake sem LLM para primeira simulação

- **Responsável (persona):** Backend/QA; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-024`, `FAC-025`, `FAC-026`.
- **Arquivos/módulos previstos:** `workers/src/factory_workers/scheduler.py; tests/simulations/`.
- **Passos de implementação:**
  1. Criar tasks mock Analyst/Backend/QA e eventos.
  2. Implementar claim -> run -> checks -> approval simulados.
  3. Reexecutar mensagens duplicadas e reiniciar worker em meio ao processo.
- **Aceite verificável:** Vertical slice de estado percorre várias tasks sem chamar modelos.
- **Validação / evidência mínima:** pytest tests/simulations/test_vertical_slice_fake.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P04 — Factory API e UI operacional inicial (P0)

**Objetivo:** Expor demandas, tarefas, approvals e eventos numa interface React antes de integrar agentes reais.

**Gate de saída da fase:** Criar demanda na interface e ver DAG/status, sem backdoor de escrita.

**Pacotes de execução paralela:** backend: FAC-028, FAC-033, frontend: FAC-029, FAC-030, FAC-031, security: FAC-032, qa: FAC-034. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-028 — Criar APIs tipadas de demandas e tarefas

- **Responsável (persona):** Backend; **lane:** `backend`; **risco:** normal.
- **DependsOn:** `FAC-021`, `FAC-022`, `FAC-023`, `FAC-012`.
- **Arquivos/módulos previstos:** `apps/factory-api/src/factory_api/routers/{demands,tasks}.py`.
- **Passos de implementação:**
  1. Criar endpoints para intake manual, consulta e filtros por estado.
  2. Validar payloads e compatibilidade de versões.
  3. Testar idempotency key e erros HTTP estáveis.
- **Aceite verificável:** OpenAPI descreve contratos reais e não executa shell.
- **Validação / evidência mínima:** pytest tests/integration/test_factory_demands_api.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-029 — Gerar client TypeScript de OpenAPI

- **Responsável (persona):** Frontend/Backend; **lane:** `frontend`; **risco:** normal.
- **DependsOn:** `FAC-028`, `FAC-008`.
- **Arquivos/módulos previstos:** `apps/factory-web/src/lib/api/generated/; scripts/gen_client.py`.
- **Passos de implementação:**
  1. Exportar OpenAPI congelada durante tests.
  2. Gerar client com ferramenta pinada e DTOs type-safe.
  3. Adicionar drift check de schema e erros compartilhados.
- **Aceite verificável:** Alteração de contrato incompatível falha teste local.
- **Validação / evidência mínima:** python scripts/gen_client.py --check; pnpm typecheck; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-030 — Dashboard e Kanban local

- **Responsável (persona):** Frontend; **lane:** `frontend`; **risco:** normal.
- **DependsOn:** `FAC-028`, `FAC-029`.
- **Arquivos/módulos previstos:** `apps/factory-web/src/features/{dashboard,kanban}/`.
- **Passos de implementação:**
  1. Criar colunas por estado, cards com ID/owner/bloqueio.
  2. Buscar via TanStack Query com paginação/filtros.
  3. Atualizar status somente via endpoints e permissions.
- **Aceite verificável:** Kanban retrata DB, não estado local imaginado pela UI.
- **Validação / evidência mínima:** Vitest + Playwright board smoke; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-031 — Detalhe da demanda e DAG navegável

- **Responsável (persona):** Frontend; **lane:** `frontend`; **risco:** normal.
- **DependsOn:** `FAC-030`.
- **Arquivos/módulos previstos:** `apps/factory-web/src/features/demands/`.
- **Passos de implementação:**
  1. Criar vista Issue -> refinamentos -> tasks -> runs.
  2. Renderizar deps e bloqueios com acessibilidade.
  3. Mostrar artefatos/evidence e botões contextuais sob policy.
- **Aceite verificável:** Operador entende por que tarefa está bloqueada e qual gate falta.
- **Validação / evidência mínima:** Playwright demands detail test; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-032 — Implementar approval inbox e revisão humana

- **Responsável (persona):** Backend/Frontend; **lane:** `security`; **risco:** high.
- **DependsOn:** `FAC-023`, `FAC-028`, `FAC-030`.
- **Arquivos/módulos previstos:** `apps/factory-api/src/factory_api/routers/approvals.py; apps/factory-web/src/features/approvals/`.
- **Passos de implementação:**
  1. Criar ApprovalRequest imutável com hash do objeto/versão.
  2. Implementar approve/reject/request-changes com session do humano e comentário.
  3. Impedir agente de decidir aprovação própria e teste replay.
- **Aceite verificável:** Nenhuma alteração de escopo/PR é autorizada só pela resposta do modelo.
- **Validação / evidência mínima:** pytest tests/security/test_human_approval.py; Playwright approval; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-033 — SSE confiável para logs e estados

- **Responsável (persona):** Backend/Frontend; **lane:** `backend`; **risco:** normal.
- **DependsOn:** `FAC-028`, `FAC-030`.
- **Arquivos/módulos previstos:** `apps/factory-api/src/factory_api/routers/events.py; apps/factory-web/src/hooks/useRunEvents.ts`.
- **Passos de implementação:**
  1. Publicar stream paginado por cursor e heartbeat.
  2. Suportar reconnect sem repetir ações e redigir logs.
  3. Mostrar progress/status e link do artifact completo sob permissão.
- **Aceite verificável:** Cliente reconecta após queda sem perder eventos nem expor secrets.
- **Validação / evidência mínima:** pytest tests/integration/test_event_stream.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-034 — Testes E2E painel e acessibilidade

- **Responsável (persona):** QA; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-030`, `FAC-031`, `FAC-032`, `FAC-033`.
- **Arquivos/módulos previstos:** `apps/factory-web/e2e/`.
- **Passos de implementação:**
  1. Cobrir intake manual, filtros, detalhes, bloqueio e aprovações.
  2. Testar keyboard navigation/loading/error.
  3. Gerar relatório compacto e screenshots em falha.
- **Aceite verificável:** Smoke end-to-end UI passa com Fake Scheduler.
- **Validação / evidência mínima:** pnpm playwright test; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P05 — Entrada de demandas e integração externa controlada (P0)

**Objetivo:** Receber demandas manualmente e por GitHub com polling; canais extras ficam habilitáveis sem alterar o domínio.

**Gate de saída da fase:** GitHub Issue real vira Demand uma única vez; modo offline continua funcional.

**Pacotes de execução paralela:** backend: FAC-035, integration: FAC-036, FAC-037, FAC-040, product: FAC-038, FAC-039. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-035 — Normalizador de intake e deduplicação

- **Responsável (persona):** Backend; **lane:** `backend`; **risco:** normal.
- **DependsOn:** `FAC-021`, `FAC-028`.
- **Arquivos/módulos previstos:** `packages/integrations/src/integrations/intake.py`.
- **Passos de implementação:**
  1. Criar DTO fonte/IDs/url/autor/texto/attachments.
  2. Sanitizar input e preservar conteúdo como dado não confiável.
  3. Aplicar dedupe e mapping para Demand no banco.
- **Aceite verificável:** Mensagem repetida atualiza evento sem duplicar demanda.
- **Validação / evidência mínima:** pytest tests/unit/test_intake_normalization.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-036 — Cliente GitHub read-only / PAT e App adapter

- **Responsável (persona):** Integrations; **lane:** `integration`; **risco:** high.
- **DependsOn:** `FAC-004`, `FAC-035`.
- **Arquivos/módulos previstos:** `packages/integrations/src/integrations/github.py`.
- **Passos de implementação:**
  1. Implementar autenticação fine-grained PAT ou GitHub App com interface comum.
  2. Ler metadata/issues/comments com paginação e backoff.
  3. Verificar escopo fixo repo owner/name e log sem token.
- **Aceite verificável:** Nunca consulta repo externo por parâmetros arbitrários de Issue.
- **Validação / evidência mínima:** pytest tests/integration/test_github_client_mock.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-037 — Polling GitHub com cursores e reconciliação

- **Responsável (persona):** Integrations; **lane:** `integration`; **risco:** normal.
- **DependsOn:** `FAC-035`, `FAC-036`, `FAC-025`.
- **Arquivos/módulos previstos:** `workers/src/factory_workers/github_poll.py`.
- **Passos de implementação:**
  1. Persistir watermark e paginação, com overlap para alterações tardias.
  2. Importar issues abertas/atualizadas com idempotência.
  3. Implementar sync-now seguro e backoff para rate limit.
- **Aceite verificável:** PC desligado não perde issues; reexecução não duplica.
- **Validação / evidência mínima:** pytest tests/integration/test_github_poll_recovery.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-038 — Discovery de demanda com evidências rastreáveis

- **Responsável (persona):** Analyst; **lane:** `product`; **risco:** normal.
- **DependsOn:** `FAC-035`, `FAC-026`.
- **Arquivos/módulos previstos:** `packages/context-engine/src/context_engine/discovery.py; specs/demands/`.
- **Passos de implementação:**
  1. Analisar texto da demanda e mapear arquivos/código em SHA conhecido.
  2. Distinguir VERIFIED/INFERRED/UNKNOWN/CONFLICT.
  3. Gerar perguntas curtas ao humano somente em ambiguidades relevantes.
- **Aceite verificável:** Nenhuma regra de negócio inventada vira aceitação sem confirmação.
- **Validação / evidência mínima:** pytest tests/fixtures/discovery/test_evidence_grounding.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-039 — Refinamento progressivo e versionamento

- **Responsável (persona):** Analyst/Planner; **lane:** `product`; **risco:** normal.
- **DependsOn:** `FAC-038`, `FAC-032`.
- **Arquivos/módulos previstos:** `packages/task-engine/src/task_engine/refinement.py; specs/demands/*/requirements.md`.
- **Passos de implementação:**
  1. Gerar critérios EARS específicos e cenários positivos/negativos.
  2. Congelar versão aprovada e registrar comentários do operador.
  3. Propor complementos de escopo sem alterar versões já assinadas.
- **Aceite verificável:** Spec aprovado é imutável; follow-up mantém history.
- **Validação / evidência mínima:** pytest tests/unit/test_requirement_revision.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-040 — Preparar Telegram long polling opcional

- **Responsável (persona):** Integrations; **lane:** `integration`; **risco:** high.
- **DependsOn:** `FAC-035`, `FAC-004`.
- **Arquivos/módulos previstos:** `packages/integrations/src/integrations/telegram.py`.
- **Passos de implementação:**
  1. Ler updates long polling sem URL pública.
  2. Validar bot, chat e user allowlist e mapear mensagens a Issue.
  3. Persistir offset após processamento e rejeitar usuários não autorizados.
- **Aceite verificável:** Integração habilitável por feature flag sem interferir no manual intake.
- **Validação / evidência mínima:** pytest tests/integration/test_telegram_poll_fake.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P06 — Context Engine, personas, skills e orçamento (P0)

**Objetivo:** Entregar o menor contexto útil por perfil, com origem e limites explícitos.

**Gate de saída da fase:** Skill router e context pack determinísticos economizam tokens sem omitir política.

**Pacotes de execução paralela:** ai: FAC-041, FAC-042, FAC-043, FAC-044, platform: FAC-045, qa: FAC-046. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-041 — Manifests tipados das seis personas

- **Responsável (persona):** AI/Architect; **lane:** `ai`; **risco:** normal.
- **DependsOn:** `FAC-038`, `FAC-039`.
- **Arquivos/módulos previstos:** `agents/manifests/{analyst,planner,backend,frontend,qa,reviewer}.yaml`.
- **Passos de implementação:**
  1. Criar goals, scope, tools, forbidden, escalation e rubric_id por perfil.
  2. Validar manifests por Pydantic/schema.
  3. Declarar limites de modelo, tool calls e contexto sem embutir secrets.
- **Aceite verificável:** Todo agente tem contrato, ferramentas permitidas e eval correspondente.
- **Validação / evidência mínima:** pytest tests/unit/test_agent_manifests.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-042 — Registry de skills local curado

- **Responsável (persona):** AI; **lane:** `ai`; **risco:** normal.
- **DependsOn:** `FAC-041`.
- **Arquivos/módulos previstos:** `agents/skills/registry.yaml; packages/context-engine/src/context_engine/skill_registry.py`.
- **Passos de implementação:**
  1. Catalogar skills com id/versão/gatilhos/peso/arquivo.
  2. Avaliar licenças e copiar apenas conteúdo permitido.
  3. Registrar hash e impedir carregamento arbitrário de skill da Issue.
- **Aceite verificável:** Registry determinístico, assinado/versionado por hash.
- **Validação / evidência mínima:** pytest tests/unit/test_skill_registry.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-043 — Router 0–2 skills por intenção

- **Responsável (persona):** AI; **lane:** `ai`; **risco:** normal.
- **DependsOn:** `FAC-041`, `FAC-042`.
- **Arquivos/módulos previstos:** `packages/context-engine/src/context_engine/router.py`.
- **Passos de implementação:**
  1. Mapear type/role/paths a no máximo workflow+especialidade.
  2. Retornar zero skills em pergunta simples.
  3. Rejeitar prompt injection que tente ativar skills privilegiadas.
- **Aceite verificável:** Pergunta trivial não carrega 30 schemas nem skills.
- **Validação / evidência mínima:** pytest tests/unit/test_skill_router.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-044 — Construir Context Pack progressive disclosure

- **Responsável (persona):** AI/Backend; **lane:** `ai`; **risco:** normal.
- **DependsOn:** `FAC-038`, `FAC-041`, `FAC-043`.
- **Arquivos/módulos previstos:** `packages/context-engine/src/context_engine/pack.py`.
- **Passos de implementação:**
  1. Gerar L0 task+aceites, L1 skills, L2 snippets por SHA e L3 artifacts sob demanda.
  2. Limitar tokens por papel e anexar fontes verificáveis.
  3. Excluir dados pessoais, segredos e código fora do escopo autorizado.
- **Aceite verificável:** Pack reproduzível por hash com estimativa token e escopo correto.
- **Validação / evidência mínima:** pytest tests/unit/test_context_pack_budget.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-045 — Compactação e recuperação de tool output

- **Responsável (persona):** Platform; **lane:** `platform`; **risco:** normal.
- **DependsOn:** `FAC-044`, `FAC-006`.
- **Arquivos/módulos previstos:** `packages/context-engine/src/context_engine/compress.py`.
- **Passos de implementação:**
  1. Persistir log integral local com SHA e TTL.
  2. Responder ao LLM apenas resumo JSON 0/1/2 e contagens.
  3. Permitir recuperação paginada por artifact_ref e negar caminhos inseguros.
- **Aceite verificável:** Falha de 10K linhas vira 1 JSON e acesso seletivo auditado.
- **Validação / evidência mínima:** pytest tests/unit/test_log_compaction.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-046 — Evals de contexto, hallucination e segurança

- **Responsável (persona):** QA/AI; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-043`, `FAC-044`, `FAC-045`.
- **Arquivos/módulos previstos:** `evals/fixtures/context/; tests/security/`.
- **Passos de implementação:**
  1. Montar fixtures de alta entropia e prompt injection em Issues.
  2. Medir precisão do arquivo escolhido, leakage, budget e skill relevance.
  3. Criar regressão e relatório por versão do router.
- **Aceite verificável:** Mudanças no router precisam superar baseline ou são rejeitadas.
- **Validação / evidência mínima:** pytest tests/fixtures/context; python scripts/validate_checks.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P07 — OpenBot: agentes descentralizados e conversa por card (P0)

**Objetivo:** Permitir chat direto com especialista e colaboração agente-agente sem passar por fluxo rígido.

**Gate de saída da fase:** @qa em ISSUE existente responde com contexto e, se necessário, gera TaskProposal sem execução livre.

**Pacotes de execução paralela:** ai: FAC-047, FAC-050, backend: FAC-048, FAC-049, security: FAC-051, frontend: FAC-052, qa: FAC-053. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-047 — Fixar e executar OpenBot upstream local

- **Responsável (persona):** AI/Platform; **lane:** `ai`; **risco:** high.
- **DependsOn:** `FAC-005`, `FAC-041`.
- **Arquivos/módulos previstos:** `infra/compose/openbot.yml; docs/spikes/openbot.md`.
- **Passos de implementação:**
  1. Fixar commit/tag e leitura do modelo de dados REST/actor.
  2. Configurar Ollama local e OpenBot API key própria em ambiente separado.
  3. Executar smoke de health, conversation e credenciais sem expor porta à rede.
- **Aceite verificável:** Versão e endpoints reais testados; run_shell inseguro desativado.
- **Validação / evidência mínima:** python scripts/validate_env.py --mode live --require openbot; contrato smoke; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-048 — Implementar OpenBot Adapter substituível

- **Responsável (persona):** Backend/AI; **lane:** `backend`; **risco:** normal.
- **DependsOn:** `FAC-047`, `FAC-028`.
- **Arquivos/módulos previstos:** `packages/agent-runtime/src/agent_runtime/openbot_adapter.py`.
- **Passos de implementação:**
  1. Definir interface create/find thread, send message, poll events, cancel.
  2. Mapear IDs externos em entidade ConversationBinding e traduzir erros.
  3. Testar contra FakeOpenBot e versão real fixada.
- **Aceite verificável:** API interna não depende de payloads específicos upstream.
- **Validação / evidência mínima:** pytest tests/contracts/test_openbot_adapter.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-049 — Vincular conversa a Issue/card e snapshots

- **Responsável (persona):** Backend; **lane:** `backend`; **risco:** normal.
- **DependsOn:** `FAC-048`, `FAC-038`.
- **Arquivos/módulos previstos:** `packages/context-engine/src/context_engine/binding.py`.
- **Passos de implementação:**
  1. Resolver referências ISSUE-42/TASK-xx por ID real.
  2. Salvar thread, participantes, SHA e policy no banco.
  3. Recuperar contexto atualizado sem confundir cards distintos.
- **Aceite verificável:** Dois cards na mesma persona nunca misturam requisitos ou dados.
- **Validação / evidência mínima:** pytest tests/integration/test_thread_bindings.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-050 — Roteamento de intenção em conversas

- **Responsável (persona):** AI; **lane:** `ai`; **risco:** normal.
- **DependsOn:** `FAC-048`, `FAC-049`, `FAC-043`.
- **Arquivos/módulos previstos:** `packages/agent-runtime/src/agent_runtime/intent_router.py`.
- **Passos de implementação:**
  1. Classificar ask/read/propose/write usando regras e validação tipada.
  2. Responder pergunta simples diretamente sem LangGraph.
  3. Converter ação de mudança em TaskProposal não executável.
- **Aceite verificável:** Pergunta sobre teste não dispara build nem cria branch.
- **Validação / evidência mínima:** pytest tests/unit/test_chat_intent_routing.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-051 — Tool Gateway de leitura e propostas

- **Responsável (persona):** Security/Backend; **lane:** `security`; **risco:** high.
- **DependsOn:** `FAC-049`, `FAC-050`, `FAC-032`.
- **Arquivos/módulos previstos:** `packages/agent-runtime/src/agent_runtime/tool_gateway.py`.
- **Passos de implementação:**
  1. Expor get_issue_context, get_task_status, search_allowed_code, propose_task.
  2. Verificar authorization policy server-side, quota, rate limits e redaction.
  3. Negar write/shell/http arbitrários a personas conversacionais.
- **Aceite verificável:** OpenBot não tem caminho direto para ler .env ou escrever repo.
- **Validação / evidência mínima:** pytest tests/security/test_tool_gateway_denied.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-052 — Chat de agentes no React por contexto

- **Responsável (persona):** Frontend; **lane:** `frontend`; **risco:** normal.
- **DependsOn:** `FAC-031`, `FAC-048`, `FAC-049`.
- **Arquivos/módulos previstos:** `apps/factory-web/src/features/agents-chat/`.
- **Passos de implementação:**
  1. Criar seletor de persona, Issue binding, mensagens e anexos locais.
  2. Diferenciar resposta simples, proposta e ação pendente de aprovação.
  3. Mostrar links de evidência e estado da proposta em tempo real.
- **Aceite verificável:** Operador conversa com @qa no card e acompanha TaskProposal.
- **Validação / evidência mínima:** Playwright tests/e2e/test_direct_agent_chat.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-053 — Limites de loops e contratos agente-agente

- **Responsável (persona):** QA/AI; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-048`, `FAC-051`.
- **Arquivos/módulos previstos:** `tests/agents/test_collaboration_limits.py; agents/policies/`.
- **Passos de implementação:**
  1. Testar máximo de hops, máximo de chamadas e resposta à falha.
  2. Impedir agente externo que solicite execução fora de policy.
  3. Avaliar divergência de contexto e repetição de mensagens.
- **Aceite verificável:** Nenhuma conversa entra em loop ou executa alteração por menção isolada.
- **Validação / evidência mínima:** pytest tests/agents/test_collaboration_limits.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P08 — LangGraph: workflows duráveis, subflows e retomada (P0)

**Objetivo:** Orquestrar tarefas autorizadas com checkpoints persistentes e HITL, sem prender conversas diretas.

**Gate de saída da fase:** Workflows pausam/reiniciam/retomam sem duplicar ações e resolvem DAG de dependências.

**Pacotes de execução paralela:** ai: FAC-054, FAC-055, backend: FAC-056, security: FAC-057, platform: FAC-058, FAC-059, qa: FAC-060. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-054 — Fixar LangGraph e checkpointer durável

- **Responsável (persona):** AI/Platform; **lane:** `ai`; **risco:** normal.
- **DependsOn:** `FAC-005`, `FAC-024`.
- **Arquivos/módulos previstos:** `packages/agent-runtime/src/agent_runtime/langgraph_adapter.py; docs/spikes/langgraph.md`.
- **Passos de implementação:**
  1. Configurar grafo com nodes typed e checkpointer Postgres.
  2. Definir mapping run_id/thread_id e versionamento do graph.
  3. Provar restart total do processo com task aguardando humano.
- **Aceite verificável:** Não usar MemorySaver em processo para persistência pós-restart.
- **Validação / evidência mínima:** pytest tests/integration/test_langgraph_durable_restart.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-055 — Criar grafo padrão de task

- **Responsável (persona):** AI/Backend; **lane:** `ai`; **risco:** normal.
- **DependsOn:** `FAC-054`, `FAC-023`.
- **Arquivos/módulos previstos:** `packages/agent-runtime/src/agent_runtime/workflows/task_graph.py`.
- **Passos de implementação:**
  1. Modelar preflight -> policy -> context -> execute -> verify -> eval -> approval.
  2. Declarar rotas fail/retry/blocked/compensation e outputs tipados.
  3. Registrar progress em Task Engine via eventos idempotentes.
- **Aceite verificável:** Grafo nunca marca done após check com exit 1 ou 2.
- **Validação / evidência mínima:** pytest tests/unit/test_graph_transitions.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-056 — Implementar TaskProposal -> task -> subworkflow

- **Responsável (persona):** Backend; **lane:** `backend`; **risco:** normal.
- **DependsOn:** `FAC-050`, `FAC-055`, `FAC-025`.
- **Arquivos/módulos previstos:** `packages/agent-runtime/src/agent_runtime/workflows/proposal_graph.py`.
- **Passos de implementação:**
  1. Validar nova atividade com deps/escopo, version e risco.
  2. Solicitar aprovação se impactar requisito ou arquivos protegidos.
  3. Disparar somente grafo do trabalho complementar autorizado.
- **Aceite verificável:** ISSUE concluída recebe follow-up QA sem recomeçar discovery inteiro.
- **Validação / evidência mínima:** pytest tests/integration/test_proposal_subworkflow.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-057 — Implementar nó de pausa HITL e resume

- **Responsável (persona):** Backend/Security; **lane:** `security`; **risco:** high.
- **DependsOn:** `FAC-032`, `FAC-054`, `FAC-055`.
- **Arquivos/módulos previstos:** `packages/agent-runtime/src/agent_runtime/workflows/hitl.py`.
- **Passos de implementação:**
  1. Usar interrupt/resume com ApprovalRequest versionado.
  2. Exigir identidade do operador e expected_version no callback.
  3. Suportar reject e changes-requested com continuidade definida.
- **Aceite verificável:** Humano continua sendo autoridade e restart mantém pause.
- **Validação / evidência mínima:** pytest tests/integration/test_human_interrupt_resume.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-058 — Retries, DLQ e reconciliação periódica

- **Responsável (persona):** Platform; **lane:** `platform`; **risco:** high.
- **DependsOn:** `FAC-024`, `FAC-025`, `FAC-055`.
- **Arquivos/módulos previstos:** `workers/src/factory_workers/{reconciler,retries}.py`.
- **Passos de implementação:**
  1. Distinguir falhas LLM, dados inválidos, infraestrutura e política.
  2. Implementar backoff com limites, DLQ e recovery de leases vencidos.
  3. Evitar reexecutar side effects já confirmados.
- **Aceite verificável:** Falha Ollama causa fila/retry, não repetição de commit/PR.
- **Validação / evidência mínima:** pytest tests/integration/test_recovery_idempotency.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-059 — Scheduler concorrente com limite GPU

- **Responsável (persona):** Platform/AI; **lane:** `platform`; **risco:** normal.
- **DependsOn:** `FAC-024`, `FAC-055`.
- **Arquivos/módulos previstos:** `packages/task-engine/src/task_engine/scheduler.py; packages/agent-runtime/src/agent_runtime/llm_queue.py`.
- **Passos de implementação:**
  1. Permitir paralelismo entre tasks independentes.
  2. Serializar chamadas pesadas Ollama inicialmente e medir fila.
  3. Definir locks por path e anti-starvation por prioridade.
- **Aceite verificável:** Duas tasks paralelas não obrigam duas inferências simultâneas em 8GB VRAM.
- **Validação / evidência mínima:** pytest tests/integration/test_scheduler_concurrency.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-060 — Testar graph runner com fake model/tools

- **Responsável (persona):** QA; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-055`, `FAC-056`, `FAC-057`, `FAC-058`, `FAC-059`.
- **Arquivos/módulos previstos:** `tests/workflows/fixtures/`.
- **Passos de implementação:**
  1. Injetar FakeLLM e FakeTools determinísticos.
  2. Testar follow-up, rejeição humana e 0/1/2.
  3. Fazer fault injection de killed process, duplicate events, late lease owner.
- **Aceite verificável:** Workflow passa sem network, Ollama e nenhum cloud token.
- **Validação / evidência mínima:** pytest tests/workflows -q; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P09 — Git worktree, sandbox e execução de código (P0)

**Objetivo:** Permitir código real proposto por agentes sem tocar diretamente em main ou expor secrets.

**Gate de saída da fase:** Duas tasks isoladas geram patches auditáveis; arquivos protegidos rejeitados; integração testada.

**Pacotes de execução paralela:** platform: FAC-061, FAC-065, security: FAC-062, backend: FAC-063, qa: FAC-064, FAC-066, integration: FAC-067. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-061 — Criar worktree seguro por run

- **Responsável (persona):** Platform; **lane:** `platform`; **risco:** high.
- **DependsOn:** `FAC-020`, `FAC-024`.
- **Arquivos/módulos previstos:** `packages/agent-runtime/src/agent_runtime/worktrees.py`.
- **Passos de implementação:**
  1. Criar branch e worktree por task/attempt em .runtime.
  2. Registrar branch, SHA e owner do workspace.
  3. Validar cleanup somente quando nenhum run ativo usa caminho.
- **Aceite verificável:** Sem worktree compartilhado nem edição direta de main.
- **Validação / evidência mínima:** pytest tests/integration/test_worktree_lifecycle.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-062 — Sandbox com perfis de CPU/RAM/rede/FS

- **Responsável (persona):** Security/Platform; **lane:** `security`; **risco:** high.
- **DependsOn:** `FAC-061`, `FAC-051`.
- **Arquivos/módulos previstos:** `infra/compose/runner.yml; packages/agent-runtime/src/agent_runtime/sandbox.py`.
- **Passos de implementação:**
  1. Criar executor limitado em usuário não privilegiado e FS com allowlist.
  2. Bloquear docker.sock, .env, home, network por padrão e comandos perigosos.
  3. Aplicar timeouts, quotas, redaction e desmontagem de volumes.
- **Aceite verificável:** Tentativa de ler .env/host path falha sem vazar dados.
- **Validação / evidência mínima:** pytest tests/security/test_sandbox_escape_guards.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-063 — Implementer com patch validado

- **Responsável (persona):** Backend/AI; **lane:** `backend`; **risco:** high.
- **DependsOn:** `FAC-062`, `FAC-044`, `FAC-055`.
- **Arquivos/módulos previstos:** `packages/agent-runtime/src/agent_runtime/implementer.py`.
- **Passos de implementação:**
  1. Consumir context pack e proposta formal, gerar patch para escopo autorizado.
  2. Validar diff, paths, symlinks e no-secret antes de gravar.
  3. Salvar hash, commit local e logs compactos.
- **Aceite verificável:** Patch só altera arquivos permitidos e é reproduzível no SHA base.
- **Validação / evidência mínima:** pytest tests/integration/test_patch_apply_scopes.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-064 — Executar checks por tarefa em sandbox

- **Responsável (persona):** QA/Platform; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-063`, `FAC-055`.
- **Arquivos/módulos previstos:** `packages/quality-gates/src/quality_gates/runner.py`.
- **Passos de implementação:**
  1. Escolher suíte por files touched/tipo de task.
  2. Invocar scripts com timeouts e capturar stdout JSON + artifact.
  3. Retornar categoria check fail vs infra fail e pedir correção limitada.
- **Aceite verificável:** Gates falhos impedem avanço, erro 2 não é tratado como bug de código.
- **Validação / evidência mínima:** pytest tests/unit/test_gate_runner.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-065 — Integrar branches sem conflito e retestar

- **Responsável (persona):** Platform; **lane:** `platform`; **risco:** high.
- **DependsOn:** `FAC-061`, `FAC-063`, `FAC-064`.
- **Arquivos/módulos previstos:** `packages/agent-runtime/src/agent_runtime/integration.py`.
- **Passos de implementação:**
  1. Reservar branch de integração local com base consistente.
  2. Aplicar commits validados sequencialmente, detectar conflito de arquivo/semântico.
  3. Executar testes integrados e reabrir tasks de resolução quando falhar.
- **Aceite verificável:** Merge de tasks paralelas não passa sem tests/regressão.
- **Validação / evidência mínima:** pytest tests/integration/test_parallel_patch_integration.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-066 — Reviewer independente com evidências

- **Responsável (persona):** Reviewer; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-065`, `FAC-064`.
- **Arquivos/módulos previstos:** `agents/manifests/reviewer.yaml; packages/eval-engine/src/eval_engine/review.py`.
- **Passos de implementação:**
  1. Fornecer diff, requisitos e evidências sem esconder risco.
  2. Inspecionar escopo, segurança, migrations e testes.
  3. Registrar review findings com severidade/citações e sem escrever patch sozinho.
- **Aceite verificável:** Reviewer tem prompt/modelo e rubric próprios e pode reprovar task.
- **Validação / evidência mínima:** pytest evals/fixtures/reviewer/; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-067 — Preparar publicação GitHub opcional por HITL

- **Responsável (persona):** Integrations; **lane:** `integration`; **risco:** high.
- **DependsOn:** `FAC-036`, `FAC-032`, `FAC-065`, `FAC-066`.
- **Arquivos/módulos previstos:** `packages/integrations/src/integrations/github_publisher.py`.
- **Passos de implementação:**
  1. Validar autorização humana para push e create PR separadamente.
  2. Criar branch remota e PR apenas para repo fixo com descrição/aceites/checks.
  3. Não oferecer merge automático ou workflows remotos no MVP.
- **Aceite verificável:** Sem autorização nenhum push remoto ocorre; PR inclui evidências redigidas.
- **Validação / evidência mínima:** pytest tests/contracts/test_github_publish_fake.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P10 — Quality gates locais, scripts compactos e segurança (P0)

**Objetivo:** Gerar evidências reprodutíveis sem CI externo, com saída mínima para agentes.

**Gate de saída da fase:** Todos os gates têm saída 0/1/2; falhas de código vs infra distinguidas.

**Pacotes de execução paralela:** platform: FAC-068, qa: FAC-069, FAC-071, FAC-073, FAC-074, frontend: FAC-070, security: FAC-072. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-068 — Criar contrato único de validação JSON

- **Responsável (persona):** QA/Platform; **lane:** `platform`; **risco:** normal.
- **DependsOn:** `FAC-006`, `FAC-064`.
- **Arquivos/módulos previstos:** `packages/quality-gates/src/quality_gates/schema.py; scripts/validate_checks.py`.
- **Passos de implementação:**
  1. Definir JSON schema com check/ok/status/metrics/artifact/errors.
  2. Envolver ferramentas verbosas em wrappers que capturam logs em arquivos.
  3. Cobrir schema inválido, timeout, command missing e saída > limite.
- **Aceite verificável:** Runner consome uma linha JSON e não precisa parsear log livre.
- **Validação / evidência mínima:** pytest tests/unit/test_quality_contract.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-069 — Lint, typecheck e unit tests Python

- **Responsável (persona):** QA; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-068`, `FAC-015`.
- **Arquivos/módulos previstos:** `scripts/quality_python.py; pyproject.toml`.
- **Passos de implementação:**
  1. Executar Ruff, mypy e pytest com flags e targets explícitos.
  2. Capturar contagens reais, cobertura opcional e exit por etapa.
  3. Guardar artefatos compactados e SHA da task.
- **Aceite verificável:** Mudanças Python não avançam com lint/typecheck/unit vermelhos.
- **Validação / evidência mínima:** python scripts/quality_python.py --json; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-070 — Testes React, TypeScript e build

- **Responsável (persona):** Frontend/QA; **lane:** `frontend`; **risco:** normal.
- **DependsOn:** `FAC-068`, `FAC-017`.
- **Arquivos/módulos previstos:** `scripts/quality_web.py; apps/*/web/package.json`.
- **Passos de implementação:**
  1. Executar ESLint, tsc, Vitest e build por aplicação afetada.
  2. Emitir métricas sintéticas apenas com marcadores de mock.
  3. Normalizar erros e relatório com artefatos.
- **Aceite verificável:** Frontend passa sem erros de tipagem e build com config real.
- **Validação / evidência mínima:** python scripts/quality_web.py --json; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-071 — Integração e E2E Playwright local

- **Responsável (persona):** QA; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-018`, `FAC-019`, `FAC-064`.
- **Arquivos/módulos previstos:** `tests/e2e/; infra/compose/base.yml`.
- **Passos de implementação:**
  1. Subir dependências isoladas e fazer migrations em DB de teste.
  2. Rodar CRUD, chat fake, HITL e board UI.
  3. Persistir traces/screenshots somente em falhas com redaction.
- **Aceite verificável:** Smoke local reproduzível sem GitHub Actions/LLM real.
- **Validação / evidência mínima:** python scripts/quality_e2e.py --json; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-072 — Scanners locais de segurança e dependências

- **Responsável (persona):** Security; **lane:** `security`; **risco:** high.
- **DependsOn:** `FAC-068`, `FAC-069`, `FAC-070`.
- **Arquivos/módulos previstos:** `scripts/quality_security.py; agents/policies/`.
- **Passos de implementação:**
  1. Integrar Bandit, Semgrep, Gitleaks, pip-audit, pnpm audit/Trivy gradualmente.
  2. Definir policies de severidade e suppressions com expiração.
  3. Produzir contagens e prova das versões usadas.
- **Aceite verificável:** Critical/high conforme policy bloqueia; suppressions não são adicionadas pelo agente.
- **Validação / evidência mínima:** python scripts/quality_security.py --json; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-073 — Quality aggregate e summaries para agentes

- **Responsável (persona):** QA/Platform; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-068`, `FAC-069`, `FAC-070`, `FAC-071`, `FAC-072`.
- **Arquivos/módulos previstos:** `packages/quality-gates/src/quality_gates/aggregate.py`.
- **Passos de implementação:**
  1. Unificar outputs 0/1/2 de todas as suítes e atrelá-los ao run.
  2. Bloquear status PASS se gate obrigatório ausente/skipped não justificado.
  3. Renderizar primeira falha, contagens e artifact links.
- **Aceite verificável:** Nenhum score LLM sobrepõe gate determinístico vermelho.
- **Validação / evidência mínima:** pytest tests/unit/test_gate_aggregation.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-074 — Perf/DAST e Sonar local opcionais

- **Responsável (persona):** QA/Security; **lane:** `qa`; **risco:** high.
- **DependsOn:** `FAC-073`.
- **Arquivos/módulos previstos:** `infra/compose/quality.yml; scripts/quality_extended.py`.
- **Passos de implementação:**
  1. Adicionar perf smoke Locust, OWASP ZAP baseline e Sonar Community com flag.
  2. Isolar scans agressivos e reservar CPU/RAM da máquina.
  3. Não bloquear MVP sem ferramenta opt-in, mas gerar aviso explícito.
- **Aceite verificável:** Perfil extendido roda quando habilitado, com métricas e sem dependência cloud.
- **Validação / evidência mínima:** quality_extended.py --json em perfil de teste; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P11 — Agent Evals, Judge, feedback e evolução de prompts (P0)

**Objetivo:** Medir confiabilidade por persona e qualidade dos judges com referência humana.

**Gate de saída da fase:** Baseline de eval reprodutível, candidato não promovido automaticamente.

**Pacotes de execução paralela:** ai: FAC-075, FAC-077, FAC-079, qa: FAC-076, frontend: FAC-078, security: FAC-080. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-075 — Definir eval schema e métricas por perfil

- **Responsável (persona):** AI/QA; **lane:** `ai`; **risco:** normal.
- **DependsOn:** `FAC-041`, `FAC-073`.
- **Arquivos/módulos previstos:** `packages/eval-engine/src/eval_engine/{schema,metrics}.py; evals/rubrics/`.
- **Passos de implementação:**
  1. Formalizar métricas por persona, contagens, latência, tokens e custos.
  2. Salvar baseline por modelo/prompt/context/skill hash.
  3. Implementar avaliadores objetivos e schema com evidence refs.
- **Aceite verificável:** Scorecards não atribuem nota subjetiva onde há teste determinístico.
- **Validação / evidência mínima:** pytest tests/unit/test_eval_metrics.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-076 — Datasets de casos dev/regression/holdout

- **Responsável (persona):** QA; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-075`, `FAC-020`.
- **Arquivos/módulos previstos:** `evals/{fixtures,regression,holdout}/`.
- **Passos de implementação:**
  1. Criar casos CPF, telefone, migração, security finding, ruim/bom planner.
  2. Rotular veredicto humano e evidências, sem PII real.
  3. Separar holdout e congelar hashes de versões.
- **Aceite verificável:** Casos têm gabarito e não são usados em prompt de produção.
- **Validação / evidência mínima:** pytest evals/fixtures; audit dataset hashes; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-077 — LLM-as-a-Judge com schema e calibração

- **Responsável (persona):** AI; **lane:** `ai`; **risco:** normal.
- **DependsOn:** `FAC-075`, `FAC-076`, `FAC-044`.
- **Arquivos/módulos previstos:** `packages/eval-engine/src/eval_engine/judge.py; evals/rubrics/`.
- **Passos de implementação:**
  1. Implementar juiz local via Ollama com rubrica pointwise/pairwise.
  2. Validar JSON Pydantic, evidências e escalar para humano em dúvida.
  3. Calibrar discordância/falso positivo/recall no dataset rotulado.
- **Aceite verificável:** Juiz não julga a própria resposta e jamais muda approval/gate automaticamente.
- **Validação / evidência mínima:** pytest tests/ai/test_judge_schema.py + benchmark calibração; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-078 — Feedback humano estruturado em runs

- **Responsável (persona):** Backend/Frontend; **lane:** `frontend`; **risco:** normal.
- **DependsOn:** `FAC-032`, `FAC-075`.
- **Arquivos/módulos previstos:** `packages/eval-engine/src/eval_engine/feedback.py; apps/factory-web/src/features/evals/`.
- **Passos de implementação:**
  1. Coletar aprovação/rejeição, erro categorizado, comentário e evidência.
  2. Vincular a run, prompt, modelo, task e requirements version.
  3. Gerar agregações de first-pass/rework e tendências.
- **Aceite verificável:** Feedback não pode ser falsificado por agente avaliado.
- **Validação / evidência mínima:** pytest tests/security/test_eval_feedback_permissions.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-079 — Experimento de prompts baseline/candidato

- **Responsável (persona):** AI; **lane:** `ai`; **risco:** normal.
- **DependsOn:** `FAC-076`, `FAC-077`, `FAC-078`.
- **Arquivos/módulos previstos:** `packages/eval-engine/src/eval_engine/experiments.py; agents/prompts/`.
- **Passos de implementação:**
  1. Rodar mesmas fixtures/seeds/budgets nos candidatos e baseline.
  2. Calcular deltas, regressões críticas, variância e custo por task aceita.
  3. Produzir diff de prompt e relatório compacto com incertezas.
- **Aceite verificável:** Sem evidência de melhora não há promoção de prompt.
- **Validação / evidência mínima:** pytest tests/ai/test_prompt_experiments.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-080 — HITL para promoção e rollback de prompts

- **Responsável (persona):** Security/Frontend; **lane:** `security`; **risco:** high.
- **DependsOn:** `FAC-079`, `FAC-032`.
- **Arquivos/módulos previstos:** `apps/factory-web/src/features/evals/experiments/; agents/prompts/`.
- **Passos de implementação:**
  1. Criar formulário revisão da comparação e decisão humana.
  2. Salvar versão e hash, ativar por flag, fornecer rollback.
  3. Bloquear agent auto-edit de rubrics/datasets e versions ativas.
- **Aceite verificável:** Prompt candidato só vira ativo após aprovação explícita.
- **Validação / evidência mínima:** pytest tests/integration/test_prompt_promotion_hitl.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P12 — Observabilidade local e otimização de recursos (P0)

**Objetivo:** Coletar rastreabilidade e uso GPU/LLM sem depender de LangSmith ou cloud.

**Gate de saída da fase:** Uma task possui traces resumidos correlacionados; falha Phoenix não bloqueia operação.

**Pacotes de execução paralela:** platform: FAC-081, FAC-083, FAC-084, FAC-085, ai: FAC-082, frontend: FAC-086. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-081 — Correlation IDs, logs e masking em todo serviço

- **Responsável (persona):** Platform; **lane:** `platform`; **risco:** high.
- **DependsOn:** `FAC-026`, `FAC-055`, `FAC-073`.
- **Arquivos/módulos previstos:** `packages/observability/src/observability/{logging,redaction}.py`.
- **Passos de implementação:**
  1. Padronizar demand/task/run/thread/trace IDs em logs JSON.
  2. Aplicar secrets redaction e política de retenção.
  3. Guardar logs verbosos localmente e expor somente summaries.
- **Aceite verificável:** Logs não contêm tokens, e uma task pode ser traçada ponta a ponta.
- **Validação / evidência mínima:** pytest tests/security/test_log_redaction.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-082 — Instrumentação Ollama de tokens e latência

- **Responsável (persona):** AI/Platform; **lane:** `ai`; **risco:** normal.
- **DependsOn:** `FAC-081`, `FAC-044`.
- **Arquivos/módulos previstos:** `packages/observability/src/observability/ollama_metrics.py`.
- **Passos de implementação:**
  1. Capturar prompt_eval_count/eval_count/load/eval durations sem conteúdo sensível.
  2. Calcular tokens/s com denominadores válidos.
  3. Agregar por modelo, task, agente e quantização.
- **Aceite verificável:** Dashboard diferencia tempo de espera, carregamento e geração.
- **Validação / evidência mínima:** pytest tests/unit/test_ollama_metrics.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-083 — Coleta local NVIDIA/VRAM/energia

- **Responsável (persona):** Platform; **lane:** `platform`; **risco:** normal.
- **DependsOn:** `FAC-082`.
- **Arquivos/módulos previstos:** `scripts/hardware_probe.py; packages/observability/src/observability/gpu.py`.
- **Passos de implementação:**
  1. Criar probe opcional nvidia-smi com timeout.
  2. Ler VRAM, gpu utilization, consumo/temperatura quando suportados.
  3. Emitir JSON compacto e status degradado se GPU indisponível.
- **Aceite verificável:** Observabilidade não bloqueia pipeline por falha de métrica.
- **Validação / evidência mínima:** pytest tests/unit/test_gpu_probe_fake.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-084 — Tracing OpenTelemetry e bridges OpenBot/LangGraph

- **Responsável (persona):** Platform; **lane:** `platform`; **risco:** normal.
- **DependsOn:** `FAC-081`, `FAC-082`, `FAC-055`, `FAC-048`.
- **Arquivos/módulos previstos:** `packages/observability/src/observability/tracing.py`.
- **Passos de implementação:**
  1. Instrumentar FastAPI, nós LangGraph e tool gateway.
  2. Emitir spans OpenBot manualmente via adapter se preciso.
  3. Aplicar sampling e não registrar prompt/raw code por padrão.
- **Aceite verificável:** Traces correlacionam workflow e chamada de modelo sem dados secretos.
- **Validação / evidência mínima:** pytest tests/integration/test_trace_correlation.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-085 — Arize Phoenix self-hosted opcional

- **Responsável (persona):** Platform; **lane:** `platform`; **risco:** normal.
- **DependsOn:** `FAC-084`.
- **Arquivos/módulos previstos:** `infra/compose/observability.yml; docs/observability-runbook.md`.
- **Passos de implementação:**
  1. Configurar Phoenix com volume local e portas 127.0.0.1.
  2. Exportar traces OTel quando flag habilitada.
  3. Implementar fallback silencioso/degradado quando collector cai.
- **Aceite verificável:** Desligar Phoenix não interfere em criação/teste/entrega.
- **Validação / evidência mínima:** docker compose --profile observability config; smoke com collector off; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-086 — Dashboard de métricas e custo-benefício

- **Responsável (persona):** Frontend; **lane:** `frontend`; **risco:** normal.
- **DependsOn:** `FAC-031`, `FAC-075`, `FAC-082`, `FAC-083`.
- **Arquivos/módulos previstos:** `apps/factory-web/src/features/observability/`.
- **Passos de implementação:**
  1. Exibir tokens/task, accepted tasks/hour, GPU, latência, failures e drill-down por artifact.
  2. Mostrar n/d em métricas ausentes sem inventar valores.
  3. Permitir comparar prompts/modelos/agentes por período.
- **Aceite verificável:** Dash separa valores medidos de estimativas e filtros por tarefa.
- **Validação / evidência mínima:** Vitest + Playwright dashboard smoke; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P13 — Demonstrações reais e testes adversariais (P0)

**Objetivo:** Provar o produto funcionando de ponta a ponta antes de expandir integrações.

**Gate de saída da fase:** Matriz UAT assinada por humano com evidência, logs compactos e métricas.

**Pacotes de execução paralela:** qa: FAC-087, FAC-089, FAC-091, backend: FAC-088, security: FAC-090, FAC-092, product: FAC-093. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-087 — Demo 1: Issue bug CPF com reprodução

- **Responsável (persona):** QA/Analyst; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-037`, `FAC-039`, `FAC-060`, `FAC-074`.
- **Arquivos/módulos previstos:** `evals/fixtures/bug-cpf/; specs/demands/demo-cpf/`.
- **Passos de implementação:**
  1. Preparar uma falha CPF sintética em fixture/branch isolada.
  2. Criar demanda e aceite.
  3. Rodar Planner -> Backend -> QA -> review com evidência de regressão.
- **Aceite verificável:** Bug repro antes, teste passa após fix e nenhuma mudança fora do escopo.
- **Validação / evidência mínima:** pytest tests/acceptance/test_bug_cpf_flow.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-088 — Demo 2: telefone fullstack e tarefas paralelas

- **Responsável (persona):** Backend/Frontend; **lane:** `backend`; **risco:** normal.
- **DependsOn:** `FAC-067`, `FAC-066`, `FAC-060`, `FAC-074`.
- **Arquivos/módulos previstos:** `evals/fixtures/feature-phone/; specs/demands/demo-phone/`.
- **Passos de implementação:**
  1. Solicitar telefone, aprovar spec e dividir migration/API/UI/teste.
  2. Executar frontend em paralelo à trilha DB/Backend.
  3. Integrar patches, rodar e2e e solicitar revisão.
- **Aceite verificável:** Campo funciona em API+UI e auditoria registra dependências.
- **Validação / evidência mínima:** pytest tests/acceptance/test_phone_feature.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-089 — Demo 3: conversa direta QA pós-conclusão

- **Responsável (persona):** QA/AI; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-052`, `FAC-057`, `FAC-088`.
- **Arquivos/módulos previstos:** `evals/fixtures/followup-qa/; tests/acceptance/`.
- **Passos de implementação:**
  1. Depois de concluir ISSUE telefone, enviar @qa citando novo cenário.
  2. Inspecionar TaskProposal e aprovação de aceites.
  3. Executar somente subworkflow QA e verificar cobertura adicionada.
- **Aceite verificável:** Demanda original mantém histórico e não reexecuta todo discovery.
- **Validação / evidência mínima:** pytest tests/acceptance/test_qa_direct_followup.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-090 — Demo 4: dependência vulnerável/upgrade

- **Responsável (persona):** Security; **lane:** `security`; **risco:** normal.
- **DependsOn:** `FAC-072`, `FAC-060`.
- **Arquivos/módulos previstos:** `evals/fixtures/dependency-update/; tests/acceptance/`.
- **Passos de implementação:**
  1. Injetar lockfile fictício com alerta conhecido.
  2. Criar Issue, validar evidência e atualizar em sandbox.
  3. Rodar scanners/tests e mostrar veto em caso de regressão.
- **Aceite verificável:** Remediação tem evidência objetiva e humano aprova publicação.
- **Validação / evidência mínima:** pytest tests/acceptance/test_security_fix_flow.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-091 — Demo 5: restart, retries, duplicate events

- **Responsável (persona):** Platform/QA; **lane:** `qa`; **risco:** normal.
- **DependsOn:** `FAC-059`, `FAC-060`, `FAC-025`.
- **Arquivos/módulos previstos:** `tests/acceptance/test_restart_recovery.py`.
- **Passos de implementação:**
  1. Interromper worker durante wait_human e após efeito idempotente.
  2. Reiniciar processo, reenviar Issue e validar lease/cursor.
  3. Verificar ausência de patch duplicado e approvals perdidas.
- **Aceite verificável:** A execução retoma corretamente e preserva audit trail.
- **Validação / evidência mínima:** pytest tests/acceptance/test_restart_recovery.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-092 — Red-team e simulações de uso indevido

- **Responsável (persona):** Security; **lane:** `security`; **risco:** high.
- **DependsOn:** `FAC-062`, `FAC-051`, `FAC-080`.
- **Arquivos/módulos previstos:** `tests/security/prompt_injection/`.
- **Passos de implementação:**
  1. Injetar instrução maliciosa em Issue, diff e mensagem de agente externo.
  2. Tentar ler .env/secret, mudar approvals, escapar worktree e ativar ferramenta vetada.
  3. Exigir bloqueio determinístico e rastreabilidade.
- **Aceite verificável:** Nenhum prompt override atravessa Tool Gateway/policies.
- **Validação / evidência mínima:** pytest tests/security -q; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-093 — Aceite humano independente e scorecard final

- **Responsável (persona):** Reviewer/Human; **lane:** `product`; **risco:** normal.
- **DependsOn:** `FAC-088`, `FAC-089`, `FAC-090`, `FAC-091`, `FAC-092`.
- **Arquivos/módulos previstos:** `docs/acceptance-report.md; .runtime/artifacts/uat/`.
- **Passos de implementação:**
  1. Comparar matriz do SPECIFY com resultados e evidências.
  2. Medir latência/tokens/VRAM/rework em execução real.
  3. Registrar lacunas e decisão humana para próxima release.
- **Aceite verificável:** Relatório não diz done se requisito/gate não foi verificado.
- **Validação / evidência mínima:** Checklist UAT assinado pelo operador; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## P14 — Integrações opcionais e hardening pós-MVP (P1/P2)

**Objetivo:** Adicionar capacidades sem arruinar execução local estável.

**Gate de saída da fase:** Cada integração pode ser ligada/desligada isoladamente e possui testes de contrato.

**Pacotes de execução paralela:** integration: FAC-094, FAC-095, security: FAC-096, FAC-097, platform: FAC-098, docs: FAC-099. O scheduler deve conferir dependencies, scopes e leases antes de liberar.

### FAC-094 — GitHub Projects v2 como espelho Kanban

- **Responsável (persona):** Integrations; **lane:** `integration`; **risco:** normal.
- **DependsOn:** `FAC-036`, `FAC-037`, `FAC-093`.
- **Arquivos/módulos previstos:** `packages/integrations/src/integrations/github_projects.py`.
- **Passos de implementação:**
  1. Validar auth específico de Projects pessoal/organização.
  2. Mapear somente Issues reais e campos conhecidos.
  3. Sincronizar mudanças de status com reconciliação sem substituir Task Engine.
- **Aceite verificável:** Problema de Projects não impede Task Engine local.
- **Validação / evidência mínima:** pytest tests/contracts/test_projects_sync_fake.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-095 — Jira Cloud polling opt-in

- **Responsável (persona):** Integrations; **lane:** `integration`; **risco:** normal.
- **DependsOn:** `FAC-035`, `FAC-037`, `FAC-094`.
- **Arquivos/módulos previstos:** `packages/integrations/src/integrations/jira.py`.
- **Passos de implementação:**
  1. Ler Cloud API com token e JQL por projeto.
  2. Persistir cursor e normalização de issue/status.
  3. Testar rate limit, expiração de token e shutdown offline.
- **Aceite verificável:** Jira desligado não requer credencial nem interfere nos demais canais.
- **Validação / evidência mínima:** pytest tests/contracts/test_jira_poll_fake.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-096 — Webhook com túnel apenas se requerido

- **Responsável (persona):** Security/Integrations; **lane:** `security`; **risco:** high.
- **DependsOn:** `FAC-036`, `FAC-037`, `FAC-094`, `FAC-095`.
- **Arquivos/módulos previstos:** `apps/factory-api/src/factory_api/routers/webhooks.py`.
- **Passos de implementação:**
  1. Criar receiver signed com raw-body HMAC para GitHub.
  2. Para Jira Automation validar segredo próprio e rede/proxy conforme contrato.
  3. Implementar replay/idempotência, expiração/rotação e polling fallback.
- **Aceite verificável:** Túnel não expõe admin UI/Ollama e payload inválido é rejeitado.
- **Validação / evidência mínima:** pytest tests/security/test_webhook_signatures.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-097 — Executar atualização local automática de dependências com policy

- **Responsável (persona):** Security/QA; **lane:** `security`; **risco:** normal.
- **DependsOn:** `FAC-072`, `FAC-091`.
- **Arquivos/módulos previstos:** `workers/src/factory_workers/dependency_audit.py`.
- **Passos de implementação:**
  1. Agendar scan local permitido e gerar DemandProposal com evidência.
  2. Distinguir transitive advisories de mudança real de lockfile.
  3. Manter patch/PR dependente de HITL e gates.
- **Aceite verificável:** Scanner pode propor, mas não atualizar automaticamente por ação perigosa.
- **Validação / evidência mínima:** pytest tests/integration/test_dependency_audit.py; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-098 — Backups, retenção e recuperação de ambiente local

- **Responsável (persona):** SRE; **lane:** `platform`; **risco:** normal.
- **DependsOn:** `FAC-094`, `FAC-081`.
- **Arquivos/módulos previstos:** `scripts/{backup,restore,dry_run_restore}.py; docs/backup-runbook.md`.
- **Passos de implementação:**
  1. Documentar backup DB e artefatos com proteção de segredos.
  2. Implementar restore em destino descartável e smoke.
  3. Estabelecer retenção de traces/artifacts e limpeza de worktrees encerradas.
- **Aceite verificável:** Recuperação testada, não apenas script de backup não verificado.
- **Validação / evidência mínima:** restore dry-run + integrity hash + smoke; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

### FAC-099 — Preparar roadmap CI/deploy sem habilitar

- **Responsável (persona):** Architect; **lane:** `docs`; **risco:** normal.
- **DependsOn:** `FAC-094`.
- **Arquivos/módulos previstos:** `docs/roadmap-futuro.md`.
- **Passos de implementação:**
  1. Documentar futuro GitHub Actions, runners confiáveis e Sonar quando houver host.
  2. Registrar riscos de PR não confiável/self-hosted runner.
  3. Manter todos os workflows externos desativados nesta release.
- **Aceite verificável:** Nenhum GitHub Secret, YAML CI obrigatório ou dependência de VPS aparece no caminho crítico.
- **Validação / evidência mínima:** Inspeção git diff .github/workflows + checklist; salvar `exit_code`, JSON resumido, logs quando houver e revisão do agente/humano pertinente.

## Protocolo de handoff para coding agent

Para cada task: 1) emitir `TASK_SELECTED id/depends_on/paths`; 2) avaliar preflight e versões; 3) implementar mudanças limitadas; 4) executar validadores; 5) persistir JSON `{task_id,status,exit_code,metrics,artifacts,changed_files,notes}`; 6) se bloqueada, citar erro de configuração/infra sem inventar sucesso; 7) perguntar humano apenas quando dado decisivo está realmente ausente; 8) não promover prompt nem fazer push/merge sem autorização.

## Metadados de validação do plano

- Fases: **15**.
- Atividades: **99** (`FAC-001` a `FAC-099`).
- Todos os `dependsOn` apontam para IDs anteriores existentes e foram validados programaticamente.
- Paths indicados são referências propostas, não evidência de código existente.
