# Rastreabilidade do escopo — 2026-10-24

Complemento posterior: os 13 requisitos `EVAL2-001–013` estão rastreados na
[extensão de evals/rubricas](../../specs/09-EVALS-RUBRICAS-E-HARNESS.md#10-rastreabilidade-da-extensão).
Eles acrescentam qualidade do processo de avaliação sem substituir as 43
exigências originais abaixo ou alterar seu estado de entrega.

Cobertura das **43 exigências** de [01-SPECIFY](../../specs/01-SPECIFY-ESCOPO.md). Estado observado pela [auditoria](../auditoria-projeto-2026-10-24.md); tarefas futuras no [backlog](../../specs/implementation-backlog.json). Nenhuma atividade desta matriz foi implementada pela análise.

`Componente` significa que a capacidade isolada existe; `parcial` indica ligação operacional, comportamento ou prova pendente. `Opcional` mantém o recorte original e não é PASS live. Nenhuma linha, sozinha, certifica uma jornada autônoma completa.

| Requisito | Estado / evidência atual | Lacuna e fechamento verificável |
|---|---|---|
| CORE-001 | Componente: monorepo apps/packages/workers e workspace uv | Imports/pacotes e reprodução do snapshot completo: FAC-100, 109. |
| CORE-002 | Produto funcional: Registry CRUD/UI, migrations, API e browser aprovados | Contrato/remoção de telefone, PostgreSQL por entrega e regressão: FAC-107, 116, 117, 132–133. |
| CORE-003 | Parcial: Python/uv, FastAPI, React/TS/Vite/Tailwind/Compose presentes | Tooling reproduzível, runners e adequação dos primitives/tokens shadcn previstos versus UI atual: FAC-100, 116, 125. Divergência de stack deve ser resolvida explicitamente, não presumida. |
| CORE-004 | Componente: preflight local/live e secrets isolados; rodada local atual PASS | Diagnóstico por perfil e health de processos/canais/modelos reais: FAC-106, 110, 122. |
| CORE-005 | Componente: Registry/manual/fakes não exigem provedores | Exercitar runtime direct e degradar GitHub/Telegram/serviços opcionais sem interromper manual: FAC-106, 110, 137. |
| CORE-006 | Parcial: labels, feedback e estados básicos na UI; E2E inicial PASS | Fluxos operacionais completos, teclado/mobile, estados assíncronos e anexos reais: FAC-107, 125, 126, 133. |
| INT-001 | Componente: demanda manual idempotente e normalizador externo | Evento comum aciona workflow, com origem/payload/histórico corretos: FAC-105, 114, 120, 122–123. |
| INT-002 | Parcial: GitHub cliente/poll/cursor com fakes | Corrigir término de página com PRs, compor worker, credenciais/repo e reconciliação live: FAC-122–123. |
| INT-003 | Parcial P1: intake Telegram e offset; evidência histórica de quatro demandas | Comandos, resposta vinculada, progresso, identidade e decisões: FAC-120–121, 130, 137. |
| INT-004 | Opcional P2: classes Projects/Jira com fake | Espelho Projects e worker/cursor Jira; card draft exige extensão explícita: FAC-128. |
| DISC-001 | Parcial: helper diferencia VERIFIED/UNKNOWN com inventário fornecido | Investigar código real no SHA e pedido livre, citar evidência e materializar perguntas: FAC-111–112, 131. |
| DISC-002 | Parcial: helpers de revisão e imutabilidade por serviço | EARS/cenários gerados, Q&A durável, versão aprovada e escopo final vinculados ao fluxo: FAC-103, 112–113, 131. |
| TASK-001 | Parcial: modelo de task, DAG e tasks criadas manualmente em testes | Planner gera tasks com owner/deps/paths/risco/testes/outputs e contrato front/back: FAC-113–114, 131–133. |
| TASK-002 | Componente DAG; estado parcial: transições não atômicas e conclusão sem evidência | CAS/locking, readiness com deps e precondições de done: FAC-101, 113–114. |
| TASK-003 | Parcial: claim/fencing existem; heartbeat running falha em probe | Renovação, commit/efeito com fencing e locks de paths entre processos: FAC-102, 114, 119, 137. |
| TASK-004 | Parcial: proposal/aceite/outbox persistidos, dispatcher com callback | Hash do escopo final, consumidor real e follow-up executável/idempotente: FAC-103, 114, 119, 134. |
| COL-001 | Parcial: conversa QA vinculada ao card pela API/UI | Seis personas, task binding, entrada Telegram/GitHub e ferramentas reais: FAC-120–126. |
| COL-002 | Parcial: intenção gera proposta inerte em casos conhecidos | Pedido português literal falha; parser semântico/estruturado e policy no caminho real: FAC-112, 124, 130. |
| COL-003 | Componente: contador de hops/calls/repetição testado | Integrar/persistir budgets e impedir loops entre processos/conversas reais: FAC-114, 124. |
| COL-004 | Parcial: follow-up preserva snapshot/histórico em fake | QA real gera e executa teste complementar sem replanejar toda a demanda: FAC-119, 134. |
| ORCH-001 | Parcial: adapters e builder LangGraph presentes | Compor OpenBot/conversas com workers/grafo concreto e modelo local: FAC-110, 114, 124. |
| ORCH-002 | Parcial: checkpointer PostgreSQL e interrupt; teste PG não executado nesta rodada | ApprovalRequest validado no resume, ciclo real e restart de processo: FAC-119, 137. |
| ORCH-003 | Parcial: slot de inferência PG e flags Ollama; scheduler fake | Todos os chamadores usam fila, locks por paths, concorrência medida e anti-starvation: FAC-102, 110, 114. |
| EXEC-001 | Parcial: worktree/patch/sandbox/integração testados isoladamente | Secrets aninhados, baseline completo, agente gerador, runners e integração real: FAC-104, 109, 115–117, 133. |
| EXEC-002 | Componente: ToolGateway read/propose com callbacks | Bridge real, identidade/quotas/timeouts/paths e ausência de shell irrestrito: FAC-104, 124. |
| EXEC-003 | Parcial: guardas em contratos de review/publisher | Resolver autorizações persistidas e payload final, proteger self-modification e publicar por transporte real: FAC-103–104, 118, 127. Merge continua humano. |
| CTX-001 | Componente: pack com fontes/SHAs/budget, sem retrieval operacional | Recuperar requisito/tarefa/commit/arquivos corretos e renovar bindings: FAC-103, 111, 124. |
| CTX-002 | Componente: registry e router 0–2 skills; quatro casos eval PASS | Aplicar a seleção/progressive disclosure ao agente e às ferramentas reais: FAC-110–111, 124. |
| CTX-003 | Componente: compactação, hash, TTL e leitura paginada de outputs | Ligar ao loop e redigir também persistência/leitura sensível; preservar evidência verificável sob retenção: FAC-105, 111, 138. |
| QA-001 | Parcial: scripts presentes, Python/builds/browser básicos PASS; segurança histórica | Rodar no worktree/SHA por task, cobrir ambos os frontends e integração PostgreSQL: FAC-116–117, 132–133, 136. |
| QA-002 | Parcial: schema/aggregate existem; compatibilidade permissiva e gate de outro run aceitos | Contrato 0/1/2 estrito, origem verificável e done condicionado a gates: FAC-101, 105, 117–118. |
| QA-003 | Parcial: fixtures e demos determinísticos existentes | Bugs/feature/vulnerabilidade devem ser resolvidos pelo agente, com testes ocultos e regressão reais: FAC-109, 130–136. |
| EVAL-001 | Parcial: schemas e métricas de fixtures | Runs/attempts autoritativos, first-pass/rework corretos e aceite por papel no dashboard: FAC-105, 129, 138. |
| EVAL-002 | Parcial: Judge separado e validator; calibração histórica de 3 casos provisórios | Revisão humana independente/calibração e uso complementar; benchmark futuro usa goldset maior: FAC-118, 129; LLMG-T13–15. |
| EVAL-003 | Parcial: dev/regression/holdout, 14 casos/10 labels provisórios | Rótulos revisados, exclusão do contexto, trials reais e proveniência dos resultados: FAC-109, 129, 139. |
| EVAL-004 | Parcial: registro autenticado de promoção/rollback | Validar experimento/gates existentes; runtime usa release aprovado e rollback afeta próxima execução: FAC-129. |
| OBS-001 | Parcial: middleware HTTP e helpers de correlação | Mesmo correlation/demand/task/run/thread entre intake, grafo, tools, modelo, gates e publicação: FAC-105, 124, 138. |
| OBS-002 | Componentes: métricas nativas, GPU, Compose Phoenix opcional | Instrumentar chamadas reais, medir fila/load/geração; Phoenix desligado não bloqueia: FAC-110, 138. |
| OBS-003 | Parcial: masking em packs/logging/summary | Aplicação uniforme no chat que monta prompt próprio, payloads/outputs completos, retenção e GC: FAC-104, 111, 124, 138. |
| HITL-001 | Parcial: decisões autenticadas com hash genérico de entidade | Hash deve incluir requisito/plano/paths/ação; decisão persistida governa execução/publicação: FAC-103, 108, 119, 121, 127, 139. |
| HITL-002 | Parcial: comentário/rejeição e interrupt isolados | Rejeitar/solicitar ajustes/esclarecer/retomar duravelmente com identidade válida por canal: FAC-112, 119–121, 125. |
| AUD-001 | Componente: audit/outbox/inbox/registry | Encadear entrada, plano, tools, patch, review, eval e efeito no run real, com integridade: FAC-105, 114, 119, 127, 138. |
| AUD-002 | Componente: EntitySnapshot e docs de exemplo | Snapshot Markdown de requisitos/decisões/aceites gerado a partir do estado persistido e vinculado à revisão aprovada: FAC-103, 112, 131, 138. |

## Aceites globais do escopo original

| Critério de sucesso de 01-SPECIFY §9 | Disposição atual / prova futura |
|---|---|
| Cadastro completo local com dados sintéticos | Base comprovada em testes; FAC-107 fecha telefone e FAC-116/133 validam a entrega integrada em PostgreSQL. |
| Demanda manual e GitHub com duas especialidades/deps/HITL | Não demonstrado com modelo real; FAC-112–119, 122, 125, 131–133. |
| @qa contextual e follow-up sem discovery integral | Fakes/contratos existentes; prova real FAC-124/134. |
| Paralelismo sem integração indevida de conflito | Helpers existentes; locks/child tasks/merge e reteste reais FAC-102/113/133. |
| Pausa/restart sem duplicar efeitos | Persistência histórica de checkpointer; prova do processo completo FAC-119/137. |
| Sandbox sem secrets/host/admin | Falha de secret aninhado reproduzida; fechar FAC-104/116 e red-team operacional. |
| Preflight auth vs indisponibilidade e saída segura | Componente disponível; perfil da stack e pilotos de modelos/canais FAC-106/110/122. |
| Gates críticos vetam entrega | Falta amarrar conclusão/proveniência; FAC-101/105/117/118. |
| Evals/feedback versionados, candidato reprovado não promovido | Falta origem dos trials, validação do experimento e consumo do release: FAC-129. |
| Sem cloud/SaaS/VPS/CI obrigatórios | Diretriz preservada. Direct e testes locais são o caminho principal; opcionais permanecem isolados. |

O pedido atual acrescenta profundidade operacional ao Telegram e exige prova com uma feature inédita. Essas entregas estão mapeadas em FAC-120–121 e FAC-130–139; não estão escondidas no status dos helpers antigos.
