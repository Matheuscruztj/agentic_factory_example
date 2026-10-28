# Validação das 99 atividades originais

Data: 2026-10-24. Auditoria técnica, sem implementação.

Antes: 96 done / 3 in_progress. Agora: **47 done de componente / 52 in_progress**; 49 conclusões foram reabertas por lacunas concretas.

`done` preserva o aceite do componente e sua evidência disponível. Não é percentual de produto pronto, certificação live atual ou UAT humano. As evidências específicas e os comandos originalmente previstos constam dos campos `audit` e `original_validation` do [backlog](../../specs/implementation-backlog.json). A suíte atual passou 124 testes, mas as sondagens adicionais reproduziram falhas ausentes dessa cobertura.

`completion_tasks` liga lacunas a atividades concretas; não altera a DAG original nem declara essas atividades executadas. Atividades de aceite integral podem depender do plano novo, enquanto componentes já entregues são reutilizados.

| Atividade | Estado auditado | Evidência / pendência | Trabalho de conclusão |
|---|---|---|---|
| FAC-001 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-002 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-003 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-004 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-005 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-006 | in_progress | Doctor decide sucesso apenas pelo Registry; falta supervisionar a stack e os workers necessários por perfil. | FAC-106 |
| FAC-007 | in_progress | pytest injeta paths; o comando documentado gen_client falha por import de context_engine no ambiente raiz. Checkout limpo não recertificado. | FAC-100, FAC-109 |
| FAC-008 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-009 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-010 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-011 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-012 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-013 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-014 | in_progress | Contrato do domínio ainda adia telefone, embora API/UI já o implementem; remoção do campo opcional não funciona. | FAC-107 |
| FAC-015 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-016 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-017 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-018 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-019 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-020 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-021 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-022 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-023 | in_progress | Sondagem aceita duas transições com expected_version=1 e permite done sem gates/resultados. | FAC-101 |
| FAC-024 | in_progress | Heartbeat exige status leased e rejeita running; fencing precisa valer no ciclo operacional completo. | FAC-102 |
| FAC-025 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-026 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-027 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-028 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-029 | in_progress | gen_client --check falha por import; com PYTHONPATH explícito também detecta client desatualizado. | FAC-100, FAC-126 |
| FAC-030 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-031 | in_progress | Detalhe mostra requisitos e dependências, mas não runs, diffs, gates e motivos operacionais de bloqueio. | FAC-125 |
| FAC-032 | in_progress | Decisão genérica persiste, mas não retoma grafo; hash de demanda não inclui conteúdo da RequirementRevision nem plano. | FAC-103, FAC-119 |
| FAC-033 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-034 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-035 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-036 | in_progress | Cliente read-only e provider injetável testados; falta composição operacional PAT/App, renovação e prova do repo permitido. | FAC-122 |
| FAC-037 | in_progress | Página com 100 resultados e 1 PR vira 99 Issues e encerra polling antes da página seguinte; falta worker operacional supervisionado. | FAC-122 |
| FAC-038 | in_progress | Discovery atual confirma menções de paths de inventário fornecido; não investiga demanda livre nem está ligado ao fluxo real. | FAC-111, FAC-112 |
| FAC-039 | in_progress | Helper versiona texto fornecido; não produz EARS/cenários nem oferece refinamento e esclarecimento operacional por canal. | FAC-103, FAC-112 |
| FAC-040 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-041 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-042 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-043 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-044 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-045 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-046 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-047 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-048 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-049 | in_progress | Binding usa snapshot_sha como hash do contexto JSON, não commit Git, e não renova contexto após revisão. | FAC-103, FAC-124 |
| FAC-050 | in_progress | Pedido literal em português 'alterar cor do botao para o tema dark' é classificado ask e não gera proposta. | FAC-112, FAC-120, FAC-124 |
| FAC-051 | in_progress | Gateway existe como classe com callbacks; falta bridge operacional e política central de paths protegidos. | FAC-104, FAC-124 |
| FAC-052 | in_progress | Chat acessível apenas a QA, sem aceite de proposta na UI; nomes de anexos são descartados no envio. | FAC-124, FAC-125, FAC-126 |
| FAC-053 | in_progress | Contador de hops/calls funciona isoladamente; não é consumido nas conversas operacionais nem persistido entre processos. | FAC-114, FAC-124 |
| FAC-054 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-055 | in_progress | Grafo é builder de callbacks; não há composição produtiva, nó eval ou sincronização transacional com Task Engine. | FAC-114, FAC-117, FAC-118, FAC-119 |
| FAC-056 | in_progress | API cria task/outbox e dispatcher chama callback fake; não há consumidor contínuo nem subworkflow QA concreto. | FAC-114, FAC-119, FAC-134 |
| FAC-057 | in_progress | interrupt aceita dict com actor/approval_id; falta validar ApprovalRequest persistido, versão e changes_requested no resume real. | FAC-103, FAC-119 |
| FAC-058 | in_progress | Retry/DLQ/reconciler são funções testadas; falta loop periódico ligado a inferência/commit/publicação reais. | FAC-114, FAC-119, FAC-137 |
| FAC-059 | in_progress | Slot PostgreSQL existe; scheduler é fake e faltam locks por paths, anti-starvation e uso do slot por todos os chamadores. | FAC-102, FAC-110, FAC-114 |
| FAC-060 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-061 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-062 | in_progress | Proteção de secrets é rasa: config/.env chegou à chamada de lançamento em probe com Docker mockado. | FAC-104, FAC-116 |
| FAC-063 | in_progress | Implementer aplica patch fornecido pelo chamador; não gera patch com LLM/contexto nem registra commit/run real. | FAC-110, FAC-111, FAC-115 |
| FAC-064 | in_progress | Runner olha apenas returncode; falta seleção de suites, JSON/artefatos vinculados ao run/SHA e correção limitada. | FAC-105, FAC-116, FAC-117 |
| FAC-065 | in_progress | Merge isolado e regressão via callback existem; faltam integração pelo coordenador e tarefa de resolução de conflito. | FAC-114, FAC-117, FAC-133 |
| FAC-066 | in_progress | Validação de review e evaluate injetável existem; reviewer local real e veto no fluxo ainda não foram demonstrados. | FAC-118 |
| FAC-067 | in_progress | Publisher valida dataclasses fornecidas; só há Protocol de transporte, sem push/PR reais nem resolução de decisões persistidas. | FAC-103, FAC-127 |
| FAC-068 | in_progress | Schema canônico existe, mas validate_checks ainda aceita compatibilidade schema/ok que ignora status/exit_code. | FAC-105 |
| FAC-069 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-070 | in_progress | quality_frontend só executa Factory Web; Registry foi verificado separadamente nesta auditoria. | FAC-117 |
| FAC-071 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-072 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-073 | in_progress | Agregador aceita quatro PASS de outro run/SHA e apenas reetiqueta run_id solicitado; proveniência não é verificada. | FAC-105, FAC-117 |
| FAC-074 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-075 | in_progress | Schemas/métricas sintéticos não estão ligados a runs autoritativos e aceites do ciclo real. | FAC-105, FAC-129, FAC-138 |
| FAC-076 | in_progress | 10 rótulos provisórios aguardam revisão independente; 14 casos em cinco datasets não são goldset humano aprovado. | FAC-129, FAC-139 |
| FAC-077 | in_progress | Calibração histórica 3/3 sobre rótulos provisórios não certifica Judge; falta calibração independente e integração operacional. | FAC-129, FAC-139 |
| FAC-078 | in_progress | Feedback aceita UUID de run sem provar existência e recebe modelo/hash do cliente; first_pass_rate é aprovações/feedbacks. | FAC-105, FAC-129 |
| FAC-079 | in_progress | Comparação consome observações externas; faltam trials reais vinculados a modelos/datasets e verificação de proveniência. | FAC-129 |
| FAC-080 | in_progress | Promoção valida formato do hash do experimento, não existência/resultado/regressão; runtime não resolve o prompt ativo. | FAC-129 |
| FAC-081 | in_progress | Middleware HTTP e utilitários redigem/correlacionam; cadeia intake-worker-modelo-checks-review-publicação não está instrumentada. | FAC-138 |
| FAC-082 | in_progress | Wrapper Ollama mede tempos/tokens em teste, mas chamadas operacionais não passam por ele de ponta a ponta. | FAC-110, FAC-138 |
| FAC-083 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-084 | in_progress | Helpers de spans testados com tracer fake; bridges reais OpenBot/LangGraph/modelo não estão conectadas. | FAC-124, FAC-138 |
| FAC-085 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-086 | in_progress | Dashboard de medidas locais existe; falta origem em runs reais e métricas por persona/aceite/retrabalho. | FAC-125, FAC-129, FAC-138 |
| FAC-087 | in_progress | Teste CPF chama helper com fixture; não cria demanda nem executa Planner/Backend/QA com modelo local. | FAC-135 |
| FAC-088 | in_progress | Telefone já foi implementado; teste valida API e cria tasks manualmente, sem demonstrar autoria/integração por agentes. | FAC-107, FAC-132, FAC-133 |
| FAC-089 | in_progress | Demo de follow-up usa lambda retornando run-id; não gera novo teste por QA real. | FAC-134 |
| FAC-090 | in_progress | Demo cria proposta e garante lockfile inalterado; não executa remediação nem scan antes/depois. | FAC-136 |
| FAC-091 | in_progress | Reabre SQLite e testa peças de retry; não mata/reinicia worker real em inferência, HITL e após efeito externo. | FAC-119, FAC-137 |
| FAC-092 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
| FAC-093 | in_progress | Sem UAT independente; provas isoladas não substituem execução das jornadas e assinatura verificável. | FAC-108, FAC-139 |
| FAC-094 | in_progress | Mutation Projects funciona em fake; não há resolução item/Issue/status nem consumidor do espelho. | FAC-128 |
| FAC-095 | in_progress | Cliente Jira fake sem pipeline persistido de cursor/reconciliação/worker; opt-in não é integração operacional concluída. | FAC-128 |
| FAC-096 | in_progress | Webhook valida HMAC e cria demanda, mas aceita qualquer full_name válido e usa caminho de intake próprio. | FAC-104, FAC-128 |
| FAC-097 | in_progress | Script gera proposta sintética; worker agendado de auditoria de dependências previsto na atividade não existe. | FAC-136, FAC-128 |
| FAC-098 | in_progress | Backup/restore de banco tem evidência; faltam artefatos, OpenBot, retenção de traces e limpeza segura de worktrees. | FAC-138 |
| FAC-099 | done | Componente existente e cobertura local disponível; done não comprova jornada autônoma nem aceite humano. | — |
