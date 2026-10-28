<!-- Cópia integral do state.md antes da revisão documental de 2026-10-27. Histórico; não é o handoff vigente. -->

# Estado operacional e plano de fechamento

Atualizado em 2026-10-26 (validação das cinco primeiras pendentes até 18:25 UTC). Fonte canônica de status e critérios: `specs/implementation-backlog.json`. Este arquivo resume a execução necessária; não substitui os critérios do backlog nem autoriza efeitos externos.

## Resumo atual

- Backlog: 174 atividades; 162 `done`, 12 `in_progress`, nenhuma `todo`.
- Atividades abertas: FAC-121, FAC-130–139 e FAC-142.
- Scorecard: `pending_ai_acceptance`; não há receipt HMAC válido. FAC-139 só pode ser executada depois das jornadas e requisitos obrigatórios estarem fechados.
- Último full run: `20261026T171041Z-c865e753` passou 303 testes PostgreSQL, Factory E2E 1/1, Registry E2E 2/2, segurança/DAST e performance; Sonar falhou em cobertura nova 61,5% (mínimo 80%), sem novas violações.
- Validações: `make quality-fast` passou 11/11 no run `20261026T172934Z-bede3031`. `pytest` executado fora do stack passou 295 e pulou 8; não substitui a execução PostgreSQL descartável do full run. O juiz foi verificado em dados provisórios e continua sem autoridade de promoção. Essas validações globais não satisfazem autoria agêntica ou jornadas dos itens abertos.
- Preflight live passou para PostgreSQL, Redis, Ollama, OpenBot, GitHub (leitura) e Telegram (autenticação sem envio); Jira/Phoenix/LiteLLM são opcionais e foram skipped. API local Factory e UI foram iniciadas para a jornada. Não contar configuração, eco do operador, fake ou fixture como resposta/agência live.
- Evidência de execução agêntica anterior existe em `.runtime/factory-real-e2e/` e nos diretórios por atividade; revisão `uncertain` ou resposta sem evidência não é aceite.

## Estado após a continuação de FAC-121/FAC-130

O backlog permanece com 162 atividades `done` e 12 `in_progress`; scorecard `pending_ai_acceptance`, sem receipt. Foram feitas novas verificações focadas: contexto/API 20/20, Registry Playwright 2/2 e API/outbox 6/6; elas validam componentes existentes, não autoria agentiva nem aceites das jornadas. `make quality-fast` passou 11/11 no run `20261026T172934Z-bede3031`. O full run `20261026T171041Z-c865e753` passou 303 testes PostgreSQL, E2E Browser Factory 1/1, Registry 2/2, SAST/SCA/secrets, DAST e perf; Sonar falhou somente no gate de cobertura nova (61,5% vs 80%), com zero novas violações. `pytest` fora do stack passou 295 e pulou 8; tentativa posterior de novo DB descartável não passou autenticação e não executou testes. Não contar essa tentativa como validação.

O `.env` local existe, está ignorado e com modo restrito. O preflight live (`scripts/validate_env.py --env .env --mode live --require core,postgres,redis,ollama,openbot,github,telegram`) passou: 8 checks, 3 opcionais skipped (Jira/Phoenix/LiteLLM); Telegram autenticou sem envio e GitHub validou apenas leitura. O preflight das integrações requeridas passou; `DATABASE_URL`, `REGISTRY_DATABASE_URL`, `REDIS_URL` e `POSTGRES_PASSWORD` já estavam preenchidas. Defaults não secretos ausentes foram registrados; envio Telegram permanece opt-in (`TELEGRAM_SEND_ENABLED=false`). Nenhum valor secreto foi copiado para documentação.

**Novas evidências:** FAC-121 recebeu inbound live `/help` (message 8) e enviou resposta no mesmo thread (message 9) pela outbox redigida; isto não foi uma transição de demanda. Receipt sanitizado: `.runtime/artifacts/fac-121/inbound-help-reply.json`. FAC-130: UI live ligou Analyst a ContextPack read-only do commit `00d1a782ece691ad510fb4ef318590eea3540fff`, mas a resposta contradisse a decisão persistida e não trouxe citações path:line; a UI reteve corretamente. Mensagem classificada `READ`, sem proposta executável. GitHub #3 segue sem repetição após o broker; Telegram foi `/help`, não a frase FAC-130. Sem patch, result SHA, gates ou review. Evidência `.runtime/artifacts/fac-130/ui-context-eval.json`. FAC-121 e FAC-130 permanecem `in_progress`; detalhes e remaining_work estão no backlog. A ferramenta oficial `scripts/ai_acceptance.py` foi executada nas cinco primeiras: FAC-121/FAC-131 bloquearam por `AI_ACTIVITY_HAS_REMAINING_WORK`; FAC-130/132/133 por `AI_ACTIVITY_DEPENDENCIES_OPEN`. Não houve revisão nem aceite IA; ver `.runtime/artifacts/fac-130/first-five-ai-gate-check.json`.

## Como fechar uma atividade

Antes de mudar status para `done`, verificar todos os itens de saída no backlog e anexar evidência reproduzível da mesma execução: IDs de demanda/task/run, revisão aprovada e seu hash, base/result SHA, diff, contexto/prompt, gates aplicáveis, revisão independente e transcript redigido. Para passos com PostgreSQL, usar banco descartável vazio e legado quando aplicável. Registrar separadamente testes determinísticos, integração com fake, piloto live e autoria agêntica. Um tipo de evidência não substitui outro.

## Plano por atividade pendente

### FAC-121 — retorno seguro pelo Telegram

**Já há:** outbox persistente/idempotente, redaction, retry, reply-to, deep link e receipt sanitizado de entrega. Execução em PostgreSQL descartável: `.runtime/artifacts/fac-121/live-transition-delivery.json`; transição persistida enviada live uma vez e replay sem duplicata. Depois, um inbound `/help` real foi respondido na mesma thread (message 8 → 9), conforme `.runtime/artifacts/fac-121/inbound-help-reply.json`.

**Falta para fechar:** intake inbound de uma demanda e transição ligada ao ID da mensagem raiz original. O inbound recente foi somente `/help` e não acionou transição de negócio.

**Saída:** IDs do evento/outbox/mensagem, tentativa do worker, replay sem duplicata e transcript redigido.

### FAC-130 — mesma solicitação visual por UI, Telegram e GitHub

**Já há:** intake live pela UI e pela Issue #3 [`GitHub`](https://github.com/Matheuscruztj/agentic_factory_example/issues/3), importada pelo worker. Conversas Analyst ligadas às duas demandas foram persistidas. A integração de contexto para a demanda UI manual agora usa snapshot SHA autorizado e paths allowlisted; a saída ainda foi retida por citação inválida e contradição à decisão de produto. Evidências: `.runtime/artifacts/fac-130/journey-20261026.json`, `ui-context-eval.json` e artefatos de canal.

**Falta para fechar:** Telegram inbound da frase ainda não ocorreu; a resposta Analyst na UI continuou sem grounding e foi retida; GitHub ainda requer acesso seguro ao repositório externo. A repetição em thread UI limpo também foi retida, apesar do ContextPack compactado. O E2E visual local passou 2/2; não comprova autoria pelo agente. Repetir cada canal em baseline limpo, aprovar/delegar escopo rastreável, gerar patch com agente e validar cor/contraste/light/hover/focus/disabled/mobile com gates, screenshots e reviewer no SHA resultante. Issue #3 ficou aberta como origem do intake.

**Saída:** três runs ligados à mesma especificação literal, com diffs/reviews e evidência visual de cada baseline.

### FAC-131 — discovery e contrato de etiquetas

**Já há:** baseline Git sem tags; defaults de produto definidos pelo operador; EARS aprovado sob delegação explícita e persistido com hash/audit/outbox em `.runtime/artifacts/fac-131-134/fac131-delegated-ears-decision.json`. DAG de sete tarefas propostas persistido com dependências em `.runtime/artifacts/fac-131-134/fac131-delegated-dag.json`. Proveniência rotula ambos como `delegated_ai`, sem alegação humana nem autoria Factory. Contrato em `specs/demands/feature-tags-e2e/contract-review.md`.

**Falta para fechar:** Analyst live precisa entregar discovery grounded com citações e origem de conversa. A decisão e o DAG existentes substituem o trabalho administrativo sob delegação explícita, mas não comprovam autoria Analyst/Planner nem binding a thread Factory. Reconciliar esses artefatos com o runtime e executar persona Planner se o aceite exigir autoria.

**Saída:** mensagens verificáveis do Analyst, revisão aprovada/hash-bound, DAG persistido e teste de rejeição/alteração de escopo com histórico. Até cumprir, não iniciar TAG-DB/TAG-BE como autoria aceita.

### FAC-132 — execução agêntica de banco e backend para tags

**Já há:** componente Registry manual/atual com migrations, constraints e cenários de associação testados em PostgreSQL vazio e legado; evidência `.runtime/artifacts/fac-132/postgres-migrations.json`. Isso valida componente e dados, não autoria no fluxo Factory.

**Falta para fechar:** depois de FAC-131, executar TAG-DB e TAG-BE em worktrees isoladas via Factory, sem transplantar patch manual como prova; aplicar migration em PostgreSQL descartável vazio e populado; validar limites, duplicidade por caixa/acentos, IDs inválidos, associação, filtro, transações e downgrade/rollback. Vincular task/run, diff e gates aos SHAs de cada agente.

**Saída:** autoria, migration e revisão independentes com hashes por etapa; regressão de clientes legados.

### FAC-133 — integração frontend/backend de tags

**Já há:** E2E Registry sem mocks contra API/PostgreSQL passou 2/2; evidência `.runtime/artifacts/fac-133/`. Isso não demonstra geração agêntica paralela nem resolução de conflito.

**Falta para fechar:** após FAC-132, gerar TAG-FE e TAG-BE em worktrees distintas a partir do contrato aprovado; integrar em branch descartável e provocar conflito real, com child task de resolução e novo review. Executar API/UI/E2E sem mocks no PostgreSQL cobrindo reload, vazio, erro, mobile, acessibilidade e regressões de cadastro/telefone. Revisar SHA integrado.

**Saída:** tasks separadas, conflito e resolução rastreados, screenshots e gates no mesmo SHA de integração.

### FAC-134 — follow-up QA após entrega

**Falta para fechar:** depois de FAC-133, iniciar nova conversa/run real com `@qa` sobre cenário ausente; QA deve criar child task com escopo e aceite, o agente deve adicionar teste novo à entrega e executar regressão/review. Comparar snapshots antes/depois para demonstrar que requisito, demanda e tasks originais não foram alterados.

**Saída:** proposta aprovada quando aplicável, child task, teste novo, gates e prova de imutabilidade dos registros originais.

### FAC-135 — correção agêntica do bug de CPF

**Já há:** fixture sintética reproduz o bug no baseline; patch anterior do Ollama ficou no escopo e passou sandbox sem rede. A revisão independente anterior retornou `uncertain` (0.75), abaixo do aceite. Testes locais de fixture passaram dentro dos 5 testes FAC-135/136 desta continuação.

**Falta para fechar:** executar intake→Analyst→Planner→Backend→QA→Reviewer em run Factory autenticado e worktree limpa; exigir patch novo do agente, teste vermelho antes e verde depois, escopo permitido e hashes por etapa. Corrigir ou substituir a revisão contraditória; reviewer independente precisa citar linhas/evidências corretas e chegar a decisão aceitável.

**Saída:** `AgentRun`/`GateEvidence`, patch e regressão ligados à demanda/run/SHA, review independente consistente. Evidência anterior não substitui novo fluxo completo.

### FAC-136 — remediação agêntica de dependência

**Já há:** scanner em fixture encontrou 21 achados baseline, candidato intermediário deixou 18 e versão corrigida de fixture chegou a zero; testes de proposta, before/after e bloqueio de candidato insuficiente passaram. Evidência `.runtime/artifacts/fac136-runs/fac136-scan-881b07725c/run.json`.

**Falta para fechar:** ligar scanner→proposta do agente→patch em sandbox→scanner/testes/regressão em um run Factory autenticado, com advisory transitivo determinístico e evidência antes/depois. Confirmar ausência de high/critical no alvo. Não editar lockfile do projeto nem publicar sem aprovação própria; registrar separadamente qualquer decisão sobre escrita real.

**Saída:** patch/hash/review e scanner antes/depois rastreáveis no mesmo run; nenhum efeito remoto não aprovado.

### FAC-137 — recuperação após crash

**Já há:** kill do worker após interrupt persistido em PostgreSQL e retomada por processo novo, evidência `.runtime/artifacts/fac-137/postgres-process-restart.json`; fencing de lease, retry/DLQ e idempotência local testados. Nesta continuação, 8 testes locais passaram; 3 casos PostgreSQL foram excluídos por ausência de `DATABASE_URL` no shell.

**Falta para fechar:** executar matriz de falha em runtime real nos limites intake, discovery, HITL, inferência, patch, commit, integração e publicação simulada. Matar e reiniciar processo novo com PostgreSQL/checkpointer; injetar indisponibilidade Ollama/GitHub/Telegram/Redis, expiração de lease, retry e DLQ. Em cada ponto comparar IDs/contagens e provar ausência de duplicação de demanda/task/patch/approval/efeito externo, retomada de aprovação e fencing do worker antigo.

**Saída:** matriz por checkpoint, estado antes/depois, IDs e prova de reconciliação. Testes SQLite/fakes não contam como live.

### FAC-138 — observabilidade, retenção e restore

**Já há:** backup/restore descartável de Factory, Registry, checkpoint, OpenBot SQLite e artefatos, com smoke validado em `.runtime/artifacts/fac-138/restore-summary.json`.

**Falta para fechar:** correlacionar uma jornada real inteira no dashboard (demand/task/run/thread/checkpoint/model/tool/gates/review) e distinguir métricas medidas, estimadas e indisponíveis. Exercitar retenção, redaction e controle de leitura com marcadores sintéticos de segredo; confirmar que restore/GC preserva worktrees ativas e evidência essencial.

**Saída:** IDs correlacionados no dashboard, relatório de métricas, testes de retenção/redaction/RBAC e readback do restore.

### FAC-139 — aceite independente global

**Pré-condições:** FAC-130–138 concluídas; requisitos obrigatórios fechados e rastreados; skips e opcionais declarados. Não usar demos sintéticas como jornadas live nem gold labels sem proveniência humana.

**Falta para fechar:** auditar requisito→owner/task→run→artefato/SHA para todo pacote; executar reviewer IA independente contra hashes finais do pacote e backlog; emitir receipt HMAC apenas após aceite; validar assinatura/hash e regenerar scorecard. Se qualquer critério ou evidência faltar, manter `pending_ai_acceptance` e registrar o motivo.

### FAC-142 — calibração do Judge

**Já há:** harness e métricas locais estão instrumentados; quality-fast reporta judge-calibration verde como verificação do harness, não como calibração aceita. Ainda não existe gold humano independente suficiente.

**Falta para fechar:** curar slices anonimizados/adversariais e obter rótulos de referência humanos independentes com proveniência; executar comparações pareadas A/B, estilo/verbosidade, autoria e referências fabricadas. Medir falso negativo crítico, falsa reprovação, abstenção/cobertura, schema e custo contra os rótulos; definir/validar limites de aceite. Manter Judge advisory até esses limites passarem.

**Saída:** dataset/rótulos versionados e auditáveis, resultados reproduzíveis e decisão de promoção conforme política. Rótulo sintético ou gerado por modelo não serve como referência independente.

## Ordem de execução e bloqueios

1. Conciliar decisão EARS e DAG delegados do FAC-131 com discovery grounded de Analyst e proveniência de conversa; executar Planner Factory rastreável se requerido pelo aceite.
2. Executar FAC-132 → FAC-133 → FAC-134 usando o contrato congelado e autoria Factory rastreável.
3. Avançar FAC-135 e FAC-136 nas fixtures isoladas, paralelamente quando os paths não colidirem; não declarar completo sem dispatch e review exigidos.
4. Completar FAC-121 e FAC-130 nos limites de autorização de cada canal; distinguir evento live específico de mensagem/Issue sintéticas anteriores.
5. Completar FAC-137 com matriz de crashes; FAC-138 correlaciona jornadas concluídas e restaura o conjunto.
6. FAC-142 pode preparar harness e dataset, mas fechamento exige referência humana independente.
7. Executar FAC-139 por último; emitir receipt somente se todos os critérios obrigatórios passarem.

## Limites de autorização e classificação de evidência

- Trabalho local, fixtures, código, testes, análise e revisão podem prosseguir dentro dos escopos já autorizados. A solicitação de 2026-10-26 dispensa nova validação manual do operador para aceite técnico baseado em evidência; ela não converte teste local em jornada live nem supre decisão humana independente requerida como dado de referência.
- Aprovação de defaults de produto não é aprovação do requisito EARS concreto. A revisão EARS deve ser mostrada com hash antes da decisão Factory.
- Mensagem Telegram, Issue/comentário GitHub, publicação, merge, deploy ou escrita em lockfile remoto exigem a autorização específica prevista no backlog e no plano operacional; autorização para um teste sintético não se estende a uma jornada diferente.
- Classificar toda evidência como determinística, fake, live autenticada, autoria agêntica ou revisão humana/IA. Não promover um nível a outro. A calibração do Judge usa rótulos AI-provisional; classificar a decisão EARS/DAG como IA delegada e o Telegram como envio live com marcador sintético.
- Ao final de cada sessão, atualizar backlog, scorecard e este documento; deixar status `in_progress` se qualquer critério restante não tiver prova válida.


## Atualização FAC-130 — 2026-10-26 19:00Z

Grounding corrigido: o validador aceita `path:line` em Markdown sem permitir citações sem linha; pack CSS do snapshot foi compactado. A descoberta UI via browser e a GitHub #3 foram aceitas para escopo, com resolução delegada IA do conflito do token ausente para `--button-dark` local em `.submit-button`, sem tema global. Codex executou commits em worktrees limpas: UI `f5a725103f4fbec6e5dcb5e2288b95725b06fc28`, GitHub `93517a41cde8c78ddbd123bb36122b824b9b0a38`; build + Playwright 2/2 e review local Qwen2.5 approve em ambos, screenshots e logs sob `.runtime/artifacts/fac-130/agent-runs/`. Proveniência não é Factory worker e não há AgentRun/GateEvidence. Poll Telegram live retornou `imported=0`, offset estável; não houve inbound da frase. FAC-130 permanece `in_progress`, sem aceite/receipt global, dependência FAC-121 segue aberta.

Janela final de intake Telegram em 2026-10-26: polling por 60s/5s, 12 ciclos sem inbound (`imported=0`, offset `960529131`); worker encerrado. Nenhuma mensagem sintética ou resposta enviada. FAC-130 segue in_progress. Capturado 2026-10-26T19:02:34.983864+00:00.

## Atualização FAC-130 — 2026-10-26 19:32Z

As trilhas UI e GitHub agora têm execuções Factory separadas, ambas no baseline `00d1a782ece691ad510fb4ef318590eea3540fff`. UI: task `665ff850-6388-415d-9ad7-566eadfeab6b`, run `dbe38f01-e5b5-4003-ab74-fccb73b3e428`, SHA `724288e67e73d8f72c2067c323b5da595d1fcabc`. GitHub #3: task `a727ee55-647c-45ba-970e-291fa04353e4`, run `73aa83b1-b0c4-4413-ab13-bdaa9a520bda`, SHA `122a9b326ae574d031e3a4e87d57a2ae3fc67785`. Cada SHA tem build PASS, Playwright 2/2, `GateEvidence` e review Qwen3 aprovada. Receipts em `.runtime/artifacts/fac-130/agent-runs/` e resumo em `.runtime/artifacts/fac-130/current-implementation-update-20261026.json`.

O intake Telegram oficial fez um long poll de 25s: `imported=0`, offset `960529131`, nenhum outbound. Não criei evento sintético. FAC-130 permanece `in_progress` por falta de inbound Telegram e pela dependência FAC-121 aberta; nenhum aceite global foi emitido. Os dois commits locais não foram enviados nem integrados.
