# Agentic Factory Local v2 — SPECIFY / Escopo do Produto

**Estado:** proposta para implementação; nenhum módulo é presumido como existente. **Prioridade:** PoC local single-repository, single-operator, auditável. **Data-base:** 2026-10-24. **Idioma:** código/contratos/docs técnicos em inglês; interface e conversas podem ser em português.

## 1. Objetivo

Construir uma fábrica de software que **evolua exclusivamente seu próprio monorepo**, inicialmente a aplicação real `customer-registry` (cadastro de usuários). Ela recebe demandas por GitHub Issues, entrada manual ou, depois, Telegram/Jira; entende a necessidade; faz discovery e refinamento progressivos; decompõe em tarefas com dependências; delega a personas especializadas; permite **conversa direta entre usuário e qualquer persona, vinculada a uma Issue/card**; coordena trabalho estruturado com LangGraph; mantém execução e estado sob controle do Task Engine Python; mede qualidade e eficiência com scripts/evals; e solicita aprovação humana antes de ações relevantes. 

**Objetivo verificável:** uma Issue «Adicionar telefone ao cadastro» se transforma em mudanças testadas em FastAPI + React, feitas em branches/worktrees isolados, com evidências por tarefa, proposta de PR e decisão humana; posteriormente é possível mencionar `@qa` sobre a Issue e adicionar somente o teste faltante, sem obrigar nova passagem por todo discovery.

## 2. Invariantes de produto (não negociar no MVP)

1. **Um único repositório e operador.** O repo da fábrica é o próprio alvo das mudanças. Nenhum tenant, white-label, onboarding de repositórios de terceiros ou multi-empresa.
2. **Execução local.** Sem deploy em VPS, sem secrets no GitHub, sem obrigação de pipeline GitHub Actions; testes e qualidade rodam na máquina local. GitHub é fonte opcional de Issues e destino opcional de PR quando autorizado.
3. **Separação de responsabilidades.** OpenBot = conversação/inboxes/delegação; LangGraph = workflow/retomada; Task Engine = autoridade de estado, dependências, autorização, locks e auditoria; LLM = proposta, nunca autoridade de permissão.
4. **Dual mode.** Conversa direta não inicia workflow desnecessário; mutações são formalizadas como TaskProposal -> decisão de política/HITL -> trabalho registrado -> sandbox.
5. **HITL real.** Requisitos ambíguos, alterações de escopo, autorização de publicação, ajustes em políticas, prompts promovidos, merge e mudanças perigosas exigem decisão humana rastreada.
6. **Execução isolada.** Nada de executar texto de Issue em shell privilegiado. Agentes conversacionais não possuem tokens do GitHub, segredo do bot, credenciais Docker ou comandos irrestritos; tarefas de código rodam em sandbox e worktree autorizados.
7. **Observabilidade self-hosted.** PostgreSQL + logging estruturado + métricas do Ollama como base; OpenTelemetry e Arize Phoenix opcionais. Nunca exigir LangSmith, SaaS ou internet para observar execuções locais.
8. **Custo de tokens.** Primeiro validação determinística, saída JSON de uma linha e exit 0/1/2; logs completos em artefatos locais referenciados por IDs, só revelados quando necessários. Skills em progressive disclosure.
9. **Fonte da verdade.** PostgreSQL mantém estados transacionais; documentos Markdown versionam decisões e requisitos; GitHub Issue/Projects é canal e espelho, não engine de execução.
10. **Self-modification guard.** O `customer-registry` é alvo padrão. Alterações em `apps/factory-*`, `packages/task-engine`, `agents/policies`, scripts de segurança e infra da fábrica exigem revisão reforçada e não são autoaplicadas na instância em funcionamento.

## 3. Personas humanas e agênticas

**Humano operador:** abre/seleciona demanda, conversa com qualquer agente, define prioridades, responde questões de produto, aprova propostas/PRs, revisa métricas. **Personas lógicas iniciais:** Analyst/Discovery, Planner/Tech Lead, Backend/Database, Frontend, QA/Security, Reviewer. Escaláveis para SRE, Docs, Dependency Maintainer e Evaluator somente quando justificadas. Personas são configurações, **não** serviços ou modelos sempre carregados.

## 4. Canais, classificação e fronteiras

| Canal | MVP | Contrato de entrada | Fronteira de segurança |
|---|---|---|---|
| UI React/manual | P0 | Texto + opcional Issue ID, anexo local | Autenticação local, sanitização e tamanho máximo |
| GitHub Issues | P0 após credencial | Polling com cursor/paginação; Issues reais | Token somente no conector; sem execução a partir do payload |
| OpenBot thread | P0 após spike de integração | `@qa ISSUE-42 ...`, thread vinculada | Ferramentas read-only, Tool Gateway controlado |
| Telegram | P1 | Long polling, chat/user allowlist | Token secreto, rejeitar usuários não autorizados |
| Jira Cloud | P2 | Polling com JQL/cursor, normalização | API token isolado, não obrigatório para MVP |
| GitHub Projects v2 | P2 | Vista Kanban de Issues; resolução GraphQL quando necessário | Permissões específicas; sem card draft como origem inicial |
| Webhooks externos | P2 | Receiver HMAC/secret + relay/túnel | Não expor API de administração nem Ollama |

**Política offline:** com GitHub/Telegram indisponíveis, o intake manual e a fábrica local continuam funcionando; jobs ficam pendentes para reconciliação.

## 5. Jornadas ponta a ponta

### US-01 — Cadastro inicial operante
Como operador, inicio Docker + frontend/API e cadastro/listo/edito/desativo usuários, com e-mail único, validação e histórico básico, para existir um produto real sujeito a evolução. `DELETE` deve ser decisão explícita (soft delete recomendado) e testes devem cobrir o comportamento.

### US-02 — Issue de bug
Abro `BUG: CPF inválido aceito`. O intake identifica Issue, armazena evidência, Discovery reproduz, humano confirma regra quando ambígua, Planner divide reprodução/fix/teste, Backend altera, QA executa regressão, Reviewer revisa. Um pacote de evidências e branch/PR são preparados somente conforme autorização.

### US-03 — Feature de telefone em paralelo
Issue `FEAT: adicionar telefone`. Analyst estabelece contrato; Planner publica DAG; Database/Backend e Frontend trabalham em worktrees distintos conforme dependências; QA roda testes integrados após integração; humano aprova. A Issue acompanha tarefas e status.

### US-04 — Conversa direta em card concluído
Operador envia `@qa ISSUE-42: faltou testar telefone colado com caracteres especiais`. OpenBot resolve a thread/card; Context Engine recupera requisitos, commit e testes; QA responde ou gera `TaskProposal` complementar; Task Engine verifica contexto, autorização, deps e estado; apenas subworkflow QA é disparado, sem reiniciar planejamento integral. Se comportamento esperado é desconhecido, o humano esclarece antes da implementação.

### US-05 — Remediação de vulnerabilidade/pacotes
Intake recebe `SECURITY: atualizar pacote vulnerável`. Verificador estabelece CVE/versão/lockfile; Planner identifica upgrade e riscos; Backend implementa branch; scanners + testes provam mitigação; reviewer e humano decidem; mudança em arquivos sensíveis possui gate reforçado.

### US-06 — Falha de um agente
Falha de rede/Ollama ou desligamento do PC pausa run com checkpoint e lease expirável. Reativação recupera tarefas com idempotência, evitando duplo commit/delegação; erro de configuração dispara preflight e não consome novos tokens.

### US-07 — Melhoria supervisionada de prompt
Uma execução é reprovada por omitir um cenário; evidência e feedback humanos geram hipótese; prompt candidato é comparado com baseline em fixtures controladas; promoção somente após checks determinísticos, regressão e autorização humana. Versão anterior mantém rollback.

### US-08 — Interface operacional
No React visualizo kanban interno, demandas, tarefas, dependências, agentes online, threads/context binding, aprovações, diffs, resultados dos gates, evals por perfil e traces locais; sem obrigar abrir ferramenta separada para conhecer resultado 0/1.

## 6. Requisitos rastreáveis (SPECIFY IDs)

### Base e produto
- `CORE-001`: monorepo único com `apps/factory-api`, `apps/factory-web`, `apps/customer-registry/{api,web}` e pacotes Python reutilizáveis.
- `CORE-002`: serviço de cadastro funcional com persistência, validações e testes locais.
- `CORE-003`: runtime Python com `uv`, React/Vite/TypeScript/Tailwind/shadcn/ui e Docker Compose perfis opcionais.
- `CORE-004`: `.env` e `.env.example` sem secrets versionados; preflight `local` e `live` por integração com códigos 0/1/2.
- `CORE-005`: funcionamento útil sem GitHub/Telegram/Jira/LLM remoto (modo manual e fake model para tests).
- `CORE-006`: UI responsiva, acessível, com loading/error/empty e confirmação explícita de ações.

### Demanda, colaboração e tarefas
- `INT-001`: criar/consultar demanda manual com fonte e identidade idempotente.
- `INT-002`: sincronizar Issues por polling read-only, cursor e overlap/reconcile.
- `INT-003`: estender intake para Telegram long polling com allowlist (P1).
- `INT-004`: estender intake para Jira Cloud (P2); Projects v2 como exibição/espelho opcional.
- `DISC-001`: discovery cita arquivos/commit e distingue fato, hipótese e dúvida.
- `DISC-002`: refinamento EARS/aceites, congelamento de versão e revisão humana.
- `TASK-001`: demandas -> tarefas pequenas com owner_role, dependencies, path scopes, risk e teste.
- `TASK-002`: DAG válido, estados controlados e readiness calculada de forma determinística.
- `TASK-003`: reservar tarefas com lock/lease e impedir execução duplicada.
- `TASK-004`: TaskProposal aditiva após discovery/revisão, com impacto/versionamento/auditoria.
- `COL-001`: direcionar mensagem diretamente a um agente e vincular thread a Issue/card.
- `COL-002`: conversa sem efeito colateral não entra no workflow; mutação sempre passa pela política.
- `COL-003`: comunicação entre agentes com limite de hops, orçamento e prevenção de loops.
- `COL-004`: novas tarefas surgidas em conversa preservam histórico da Issue concluída.

### Orquestração, ferramentas, contexto e qualidade
- `ORCH-001`: OpenBot como colaboração e LangGraph como execução estruturada, ambos substituíveis por adapters.
- `ORCH-002`: checkpoint de LangGraph, interrupção HITL e retomada idempotente.
- `ORCH-003`: política de concorrência por tarefa, por arquivos e por GPU (8 GB VRAM).
- `EXEC-001`: Git worktree por task/run, branch, allowlist de caminhos, sandbox e inspeção de diff.
- `EXEC-002`: Tool Gateway aplica autorização server-side, timeouts e quotas; sem shell livre aos chats.
- `EXEC-003`: alterações sensíveis e publicações exigem políticas e aprovação; merge é humano.
- `CTX-001`: contexto por demanda, tarefa, perfil, commit, arquivos e fontes citadas.
- `CTX-002`: roteamento 0–2 skills por tarefa; L0-L3 progressivo; não carregar todo o repositório.
- `CTX-003`: compressão reversível somente de logs/tool outputs; nunca apagar evidências críticas.
- `QA-001`: scripts locais de lint/typecheck/testes/integração/E2E/SAST/SCA em JSON compacto.
- `QA-002`: status de gate 0/1/2; não aceitar logs textuais como sinal único.
- `QA-003`: test fixtures de bugs e vulnerabilidades reais/sintéticas e testes de não-regressão.
- `EVAL-001`: métricas específicas por persona + desempenho geral (task success, first pass, rework, latency, tokens).
- `EVAL-002`: Judge opcional independente do executor, calibrado com casos humanos; nunca substitui testes.
- `EVAL-003`: datasets dev/regression/holdout, experiências pareadas, versionamento e feedback.
- `EVAL-004`: promoção de prompts/skils somente por aprovação humana, com rollback.
- `OBS-001`: trace ID correlaciona demanda, task, OpenBot thread, LangGraph run, ferramentas, Ollama e avaliação.
- `OBS-002`: métricas nativas do Ollama/GPU e logs locais; Phoenix self-hosted opcional, não bloqueante.
- `OBS-003`: mascaramento de tokens e dados pessoais; limites de retenção de payloads.
- `HITL-001`: aprovações transacionais para requisitos, escopo, publish e alterações privilegiadas.
- `HITL-002`: rejeição/ajuste com comentário e evidência, retomada durável e prazo não presumido.
- `AUD-001`: audit trail de entrada, plano, decisões, tool calls privilegiados, patch, eval e publicação.
- `AUD-002`: snapshot versionado specs/decisions/acceptance em Markdown, gerado a partir do estado persistido.

## 7. Estados e políticas

**Demand:** `new -> triage -> discovery -> clarification_pending -> refined -> approved -> planned -> executing -> verifying -> human_review -> completed`; exceções `blocked`, `failed`, `cancelled`, `follow_up_required`. Transições precisam de comando válido, versão esperada, ator e razão.

**Task:** `proposed -> ready -> leased -> running -> review -> done`; exceções `blocked`, `retry_wait`, `failed`, `cancelled`. Uma tarefa concluída é imutável; follow-up cria nova task vinculada.

**Run:** `queued -> starting -> running -> waiting_human -> resumed -> succeeded/failed/cancelled`. Idempotência por `{task_id, attempt_number}`; checkpoints externos não substituem transação no banco.

**Policies:** `read` e `analyze` são possíveis com contexto confiável; `create_task` pode gerar proposta sem autorizar execução; `sandbox_write` exige task autorizada; `push_branch/create_pr` exige autorização explícita; `merge`, `deploy`, `edit_secrets`, `edit_policies` nunca são delegados autonomamente no MVP.

## 8. Evals, métricas e gates

| Métrica | Fórmula / evidência | Uso |
|---|---|---|
| Completion rate | tarefas aprovadas / tarefas encerradas | qualidade do fluxo |
| First-pass success | tasks aprovadas no primeiro ciclo / tasks avaliadas | qualidade inicial |
| Rework rate | tarefas que reabriram correção / tarefas entregues | eficiência de prompts/skills |
| Accepted tasks/hour | tasks aprovadas / horas de inferência+execução | custo-benefício real |
| Token efficiency | tokens de entrada+saída por task aprovada | controle de contexto |
| Tool correctness | tool calls válidas / tentativas | robustez de contratos |
| Judge-human agreement | concordância do Judge em dataset rotulado | calibração de Judge |
| Defect recall | falhas conhecidas apontadas / total falhas conhecidas | QA/Reviewer |
| Policy incidents | tentativas de ação proibida | indicador de bloqueio; nunca score substitutivo |

Os scripts emitem **um JSON por execução**, ex. `{"schema":1,"check":"unit","ok":1,"metrics":{"passed":23,"failed":0},"artifact":"runs/42/unit.log"}` com exit 0; reprovação => exit 1; problema de infraestrutura => exit 2. Saída extensa não é enviada a LLM sem necessidade. Métricas e traces não podem conter secretos; resultados de avaliações são imutáveis para o agente avaliado.

## 9. Critérios de sucesso (aceitação independente)

- Cadastro completo funciona em ambiente local, incluindo banco e interface React, com suíte verde e dados de exemplo não sensíveis.
- Uma Issue manual e uma Issue GitHub seguem do intake ao planejamento, passando por pelo menos duas tarefas especializadas com deps e revisão humana.
- O usuário consegue enviar `@qa ISSUE-42 ...`, receber resposta contextual e criar tarefa complementar sem reiniciar todo o fluxo.
- Dois agentes podem trabalhar em tarefas independentes; duas mutações conflitantes do mesmo arquivo não são integradas sem resolução.
- LangGraph pausa e retoma um run após reinício da aplicação; não duplica task, patch nem aprovação.
- Sandbox impede exposição de `.env`, chaves privadas e acesso irrestrito a ações administrativas.
- Preflight distingue credencial inválida de indisponibilidade de serviço; nenhum secret aparece na saída.
- Scripts de qualidade retornam 0/1/2 e métricas objetivas; um erro crítico impede entrega mesmo com Judge positivo.
- Evals por perfil registram versões de prompts/modelos e feedback humano; candidato reprovado não é promovido.
- Nenhum passo exige AWS, LangSmith, GitHub Actions, SaaS de observabilidade ou implantação de servidor remoto.

## 10. Fora de escopo agora

Multi-tenant; white-label; integração com múltiplos repositórios ou clientes; deploy automatizado; merge automático; autoedição do Task Engine/segredos/políticas; comunicação pública irrestrita; execução simultânea de vários modelos de 20B+ em 8 GB VRAM; GitHub Secrets/Actions como requisito; otimização automática de prompt em produção; pipelines externos como fonte de verdade.

## 11. Dependências e sequência

Começar em `P00` preflight e invariantes, `P01` fundação, `P02` cadastro real, `P03` Task Engine, `P04` API/UI básica. O primeiro vertical slice é intake manual -> tarefas -> implementações simuladas -> HITL; só depois acoplar OpenBot e LangGraph reais. GitHub polling antes de Jira. Avaliação de qualidade antes de otimização de prompts. Observabilidade básica antes de Phoenix. Detalhes, responsáveis, paths e verificações em `03-TASKS-POR-FASES.md`.
