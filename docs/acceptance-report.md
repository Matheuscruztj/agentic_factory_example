# Acceptance report (draft)

Status: **pending_ai_acceptance**. no AI acceptance is claimed; required evidence or a valid AI receipt is missing

Backlog SHA-256: `398cac7921deb7666f8d445b36df3476c6ddd3a081570723cd7efd146380a427`. Nenhum reviewer de IA independente aprovou este relatório.

| Atividade | Estado | Critério registrado |
|---|---|---|
| FAC-001 | done | Nenhum arquivo legado é reescrito sem evidência do diagnóstico. |
| FAC-002 | done | ADRs explicitam owner de estados e proibições verificáveis. |
| FAC-003 | done | Nenhuma credencial real está no repositório; boot aceita integrações desabilitadas. |
| FAC-004 | done | Diferencia chave inválida e rede indisponível sem enviar mensagens ou criar Issues. |
| FAC-005 | done | Contratos e limitações citados com versões, ou bloqueio técnico explícito. |
| FAC-006 | done | Um comando devolve status claro sem ler milhares de linhas de log. |
| FAC-007 | done | Workspace Python instala e roda lint/test em checkout limpo. |
| FAC-008 | done | Frontend compila com design responsivo e sem erros TS. |
| FAC-009 | done | Serviços base sobem e persistem dados com restart sem portas públicas. |
| FAC-010 | done | API fornece liveness e readiness distinto por dependência. |
| FAC-011 | done | Sessões fecham corretamente e migrations são reproduzíveis. |
| FAC-012 | done | Acesso a 127.0.0.1 não substitui autenticação; segredo nunca vai para browser. |
| FAC-013 | done | UI distingue configuração pendente de falha operacional. |
| FAC-014 | done | Contrato da demo claro, com dados sensíveis sintéticos e sem requisito indefinido. |
| FAC-015 | done | API CRUD atende contrato e não depende da Factory API para funcionar. |
| FAC-016 | done | Email duplicado gera conflito 409 e schema tem constraints. |
| FAC-017 | done | Fluxos cadastro funcionam desktop/mobile, com acessibilidade básica. |
| FAC-018 | done | Bug reproduzível possui teste e execução não depende de modelos LLM. |
| FAC-019 | done | E2E aprovado com dados sintéticos; artefatos por execução. |
| FAC-020 | done | Outro dev reproduz demo e fixtures sem credencial externa. |
| FAC-021 | done | Mesmo evento/Issue não cria duas demandas e versão aprovada é imutável. |
| FAC-022 | done | Tarefa bloqueada não é liberada e ciclos geram erro tipado. |
| FAC-023 | done | LLM não altera status diretamente; transição inválida gera erro estável. |
| FAC-024 | done | Duas instâncias não executam mesma task simultaneamente. |
| FAC-025 | done | Processamento at-least-once não vira efeitos duplicados no domínio. |
| FAC-026 | done | Toda task/run tem links a evidências, sem credenciais ou dumps de prompts. |
| FAC-027 | done | Vertical slice de estado percorre várias tasks sem chamar modelos. |
| FAC-028 | done | OpenAPI descreve contratos reais e não executa shell. |
| FAC-029 | done | Alteração de contrato incompatível falha teste local. |
| FAC-030 | done | Kanban retrata DB, não estado local imaginado pela UI. |
| FAC-031 | done | Operador entende por que tarefa está bloqueada e qual gate falta. |
| FAC-032 | done | Nenhuma alteração de escopo/PR é autorizada só pela resposta do modelo. |
| FAC-033 | done | Cliente reconecta após queda sem perder eventos nem expor secrets. |
| FAC-034 | done | Smoke end-to-end UI passa com Fake Scheduler. |
| FAC-035 | done | Mensagem repetida atualiza evento sem duplicar demanda. |
| FAC-036 | done | Nunca consulta repo externo por parâmetros arbitrários de Issue. |
| FAC-037 | done | PC desligado não perde issues; reexecução não duplica. |
| FAC-038 | done | Nenhuma regra de negócio inventada vira aceitação sem confirmação. |
| FAC-039 | done | Spec aprovado é imutável; follow-up mantém history. |
| FAC-040 | done | Integração habilitável por feature flag sem interferir no manual intake. |
| FAC-041 | done | Todo agente tem contrato, ferramentas permitidas e eval correspondente. |
| FAC-042 | done | Registry determinístico, assinado/versionado por hash. |
| FAC-043 | done | Pergunta trivial não carrega 30 schemas nem skills. |
| FAC-044 | done | Pack reproduzível por hash com estimativa token e escopo correto. |
| FAC-045 | done | Falha de 10K linhas vira 1 JSON e acesso seletivo auditado. |
| FAC-046 | done | Mudanças no router precisam superar baseline ou são rejeitadas. |
| FAC-047 | done | Versão e endpoints reais testados; run_shell inseguro desativado. |
| FAC-048 | done | API interna não depende de payloads específicos upstream. |
| FAC-049 | done | Dois cards na mesma persona nunca misturam requisitos ou dados. |
| FAC-050 | done | Pergunta sobre teste não dispara build nem cria branch. |
| FAC-051 | done | OpenBot não tem caminho direto para ler .env ou escrever repo. |
| FAC-052 | done | Operador conversa com @qa no card e acompanha TaskProposal. |
| FAC-053 | done | Nenhuma conversa entra em loop ou executa alteração por menção isolada. |
| FAC-054 | done | Não usar MemorySaver em processo para persistência pós-restart. |
| FAC-055 | done | Grafo nunca marca done após check com exit 1 ou 2. |
| FAC-056 | done | ISSUE concluída recebe follow-up QA sem recomeçar discovery inteiro. |
| FAC-057 | done | Humano continua sendo autoridade e restart mantém pause. |
| FAC-058 | done | Falha Ollama causa fila/retry, não repetição de commit/PR. |
| FAC-059 | done | Duas tasks paralelas não obrigam duas inferências simultâneas em 8GB VRAM. |
| FAC-060 | done | Workflow passa sem network, Ollama e nenhum cloud token. |
| FAC-061 | done | Sem worktree compartilhado nem edição direta de main. |
| FAC-062 | done | Tentativa de ler .env/host path falha sem vazar dados. |
| FAC-063 | done | Patch só altera arquivos permitidos e é reproduzível no SHA base. |
| FAC-064 | done | Gates falhos impedem avanço, erro 2 não é tratado como bug de código. |
| FAC-065 | done | Merge de tasks paralelas não passa sem tests/regressão. |
| FAC-066 | done | Reviewer tem prompt/modelo e rubric próprios e pode reprovar task. |
| FAC-067 | done | Sem autorização nenhum push remoto ocorre; PR inclui evidências redigidas. |
| FAC-068 | done | Runner consome uma linha JSON e não precisa parsear log livre. |
| FAC-069 | done | Mudanças Python não avançam com lint/typecheck/unit vermelhos. |
| FAC-070 | done | Frontend passa sem erros de tipagem e build com config real. |
| FAC-071 | done | Smoke local reproduzível sem GitHub Actions/LLM real. |
| FAC-072 | done | Critical/high conforme policy bloqueia; suppressions não são adicionadas pelo agente. |
| FAC-073 | done | Nenhum score LLM sobrepõe gate determinístico vermelho. |
| FAC-074 | done | Perfil extendido roda quando habilitado, com métricas e sem dependência cloud. |
| FAC-075 | done | Scorecards não atribuem nota subjetiva onde há teste determinístico. |
| FAC-076 | done | Casos têm gabarito e não são usados em prompt de produção. |
| FAC-077 | done | Juiz não julga a própria resposta e jamais muda approval/gate automaticamente. |
| FAC-078 | done | Feedback não pode ser falsificado por agente avaliado. |
| FAC-079 | done | Sem evidência de melhora não há promoção de prompt. |
| FAC-080 | done | Prompt candidato só vira ativo após aprovação explícita. |
| FAC-081 | done | Logs não contêm tokens, e uma task pode ser traçada ponta a ponta. |
| FAC-082 | done | Dashboard diferencia tempo de espera, carregamento e geração. |
| FAC-083 | done | Observabilidade não bloqueia pipeline por falha de métrica. |
| FAC-084 | done | Traces correlacionam workflow e chamada de modelo sem dados secretos. |
| FAC-085 | done | Desligar Phoenix não interfere em criação/teste/entrega. |
| FAC-086 | done | Dash separa valores medidos de estimativas e filtros por tarefa. |
| FAC-087 | done | Bug repro antes, teste passa após fix e nenhuma mudança fora do escopo. |
| FAC-088 | done | Campo funciona em API+UI e auditoria registra dependências. |
| FAC-089 | done | Demanda original mantém histórico e não reexecuta todo discovery. |
| FAC-090 | done | Remediação tem evidência objetiva e humano aprova publicação. |
| FAC-091 | done | A execução retoma corretamente e preserva audit trail. |
| FAC-092 | done | Nenhum prompt override atravessa Tool Gateway/policies. |
| FAC-093 | done | Relatório não diz done se requisito/gate não foi verificado; aceite global exige evidência e revisão técnica independente por IA para todas as atividades requeridas. |
| FAC-094 | done | Problema de Projects não impede Task Engine local. |
| FAC-095 | done | Jira desligado não requer credencial nem interfere nos demais canais. |
| FAC-096 | done | Túnel não expõe admin UI/Ollama e payload inválido é rejeitado. |
| FAC-097 | done | Scanner pode propor, mas não atualizar automaticamente por ação perigosa. |
| FAC-098 | done | Recuperação testada, não apenas script de backup não verificado. |
| FAC-099 | done | Nenhum GitHub Secret, YAML CI obrigatório ou dependência de VPS aparece no caminho crítico. |
| FAC-100 | done | Checkout descartável instala os pacotes usados por CLI/API/workers sem depender de pythonpath do pytest. gen_client --check passa sem workaround e detecta contrato propositalmente alterado; DTOs usados pelo chat/evals são gerados. |
| FAC-101 | done | Duas sessões PostgreSQL com a mesma versão: só uma decisão vence; replay idêntico permanece idempotente. ready/running/review/done exigem deps, revisão aprovada, lease e evidências pertinentes; execução fake não conclui tasks reais. |
| FAC-102 | done | Heartbeat renova leased e running; worker vencido não publica resultado, commit nem efeito privilegiado. Escopos sobrepostos são serializados, tasks independentes progridem e prioridade possui política anti-starvation testada. |
| FAC-103 | done | Distinguir base_git_sha, context_sha256, requirement_revision_id/version/hash, plan_hash e approval_id; provar commit existente. Decisão aprova payload final com owner, scopes, deps, risk e ações; mudança invalida autorização e preserva revisão aprovada. Aprovação de escopo habilita execução local dentro dele; push, PR, merge e alterações protegidas mantêm decisões próprias. |
| FAC-104 | done | Negar secrets em qualquer profundidade, symlinks/hardlinks/renames e diffs que escapem do escopo; não montar Docker socket/credenciais do host. Arquivos da fábrica, policies, testes ocultos e resultados de gates têm proteção de integridade; alteração sensível solicita revisão reforçada. Webhook exige repo fixo autorizado além de HMAC; payload/arquivo externo é dado, sem conceder tools. |
| FAC-105 | done | Run/attempt autoritativo vincula task, modelo/digest, prompt/context/skill, revisão e commits; feedback referencia run existente. Cada gate guarda run_id, task_id, attempt, git_sha/tree hash, suite/tool/config hash e artefato verificado; outro run/SHA nunca vira PASS. Remover aceitação permissiva schema/ok no caminho de entrega; resultado ausente, duplicado, inconsistente ou adulterado bloqueia. |
| FAC-106 | done | Um runbook inicia APIs, UIs, OpenBot gateway, intake/coordenador e reconciliação conforme perfil; health indica processos ausentes. Doctor falha quando qualquer dependência obrigatória do perfil falhar; desligar integração opcional preserva manual/direct. Classificar serviço configurado, alcançável e funcional separadamente, sem expor credenciais. Catálogo distingue variável consumida, default e proposta; alinhar URLs/models/budgets, nomes Projects e ambas allowlists Telegram, sem editar secrets reais. |
| FAC-107 | done | Distinguir PATCH omitido, null para limpar, vazio e valor inválido; documentar contrato vigente sem alegar que telefone está adiado. UI cadastra, edita, remove telefone e busca conforme regra; persistência PostgreSQL e migração mantêm dados anteriores. |
| FAC-108 | done | Relatório não aceita backlog obrigatório pendente, run/gate ausente, hash diferente, skip sem justificativa ou assinatura meramente textual. Identidade independente, decisão, data, escopo do aceite e hashes dos artefatos são verificáveis; opcionais adiados ficam explícitos. Relatório anterior é histórico, sem declarar UAT nem solicitar assinatura antes de haver entrega revisável. |
| FAC-109 | done | Definir commit Git revisado com todos os arquivos necessários; worktree não depende de alterações locais não commitadas ou arquivos untracked. Fixtures começam sem a mudança a executar; baseline, resultados esperados e testes externos ao executor têm hashes. Auditoria não cria commit nem restaura checkout do operador; congelamento ocorre em fluxo futuro autorizado. |
| FAC-110 | done | Adapter direct suporta chat, saída estruturada, patch/tool protocol, timeout, cancelamento e capabilities sem cloud/fallback implícito. Registrar tag e digest, limites de contexto/saída, fila, load e tokens; serializar também OpenBot e Judge na GPU. Modelo ausente/OOM/schema inválido é classificado e limitado; nenhum download/modelo vencedor é presumido. |
| FAC-111 | done | Buscar arquivos/trechos e contratos no commit autorizado mesmo quando pedido não cita paths; não confundir hash JSON com Git SHA. Pack possui 0–2 skills, citações verificáveis, orçamento, redaction e expansão seletiva; artefatos originais permanecem disponíveis sob autorização. Contexto de outro card/revisão, goldset e testes ocultos são excluídos. |
| FAC-112 | done | Pedido livre vira tipo/impacto/evidências, fatos e dúvidas; variantes portuguesas como alterar/adicionar e menções @persona não perdem intenção. Pergunta material pausa em clarification_pending; resposta retoma o mesmo run e gera EARS/cenários positivos/negativos versionados. Requisito/escopo aprovados ficam imutáveis; pedido simples usa fluxo proporcional e não exige implementação backend desnecessária. |
| FAC-113 | done | Plano persistido atribui papel, escopo, base, risco, deps, testes e outputs; DAG inválido não cria execução. Contrato API/UI permite frontend com contrato aprovado em paralelo ao backend; integração depende dos dois. QA/Reviewer e evidências de entrega são tarefas explícitas; não inflar plano de simples CSS com mudanças fora do alvo. |
| FAC-114 | done | Intake/revisão/plano aprovados geram outbox e worker concreto inicia grafo persistido sem chamada manual a helpers. Registrar progress, tasks/runs e estado de demanda no PostgreSQL; terminal só após dependências e gates verificáveis. Pausa/cancelamento, shutdown, backpressure, reconciliação e limites de colaboração estão integrados, não apenas injetados por testes. |
| FAC-115 | done | Agente lê somente contexto autorizado, gera patch inédito, aplica no SHA base, testa e registra diff/hash/commit no worktree do run. Suporta criação/alteração de arquivos front/back/migration; valida paths reais, novos arquivos, renames e estado dirty do worktree. Budgets de passos/tokens/tempo e tentativas impedem loop; modelo não grava diretamente em main nem resolve permissão sozinho. |
| FAC-116 | done | Imagem por digest tem Python/uv, Node/pnpm e browsers conforme perfil; deps congeladas são preparadas sem execução irrestrita/rede do agente. Runner executa código/imports do worktree correto; Postgres/serviços de teste descartáveis têm rede mínima distinta do perfil sem rede. Lint, testes, build e E2E geram artefatos persistentes fora do controle do agente; containers e bancos são limpos por run. |
| FAC-117 | done | Selecionar testes por impacto e executar regressão integrada de ambos os produtos; mypy tem cobertura justificada e não somente 28 arquivos fixos. Falha de código retorna evidência compacta ao agente; infra/configuração aguarda recuperação e não consome loop de correção de código. Testes ocultos/gates protegidos não podem ser enfraquecidos pelo executor; modelo/judge nunca sobrepõe reprovação. |
| FAC-118 | done | Reviewer real recebe diff no SHA final, requisitos e evidências do mesmo run, com contexto/prompt separado e sem tools de escrita. High/critical e evidência ausente geram retrabalho ou bloqueio; correção muda SHA e exige revisão nova. Judge permanece opcional/complementar; indisponibilidade de juiz não substitui testes nem pode fingir revisão aprovada. |
| FAC-119 | done | ApprovalRequest persistido e identidade autenticada controlam interrupt/resume com approved/rejected/changes_requested. Consumidor contínuo de follow-up/outbox usa identificador durável e recupera crash entre efeito e recibo sem duplicar task/commit. Retomar pós-restart em processo novo preserva spec, lease e artefatos; DLQ/retry são operáveis e auditados. |
| FAC-120 | done | Marco de componente: Telegram grammar v1 and post-commit, replay-safe inbox journaling are implemented and covered by database-backed worker tests. |
| FAC-121 | done | Confirmação, perguntas, progresso e resultado usam outbox idempotente e reply/thread correto; anexos/logs são redigidos e limitados. Definir política de equivalência da identidade Telegram com operador; se não aprovada, decisões sensíveis oferecem link à UI autenticada. Aprovação por canal, quando habilitada pelo operador, é escopada ao hash/versão/ação e não permite auto-merge/publicação implícita. |
| FAC-122 | done | Marco de componente: Pinned GitHub reads, raw pagination metadata, PR filtering, atomic persistent cursor, overlap polling and restart/idempotency paths are implemented and covered by transport/worker tests. |
| FAC-123 | done | Marco de componente: Issue comments are imported as bounded, redacted, immutable versioned proposal events; offline operation is covered. Remote reconciliation remains separately gated. |
| FAC-124 | done | Marco de componente: OpenBot adapter, role manifests and tool gateway enforce role/manifest boundaries, context binding and bounded conversation contracts in component tests. |
| FAC-125 | done | Marco de componente: Factory UI dashboard and agent conversation surfaces expose the current demand/task/run contracts, authorization states and loading/error paths in browser/build checks. |
| FAC-126 | done | Marco de componente: Generated API client and event/API contracts are validated by OpenAPI, build and browser-facing component coverage; cross-card SSE and full no-mock flow remain in downstream journeys. |
| FAC-127 | done | Marco de componente: GitHub publishing component binds repository, branch and commit SHA to distinct push/PR approvals, reconciles repeated requests, and redacts evidence in transport contract tests. |
| FAC-128 | done | Marco de componente: Projects/Jira adapters and signed webhook intake have fixed-repository/optional-credential boundaries and offline contract/security tests; live optional-provider setup remains opt-in. |
| FAC-129 | done | Marco de componente: Prompt experiment, feedback, release and scorecard components preserve baseline/candidate hashes, objective checks and explicit non-promotion; judge-disabled metrics stay unavailable. |
| FAC-130 | done | Texto literal 'alterar cor do botao para o tema dark' é aceito via UI, Telegram e GitHub Issue em execuções separadas sobre baseline limpo. Resolver botão/tela/tema e regra de contraste; se ambíguo perguntar, aprovar escopo e implementação pode ser fornecida pelo Codex em bundle assistido aprovado por hash, sem alegar autoria Ollama. Provar cor computada, hover/focus/disabled, contraste, light preservado, gates, revisão e evidências; evitar backend sem necessidade. Autoria assistida pelo Codex foi autorizada pelo operador; autonomia Ollama é reportada separadamente e não é condição de entrega funcional. Nenhum resultado assistido é rotulado como autoria autônoma Ollama. |
| FAC-131 | done | Contrato de etiquetas parte do baseline sem tags, registra defaults do operador, contém critérios/cenários coerentes e um plano executável hash-bound. A autoria Codex-assistida e as decisões delegadas ficam identificadas; não se exige persona Analyst/Planner autônoma. |
| FAC-132 | done | Migração preserva cadastro legado e rollback seguro; endpoints de etiquetas e associação/filtro passam os limites e falhas essenciais em PostgreSQL descartável, com evidência ligada aos commits DB/BE. |
| FAC-133 | done | Branch integrada resolve o conflito de migration e a jornada de etiquetas passa E2E contra PostgreSQL descartável, incluindo duplicata, associação, filtro, reload, mobile/teclado e regressão de cliente; registrar SHA e review local. |
| FAC-134 | done | Testes do follow-up QA comprovam proposta escopada, limite de aprovação e replay idempotente sem duplicar task/efeitos; integração externa e aprovação humana de um follow-up específico ficam fora deste fechamento. |
| FAC-135 | done | Fixture isolada começa com falha conhecida e teste que reprova; CPF permanece sintético e sem requisito de adicionar PII ao produto. Intake real conduz Analyst/Planner/Backend/QA/Reviewer, Codex assistido ou LLM produz o fix, com proveniência explícita e regressão passa no commit correto. Artefatos distinguem reprodução anterior, alteração gerada e validação posterior; helper previamente correto não conta como nova execução. Autoria assistida pelo Codex foi autorizada pelo operador; autonomia Ollama é reportada separadamente e não é condição de entrega funcional. Nenhum resultado assistido é rotulado como autoria autônoma Ollama. |
| FAC-136 | done | Na fixture sintética, scanner mostra a vulnerabilidade antes e zero findings depois do patch, com hashes conferidos e testes passando; lockfile do produto e publicação não são alterados. |
| FAC-137 | done | Dois casos críticos com PostgreSQL/checkpointer sobrevivem à morte do worker e retomada em novo processo sem perder ou duplicar estado de aprovação/domínio; serviços externos são simulados. |
| FAC-138 | done | Backups descartáveis de Factory, Registry, OpenBot e artefato restauram com integridade/readback; testes focados confirmam redaction e retenção sem revelar segredos. |
| FAC-139 | done | As atividades obrigatórias do escopo reduzido estão concluídas com evidências apontadas; quality-fast passa; o relatório separa o que foi testado do que ficou fora e não declara aceite global/produção. |
| LLMG-T01 | done | ADR aprovado; modo `direct` preservado |
| LLMG-T02 | done | `docker compose config` válido com profile desligado/ligado |
| LLMG-T03 | done | testes offline + JSON/exit 0/1/2; segredos não logados |
| LLMG-T04 | done | fake adapters unitários; modo direto sem LiteLLM |
| LLMG-T05 | done | smoke chat retorna resposta; rota sem publicar gateway externamente |
| LLMG-T06 | done | smoke com OpenBot e fake LangGraph; 1 chamada de cada vez |
| LLMG-T07 | done | trace correlacionado, sem segredos; Phoenix opcional |
| LLMG-T08 | done | relatório de overhead; sem conclusão se N insuficiente |
| LLMG-T09 | done | fixture íntegra, casos positivos/negativos, sem vazamento do gabarito |
| LLMG-T10 | done | medição 1 modelo × 1 fixture em modo direto e proxy |
| LLMG-T11 | done | resultados reprodutíveis 0/1/2; artefatos anexados |
| LLMG-T12 | done | relatório inclui tarefas aceitas/h e tokens por aceite |
| LLMG-T13 | done | 20+ rótulos conferidos, holdout segregado |
| LLMG-T14 | done | invalid JSON contabilizado; não forçar score quando faltam evidências |
| LLMG-T15 | done | relatório com matriz de confusão, exemplos divergentes |
| LLMG-T16 | done | prompt ativo não muda sem aprovação e regressão |
| LLMG-T17 | done | tentativa maliciosa bloqueada; resultado persistido |
| LLMG-T18 | done | E2E de navegação + estados vazio/erro |
| LLMG-T19 | done | exclusão de artefatos obsoletos sem eliminar auditoria essencial |
| LLMG-T20 | done | cenário LiteLLM offline não bloqueia `direct` |
| LLMG-T21 | done | relatório final de evidências por atividade com receipt HMAC de IA vinculado aos hashes do módulo, cobrindo os perfis coding e judge, comparação AB proxy/direct, red-team, bloqueio HITL e perfil de 8 GB VRAM; sem assinatura humana de UAT. |
| FAC-140 | done | Marco de componente: Eight persona rubric drafts contain versioned criteria, applicability, evidence requirements, 0–3 anchors, null/unassessable behavior and explicit draft-only non-activation. |
| FAC-141 | done | Marco de componente: Meta-grader now requires reference, two valid alternatives, seeded defect and removed-test controls; constant-output and critical false acceptance fail, with promotion disabled. |
| FAC-142 | done | Gerar casos sintéticos versionados com oráculo executável e resultados conhecidos; separar rótulo determinístico de julgamento de IA e manter human_agreement indisponível. Executar casos corretos, contraditórios e sem evidência e variantes de ordem, verbosidade, autoria, referência fabricada e injeção; medir FN crítico, falsa reprovação, abstenção/cobertura/schema e limites. Revisão independente por IA verifica dataset/oráculo/resultados e conclusão por slice; avaliação completa pode concluir advisory_only sem promover modelo nem alegar calibração humana. |
| FAC-143 | done | Marco de componente: Reliability metrics report case-macro pass@1/pass@k/pass^k, paired provenance, missing measured costs as null, and case-bootstrap intervals only at adequate sample size. |
| FAC-144 | done | Marco de componente: Resource profiles record CPU/RAM/VRAM/time, concurrency, warmup, cache and model digest; mismatched profiles are inconclusive and no hardware multiplier is applied. |
| FAC-145 | done | Marco de componente: Handoff comparison records authoritative state SHA, lost obligations, duplicate effects, divergence, reorientation cost and large-log recovery without automatic promotion. |
| FAC-146 | done | Marco de componente: Architecture comparison uses paired cases and counts coordination, GPU wait, tools, review and rework; fewer than 20 paired cases stays inconclusive and adoption remains manual. |
| FAC-147 | done | Marco de componente: Tool usability report measures outcome, selection, argument validity, recovery, relevant evidence, tokens and unproductive calls, with an explicit no-tool control and no fixed tool order. |
| FAC-148 | done | Marco de componente: Versioned suite catalog now names all seven eval families, owners, split policies and incident lifecycle; validation prevents draft data from claiming production or secret-holdout status. |
| FAC-149 | done | Marco de componente: Controlled interaction candidates specify state/effect oracles and negative controls for no-op, material clarification, approval boundaries and cancellation. |
| FAC-150 | done | Marco de componente: Three no-solution fullstack capability baselines list unresolved product decisions and required CSV import/export/pagination controls; no feature implementation or oracle activation is claimed. |
| FAC-151 | done | Marco de componente: Cross-language/channel candidate families include equivalent normalized intents plus non-equivalence controls and family-level split policy; candidates remain unapproved and outside prompts. |
| FAC-152 | done | Marco de componente: Local GitHub/Telegram simulator supports paginated issues/comments, PR filtering, edits, updates/replies/sends, journal, fake clock and one-shot faults; actual integration transports/workers run against it. |
| FAC-153 | done | Entradas inválidas não provocam 500 no PostgreSQL; reduzir avisos reais sem suppressions automáticas, preservando E2E e relatórios dos scanners. |

Este scorecard usa o aceite técnico por IA autorizado pelo operador; ele não declara aceite humano nem autoriza efeitos externos com HITL próprio. `done` no backlog precisa estar ligado a evidências verificadas e ao receipt de IA.
