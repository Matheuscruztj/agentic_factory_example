# Auditoria técnica do projeto — 2026-10-24

> Este relatório preserva o snapshot da auditoria inicial (160 atividades).
> A [pesquisa posterior de evals/rubricas](pesquisa-fabricas-agenticas-evals-rubricas-2026-10-24.md)
> acrescentou FAC-140–152, levando o backlog atual a 173. As conclusões e
> contagens abaixo são históricas. O reparo de quality gates em 2026-10-25
> acrescentou FAC-153 e atualizou estados; consultar [state.md](../state.md)
> para o planejamento consolidado.

**Conclusão:** existe uma base funcional de cadastro e uma coleção relevante de componentes da fábrica. Ainda não há evidência de uma fábrica operacional que receba um pedido livre e o execute, com LLM local, do discovery à entrega revisada pelos três canais. A principal lacuna é a composição operacional; também foram reproduzidas falhas de estado, integração, isolamento e proveniência das evidências.

Esta etapa fez análise, execução de verificações e planejamento. Não implementou funcionalidades, corrigiu código, criou commits, publicou PRs, enviou mensagens, consumiu updates Telegram ou assinou aceite. Os testes usaram dados sintéticos e ambientes temporários. Alterações de código já presentes no checkout foram preservadas.

## 1. Como interpretar o andamento

O backlog anterior registrava **96 done e 3 in_progress**. A revisão dos passos e critérios originais, confrontados com o código e a cobertura, resultou em:

| Conjunto | Concluído | Parcial/pendente | Futuro não iniciado |
|---|---:|---:|---:|
| 99 atividades originais | 47 componentes | 52 | 0 |
| FAC-100–139, fechamento operacional/E2E | 0 | 0 | 40 |
| LLMG-T01–T21, melhoria opt-in | 0 | 0 | 21 |
| Total do backlog revisado | 47 | 52 | 61 |

**49 atividades antes concluídas foram reabertas**, além das três pendências humanas já conhecidas. Isso não elimina a implementação existente: aplicação de patch, contrato de review, mecanismo de retry e testes fake continuam úteis. A reabertura registra que o componente não cumpriu todos os passos do aceite declarado. Exemplo: aplicar um patch fornecido pelo teste não demonstra um implementer que gera código com LLM.

Não interpretar essas contagens como percentual de produto concluído: tarefas têm tamanhos diferentes e integrações opcionais estão identificadas separadamente. `done` de componente também não equivale a UAT humano, execução live atual ou autonomia demonstrada.

- [Disposição individual das 99 atividades](auditoria/atividades-2026-10-24.md).
- [Rastreabilidade dos 43 requisitos originais](auditoria/rastreabilidade-2026-10-24.md).
- [Backlog estruturado e dependências](../specs/implementation-backlog.json).
- [Plano de fechamento e jornadas](../specs/08-PLANO-CONCLUSAO-E2E.md).
- [Estado anterior preservado](auditoria/estado-anterior-2026-10-24.md).

## 2. Método e limites da evidência

Foram inspecionados os documentos 01–07, as fases P00–P14, a melhoria LiteLLM e sua configuração, runbooks, ADRs, contratos do cadastro, código de API/UI, Task Engine, runtime, workers, integrações, qualidade, evals e testes. O checkout observado está em `main`, HEAD `00d1a782ece691ad510fb4ef318590eea3540fff`, com muitas alterações preexistentes e arquivos de implementação ainda não versionados.

Os achados distinguem quatro níveis:

1. **Executado nesta auditoria:** comando ou sondagem registrada, com resultado concreto.
2. **Inspeção do código:** responsabilidade e ligação identificáveis; ausência de consumidor verificada por busca de usos e leitura dos entrypoints.
3. **Histórico local:** artefato anterior encontrado em `.runtime`, útil como histórico, sem recertificação do estado atual.
4. **Planejado:** critério de aceite futuro, sem afirmar que já foi executado.

Evidências locais desta análise: `.runtime/audit-2026-10-24/`. A pasta é ignorada pelo Git; este relatório preserva conclusões e contagens, mas reprodução em outra máquina exige arquivar/exportar as evidências sanitizadas. Não há garantia de reprodução apenas a partir do HEAD atual, porque parte do código está fora dele; FAC-109 trata essa lacuna.

## 3. Validação executada

| Verificação | Resultado | O que comprova / limite |
|---|---|---|
| `uv run --frozen pytest -q` | 124 passed, 2 skipped | Componentes, contratos e integrações de teste. Os dois testes PostgreSQL dependem de `DATABASE_URL`, ausente no ambiente desse processo. |
| `uv run --frozen ruff check apps packages workers scripts tests` | PASS | Lint do conjunto informado. |
| mypy com os targets de `scripts/quality_python.py` | PASS, 28 arquivos | Não é typecheck integral de todo o monorepo. |
| Factory Web: Vitest / ESLint / build TypeScript+Vite | PASS, 3 testes | Build e testes atuais, sem comprovar workflow operacional. |
| Registry Web: Vitest / build TypeScript+Vite | PASS, 3 testes | Contrato do cliente e build atuais. |
| Playwright `factory.spec.ts` | PASS, 1 teste | Interface com respostas de API simuladas; não comprova PostgreSQL/agentes. |
| Playwright Registry | PASS, 1 teste | Cadastro/edição/desativação pela UI e API local temporária com SQLite. |
| `scripts/evaluate_context.py` | PASS, 4 casos | Precisão/recall/skills/budget no pequeno conjunto determinístico fornecido. |
| `scripts/validate_eval_datasets.py` | PASS, 14 casos em 5 datasets | Hashes íntegros; **10 rótulos provisórios**, ainda sem revisão humana independente. |
| `scripts/gen_client.py --check`, via `uv run --frozen` | ERRO de import | `ModuleNotFoundError: context_engine` no comando documentado. |
| Mesmo drift check com paths dos pacotes explicitados | FAIL | `generated client is stale`; corrigir o import não resolve o drift. |
| Preflight `--mode local --require core,postgres,redis` | PASS, 6 checks / 4 skipped | Validação sintática/configuração, não autenticação nem disponibilidade live. |
| Doctor e sondagem HTTP local | Stack incompleta | Factory API/PG/Redis/Ollama alcançados; Registry/UIs/OpenBot no host indisponíveis naquele instante. |

O Playwright do Registry iniciou seus próprios serviços temporários e os encerrou. O smoke `factory-live.spec.ts`, que cria demanda e aprovação na base operacional, não foi repetido. Scans completos de segurança, calibração com inferência e experimentos de prompts não foram repetidos nesta análise; os relatórios verdes encontrados são históricos. Não há declaração de “todos os gates atuais aprovados”: o drift OpenAPI está reprovado e faltam aceites operacionais.

Foram preservados os bytes anteriores de `tsconfig.tsbuildinfo` durante os builds. Logs dos comandos e as sondagens adicionais estão na pasta de evidências da auditoria.

## 4. Falhas reproduzidas fora da cobertura existente

As sondagens usaram diretórios/bancos temporários e adapters fake quando necessário. Não escreveram na base operacional nem iniciaram containers de execução de agentes.

| Achado | Reprodução / consequência | Correção planejada |
|---|---|---|
| A01 — Intenção em português | `alterar cor do botao para o tema dark` retorna `ask`, sem proposta. O regex de diretiva não cobre esse infinitivo. | FAC-112, 120, 124, 130 |
| A02 — Heartbeat | Após reservar task e mudar para `running`, `heartbeat` retorna `LEASE_LOST`, pois só aceita `leased`. Tasks longas podem perder lease. | FAC-102 |
| A03 — Versão não atômica | Duas sessões SQLite carregam versão 1; a primeira faz `triage`, a segunda ainda faz `cancelled`. Restam dois eventos com `expected_version=1` e versão final 2. O check em Python não é compare-and-swap SQL. Confirmar também concorrência PostgreSQL no aceite futuro. | FAC-101 |
| A04 — Conclusão sem qualidade | Transições válidas `running → review → done` aceitam task sem resultado e sem critérios; não verificam evidências/gates. | FAC-101, 105, 117 |
| A05 — Paginação GitHub | Página bruta com 100 itens, incluindo 1 PR, retorna 99 Issues. Worker usa esse comprimento filtrado para parar; não busca Issue da segunda página. | FAC-122 |
| A06 — Aceite final permissivo | `build_report` retorna `accepted` com atividade pendente e JSON contendo reviewer/data/signature_ref arbitrários, apenas não vazios. Ausência de assinatura é bloqueada; autenticidade e completude não são verificadas. | FAC-108, 139 |
| A07 — Gates de outro run | Quatro contratos PASS com `run_id=different-run` são aceitos pelo agregado solicitado para outro run. Não há vínculo obrigatório ao SHA/tree. | FAC-105, 117 |
| A08 — Secret aninhado | `config/.env` sintético atravessa a validação de `run_sandboxed` e chega à chamada de lançamento mockada. A busca de arquivos sensíveis só inspeciona a raiz; symlinks têm checagem separada. Nenhum container foi iniciado nessa sondagem. | FAC-104, 116 |
| A09 — Telefone não pode ser removido | PATCH só com `phone:null` retorna 400 e preserva o valor; `phone:""` retorna 422. Omitir/null/vazio não têm contrato útil de limpeza do opcional. | FAC-107 |

Artefato: `.runtime/audit-2026-10-24/diagnostic-probes.json`. Todos os achados acima possuem trabalho pendente; nenhum foi corrigido nesta fase.

## 5. O que funciona atualmente

**Produto alvo:** Registry tem CRUD, busca, unicidade normalizada, desativação lógica, migrações, telefone opcional, UI e testes. O teste de navegador executado passou. A semântica de remoção do telefone precisa de correção; o documento de domínio ainda o descreve como adiado. CPF é helper/fixture sintético, não campo integrado ao cadastro.

**API/UI da fábrica:** autenticação local, CSRF, intake manual, listagem/detalhe, tarefas/dependências, decisões de aprovação, stream SSE, feedback/evals e dashboard de observabilidade têm implementação. A UI permite **simulação local**, e o chat oferece **QA**. Falta UI para discovery/refinamento/plano, execução real, aceitação de proposta, inspeção de diffs/gates/runs e demais personas. O client gerado não corresponde ao OpenAPI atual.

**Peças de execução:** há DAG, máquina de estados, leases, outbox/inbox, checkpoints PostgreSQL, retry/DLQ, criação de worktrees, aplicação de patch, sandbox Docker, integração de branches e validação de review/publicação. São peças reutilizáveis; os achados A02–A08 mostram que guardas ainda precisam ser fechadas antes de unificá-las.

**Contexto/qualidade:** manifests, skills, roteamento, packs, compactação, schemas e runners possuem cobertura. Os scripts de qualidade existem, mas precisam ser executados por task/run no worktree correto, preservar integridade e vincular resultado ao commit entregue. Um runner que só lê returncode não comprova o contrato JSON e os artefatos esperados.

## 6. Onde o fluxo se interrompe

| Entrada / etapa | Implementação observada | Interrupção atual |
|---|---|---|
| Demanda pelo frontend | POST demanda/revisão; consulta, aprovação e SSE | Não aciona discovery/plano/worker real. Botão operacional executa `run-fake`. |
| Telegram | Allowlist, getUpdates, mapper, persistência de demanda e offset | Cada mensagem vira demanda do tipo question. Sem comandos, associação de respostas, envio de progresso ou retomada do trabalho. |
| GitHub Issue | Cliente e funções de polling/reconciliação | Sem entrypoint supervisionado/configuração completa; paginação falha com PRs; sem prova live ou continuidade até execução. |
| Card GitHub Projects | Classe para mutation de status | Não é intake de card. Card vinculado a Issue pode usar intake da Issue; draft é explicitamente fora do MVP original. |
| Discovery/refinamento | Helpers com inventário/texto fornecidos | Não existe investigação operacional de pedido livre, EARS gerado, conversa de esclarecimento e persistência de suas decisões. |
| Planner | Manifest e validador DAG | Falta agente que produza plano persistido/executável para backend/frontend/QA. |
| Grafo de task | `build_task_graph` recebe callbacks | Busca de usos encontra construção em teste fake, sem composição produtiva ligada ao intake/API/worker. |
| Implementer | `apply_scoped_patch` recebe patch pronto | Falta loop de inferência/leitura/edição/teste/commit com orçamento e correção limitada. |
| Follow-up | Aceite cria task/outbox; dispatcher recebe callback | Não há consumidor contínuo nem subworkflow QA real. |
| Review/PR | Contratos de review e Protocol de transporte GitHub | Falta reviewer concreto e transporte que resolva aprovações persistidas e reconcilie efeitos. |
| Observabilidade | Middleware e helpers instrumentados em testes | Falta cadeia completa dos mesmos IDs entre todos os serviços/etapas reais. |

Os usos foram conferidos em `apps/`, `packages/`, `workers/` e `scripts/`, além dos testes. Principais referências: [demands.py](../apps/factory-api/src/factory_api/routers/demands.py), [task_graph.py](../packages/agent-runtime/src/agent_runtime/workflows/task_graph.py), [implementer.py](../packages/agent-runtime/src/agent_runtime/implementer.py), [followups.py](../workers/src/factory_workers/followups.py), [telegram_poll.py](../workers/src/factory_workers/telegram_poll.py) e [Dashboard.tsx](../apps/factory-web/src/features/dashboard/Dashboard.tsx).

## 7. Autonomia: definição atual e desejada

O escopo original exige execução local independente **dentro de escopo autorizado**, com Task Engine como autoridade. Ele também exige HITL para ambiguidade material, mudança de escopo, publicação, merge, policies/secrets e promoção de prompts. O pedido de autonomia não foi usado para eliminar essas restrições silenciosamente.

Depois de requisito/plano/paths/budget autorizados, a fábrica deve investigar detalhes técnicos, gerar tarefas/patches, chamar Ollama, executar testes, corrigir dentro do limite, integrar e preparar revisão **sem o operador executar comandos ou copiar patches**. Quando precisar de decisão de produto, deve perguntar no canal e retomar. Publi­cação e merge seguem decisões próprias; merge/deploy não são automáticos no MVP. Um pedido no alvo padrão `customer-registry` não autoriza editar a própria fábrica em execução.

“Rodou modelo local”, “OpenBot respondeu” e “tests verdes” são provas diferentes. O aceite precisa demonstrar sua ligação no mesmo run, até mudança funcional inédita no produto e pacote de evidências revisável.

## 8. Validação das definições de escopo e documentação

- `01-SPECIFY` e `02-DESIGN` continuam coerentes no objetivo single-repository, local-first, com HITL. São referência desejada; não inventário de implementação.
- `03-TASKS` descreve 99 atividades com passos mais amplos que vários testes existentes. Caminhos de testes ali são frequentemente **previstos** e não existem literalmente; o backlog revisado preserva esses comandos em `original_validation` e aponta a cobertura real em `audit`.
- O índice de fases dizia P05–P09 não iniciadas, enquanto os arquivos individuais e `state.md` diziam concluídas. As fases e seus checkboxes foram reconciliados com o resultado desta auditoria.
- `state.md` dizia que restavam só três revisões humanas e repetia dependências Telegram já resolvidas. Foi substituído por controle atual de pendências, preservando o texto anterior como histórico.
- `docs/integration-validation.md` ainda dizia Ollama/OpenBot desativados, apesar das flags atuais habilitadas. Agora aponta à sondagem datada; “habilitado” continua distinto de “alcançável”.
- `docs/registry-domain.md` adiava telefone; a documentação foi marcada como anterior ao contrato implementado, com semântica de remoção explicitamente pendente.
- `04-VARIAVEIS` misturava variáveis de referência e consumidas, dizia que `.env` não tinha credenciais e omitia a allowlist de chats exigida pelo worker. Foi marcado como catálogo de referência, com diferenças confirmadas; alinhamento executável está em FAC-106.
- `05-RUNBOOK` ainda dizia que várias peças não existiam, citava `validate_task_plan.py` inexistente, path `docs/03-...` e `quality_web.py` antigo. Comandos e inventário foram corrigidos documentalmente; instalação/boot completo continuam pendentes, sem afirmar que os comandos de agente já existam.
- `06-LOCAL-CODING-LAB` continua opcional e não implementado. Seu benchmark comum foi rastreado às tarefas LLMG-T04/T08–12 e ao runtime FAC-110/115/116; comparação IDE/Continue/Aider é uma extensão opt-in explícita de T10, sem criar outro client/runner paralelo.
- `info-projeto.md` está vazio. Não foi tratado como definição de escopo: o índice de entrada foi preenchido com links para as fontes reais.
- Os relatórios anteriores de aceite/qualidade não demonstram autoria das mudanças por agentes. FAC-093 precisa de fechamento técnico e prova E2E, além de revisão humana.
- Falta garantia de imutabilidade/proveniência entre aprovação, revisão, plano, contexto, Git SHA e resultado. Um hash de JSON de contexto não pode ser usado como commit-base de Git.

## 9. Melhoria futura LiteLLM / benchmark

O [documento de melhoria](../specs/melhoria/08-LITELLM-GATEWAY-BENCHMARK-CODING-JUDGE.md) é proposta, não serviço instalado. Não foram encontrados adapter unificado, Compose LiteLLM, variáveis do gateway, registry de candidatos, persistência BenchmarkRun/Trial, CLI do harness ou comparação direta/proxy. As **21 tarefas LLMG-T01–T21** foram incorporadas como futuras.

Há reuso parcial de Judge, eval schemas, comparador de observações de prompts, gates e métricas Ollama/GPU. Isso reduz implementação futura, mas não satisfaz os aceites do módulo. A calibração histórica de três casos não atende goldset de pelo menos vinte amostras humanas nem sustenta ranking de modelos.

O desenho é adequado ao problema se preservar direct, execução serial na GPU de 8 GB, modelo/digest fixados, nenhuma promoção automática e qualidade subordinada aos testes. Ajustes de planejamento necessários estão no plano: um único adapter compartilhado com FAC-110; benchmark direct sem depender da implantação do proxy; runbook sem depender de dashboard; paths reais `src/`; campos nativos Ollama possivelmente indisponíveis via proxy; TTF­T apenas em streaming e amostras insuficientes classificadas `inconclusive`.

Nenhum vencedor, ganho de qualidade, throughput ou overhead foi medido nesta análise. Não é necessário implantar LiteLLM para terminar primeiro o fluxo com Ollama direto.

## 10. Próximo fluxo recomendado

Executar **M0 / FAC-100–109** antes de ampliar integrações. Essa onda fecha as falhas reproduzidas e torna origem/estado/autorização verificáveis. Depois M1 liga o runtime local; M2 conclui canais/UI; M3 prova alteração visual, feature inédita, correções, follow-up, recuperação e UAT. Os critérios e dependências concretos estão nas [novas fases](../specs/fases/README.md).

O projeto só deverá ser declarado entregue quando a matriz de requisitos/jornadas selecionada tiver evidência do fluxo real, sem substituir execução por fixtures já implementadas ou assinatura isolada.
