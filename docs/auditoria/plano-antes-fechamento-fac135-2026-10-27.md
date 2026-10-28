# Fechamento das pendências atuais (11 atividades)

> Decisão vigente do operador em 2026-10-27: FAC-142 usa casos sintéticos com resultado determinístico e revisão independente por IA. Exigências anteriores de labels humanos dessa atividade foram substituídas; não se alega calibração humana. O histórico permanece identificado.
Revisão documental: **2026-10-27**. Foram inspecionados specs, backlog, estado,
código dos pontos de integração e artefatos locais citados. Não houve execução
de novas jornadas, inferências, testes de produto ou envio externo nesta revisão.
Resultados de 2026-10-26 abaixo são evidências históricas inspecionadas, não
recertificação da instalação ou do banco em funcionamento.

Este é o roteiro da próxima fase. O [backlog](implementation-backlog.json)
mantém IDs, estados, dependências e critérios; o [state](../state.md) é o handoff
curto. Escopo/invariantes continuam em 01/02 e no [plano E2E](08-PLANO-CONCLUSAO-E2E.md).
Em conflito entre relatos de execução antigos, conferir o artefato e a versão
mais recente, sem apagar ou reclassificar o histórico como sucesso.

## 1. Diagnóstico: por que os testes passam e o trabalho não acaba

O backlog atual contém **174 atividades: 163 `done`, 11 `in_progress`, zero
`todo`**. As abertas são FAC-121 e FAC-130–139. FAC-142 passou a `done` com
revisão independente aprovada e não integra a lista atual de abertas. Isso não
significa 94% de autonomia comprovada:
`done` é um marco de componente. Há **90 itens `done` com
`audit.completion_tasks`** apontando para integrações/aceites complementares.
Essas referências não são 90 novas tasks nem motivo para reimplementar tudo;
precisam de uma disposição verificável no pacote final.

Os problemas concretos encontrados:

1. **Ligação operacional incompleta.** `build_task_graph` recebe callbacks;
   `implementer.py` aplica patches, mas não é um executor completo;
   `followups.py` exige `invoke_subworkflow` fornecido pelo chamador. A busca em
   `apps/`, `workers/` e `scripts/` não encontrou composição produtiva desses
   pontos para consumir automaticamente plano/outbox e executar a jornada.
   Existem provas e scripts locais em `.runtime`, que não substituem um
   processo versionado, instalável e reiniciável.
2. **Registro de run não prova autorização.** Os receipts recentes de FAC-130
   UI e GitHub contêm `run.requirement_decision="proposed"`. `create_run` confere
   vínculo da revisão à demanda, mas não sua aprovação; as transições de task
   inspecionadas também não estabelecem essa aprovação/plano final. É necessário
   conferir a trilha anterior ao efeito e proteger a entrada de execução. A
   transição `done` inspecionada consulta AgentRun completed e campos de review
   no resultado, sem conferir ali o conjunto de GateEvidence do SHA/attempt;
   fechar essa verificação no domínio, não só na orquestração.
   Aprovação posterior não autoriza retroativamente o run.
3. **Documentos se contradizem.** P18 ainda dizia que FAC-132/133 não tinham
   começado; P16 mantinha FAC-153 parcial; o índice ainda contava 14 abertas;
   o contrato de tags pedia decisão EARS já registrada sob delegação. O estado
   acumulava relatos antigos e novos da mesma tentativa.
4. **Testes repetidos não cobrem o critério faltante.** Registry funcionando,
   `quality-fast` verde ou scanner de fixture não provam intake → aprovação →
   despacho → implementação → gates → review → retorno da Factory.
5. **A jornada Telegram ainda não concluiu.** Foi recebida uma demanda visual
   real e seu ACK de registro foi enviado no root original, mas ainda não houve
   decisão aprovada, transição de negócio, execução nem retorno de resultado.
   FAC-142 segue a decisão vigente do operador: casos sintéticos com
   resultado determinístico e revisão independente por IA, sem alegação de
   calibração humana.
6. **Qualidade e aceite final ainda têm trabalho próprio.** O full run histórico
   `20261026T171041Z-c865e753` não ficou verde: Sonar reprovou cobertura nova
   de 61,5% contra 80%. O wrapper registrou `error/2`; isso não transforma uma
   reprovação de cobertura em indisponibilidade de serviço.
7. **Assinatura global ainda não tem emissão operacional demonstrada.**
   `ai_acceptance.py` emite receipt de uma atividade; `acceptance_report.py`
   verifica um receipt com escopo `all-required-activities`. A CLI de atividade
   não emite automaticamente esse pacote global. O hash do backlog muda ao
   editar status/docs: assinar antes da versão final invalida o aceite global.
8. **Ciclo de conclusão em FAC-139.** O relatório exige todos os obrigatórios
   `done`, incluindo FAC-139, para aceitar receipt global; o aceite de FAC-139
   exige esse receipt. A CLI por atividade não resolve isso. O protocolo precisa
   revisar um snapshot candidato e só ativá-lo depois do aceite, sem marcar
   sucesso no backlog oficial para tentar destravar a revisão.

## 2. O que significa terminar 100%

Para **as 11 atividades abertas**, terminar significa cumprir os critérios existentes,
registrar provas válidas, aceitar cada atividade e obter scorecard
`accepted_by_ai` no snapshot final. Não significa ativar todo opcional ou provar
confiabilidade estatística ilimitada. Jira/Projects/webhooks, cloud, CI/deploy,
expansões CSV/paginação e gateway não selecionado ficam fora do caminho crítico.

FAC-142 tem `release_scope=eval_hardening` e é obrigatório no relatório global.
Seu status atual no backlog é `done`, com avaliação sintética determinística,
`human_agreement=null`, `promotion_eligible=false` e receipt de revisão
independente aprovado. Reutilizar essa evidência; não repetir nem reabrir a
atividade, salvo se o verificador encontrar hash/receipt inválido. Isso não
alega calibração humana nem promoção do Judge.

Revisão técnica por IA segue [a política vigente](../docs/ai-acceptance-policy.md).
Em FAC-142, a revisão independente já registrada verifica dataset, oráculo,
resultados e conclusão por slice, sem ser apresentada como rótulo humano.
Aprovações já delegadas continuam válidas dentro de seu conteúdo/hash e de sua autorização;
não solicitar outra decisão idêntica apenas por troca de sessão/persona.

## 3. Preparação comum C0 — fazer uma vez antes das demos

C0 é trabalho compartilhado dentro de FAC-121/130/131/137/139, cobrindo ligações
dos componentes FAC-103/105/114–119/124–127/129. **Não cria novos IDs FAC.**
Registrar uma única implementação e referenciá-la nas jornadas beneficiadas.

### C0.1 — Congelar ambiente, baseline e critérios

1. Inspecionar `git status --short`, preservar o checkout sujo e inventariar
   worktrees existentes. Criar checkout de execução isolado; não usar reset,
   clean, stash global ou integração automática dos commits anteriores.
2. Separar **snapshot do controlador** (Factory atual) do **baseline do produto**
   `00d1a782ece691ad510fb4ef318590eea3540fff` (Registry sem tags/alteração visual).
   Rodar ferramentas da Factory atual não autoriza copiar tags prontas para o
   baseline. Dependências do runner ficam preparadas fora do contexto de solução.
3. Congelar versão dos modelos/digests, lockfiles, ferramentas, suites, scopes,
   limites e matriz de critérios. Confirmar instalação sem depender apenas do
   `pythonpath` de pytest. Não baixar modelos automaticamente.
4. Revalidar somente serviços requeridos; salvar resumo seguro, sem imprimir
   `.env`. Comandos existentes, a executar na próxima fase:

   ```bash
   uv sync --frozen --all-packages --group api
   make preflight
   make doctor-factory
   make doctor-agent
   uv run --frozen --all-packages --group api python scripts/validate_env.py --env .env --mode live --require core,postgres,redis,ollama,openbot,github,telegram
   ```

5. Reservar PostgreSQL descartável e portas próprias. Doctor e preflight não
   provam execução do coordenador. Não regenerar secrets nem presumir que os
   serviços disponíveis ontem continuam ativos.
6. Registrar antes de iniciar pilotos: destino/ação já autorizados, origem do
   inbound Telegram, versão/digest e limites da avaliação sintética FAC-142,
   reviewer independente por IA e perfil final de qualidade. Falta de inbound
   bloqueia o piloto Telegram; falta do pacote/oráculo bloqueia FAC-142, não todo
   trabalho local.

### C0.2 — Compor e versionar o caminho operacional

1. Mapear eventos reais de intake, revisão/plano aprovado e follow-up aceito para
   consumidores concretos. Registrar nomes/event IDs efetivamente encontrados;
   não criar uma segunda engine paralela à do Task Engine.
2. Versionar o dispatcher/coordenador e seu entrypoint, reaproveitando os módulos
   existentes. Paths candidatos novos: `workers/src/factory_workers/runner.py`
   e `scripts/factory_worker.py`; confirmar o layout antes de criá-los. São
   entregas necessárias, **não comandos já disponíveis**.
3. Antes de claim/execução/efeito, exigir revisão aprovada, decisão de escopo
   aplicável, plano final com hash, base existente, paths, dependencies, lease e
   fencing. Alteração de payload invalida autorização. Rejeitar `proposed`,
   aprovação stale, callback fictício e transição direta sem provas. Antes de
   `done`, conferir gates obrigatórios persistidos do mesmo run/attempt/SHA e
   review verificável desse SHA, sem aceitar apenas campos declarados em JSON.
4. Compor Analyst/Planner e executor local → contexto autorizado → Ollama →
   worktree/sandbox → patch/commit → quality runner → reviewer independente →
   resultado. Persistir AgentRun/GateEvidence e estado pelo domínio; não apenas
   inserir registros equivalentes depois de executar scripts manuais.
5. Conectar checkpoint/interrupt/resume, cancelamento, retries, DLQ e outbox ao
   processo. Tratar crash entre efeito e recibo por chave estável/reconciliação.
   Implementar handlers usados nas jornadas; `/responder`, `/agente` e
   `/cancelar` têm gramática, mas o handler Telegram inspecionado ainda retorna
   indisponível para esses casos. Alternativa de UI só vale se o contrato do caso
   permitir e o vínculo ao canal original for mantido.
6. Fixar orçamento por run antes de inferência: passos, tokens, tempo, tentativas
   de código e de transporte. Reusar limites existentes; se ausentes, propor
   configuração explícita. Os defaults inspecionados são 3 hops/20 calls/1
   repetição em `CollaborationBudget`, timeout 180s/contexto 8192/saída 2048 no
   `OllamaAdapter`; precisam de aplicação/persistência no run, não só instância
   em memória. Registrar também teto de correções, tempo e tokens totais.
   Exaustão termina com diagnóstico, não loop infinito.
7. Provar um slice por entrada normal/API autenticada, sem chamada manual a
   helpers: approval permite execução; ausência/mudança de approval veta;
   gate vermelho veta; retry não duplica efeito. Processo novo deve retomar.
   Esse mesmo slice pode compor FAC-130/131/137, evitando demo extra sem propósito.

**Saída C0:** comando documentado, supervisor/health do worker, eventos e IDs,
provas de autorização e retomada, orçamento aplicado e artefatos reproduzíveis.
Sem isso, novas demos tendem a repetir o mesmo limite de integração.

### C0.3 — Preparar o fechamento da qualidade e da assinatura

1. Associar os 90 `audit.completion_tasks` históricos aos critérios atuais:
   realizado com prova; coberto por uma das 11 atividades abertas; ou opcional fora do perfil,
   com fundamento. Não interpretar esses vínculos como novas arestas da DAG.
2. Verificar em particular FAC-127 (aprovações/transporte de publicação), FAC-129
   (trial real/prompt ativo/rollback), e os critérios selecionados de P20 ainda
   descritos como drafts. Código/teste de componente não comprova experimento.
   Registrar o que falta no checklist de FAC-137/138/139, sem fechar por rótulo
   `done` e sem ampliar o produto com features de pesquisa não selecionadas.
3. Corrigir cobertura Sonar com testes de comportamento relevantes nas linhas
   alteradas ou corrigir paths/importação da cobertura se o relatório provar
   erro de medição. Preservar mínimo 80%, inclusões e detecção de violações.
   Não excluir arquivos para reduzir artificialmente o denominador.
4. Definir um emissor global versionado com **snapshot candidato**: aceitar um
   backlog final proposto em `.runtime`, sem alterar o backlog oficial pendente;
   revisar pacote/bytes exatos e publicar esses mesmos bytes apenas após aceite
   verificável. Para FAC-139, essa revisão global é também o aceite da atividade,
   eliminando a exigência circular de receipt antes do próprio receipt. Reaproveitar
   HMAC/validações de atividade, sem simular decisão. Comprovar
   rejeição de artefato adulterado, atividade obrigatória omitida, gate errado,
   reviewer igual ao executor e backlog alterado. O verificador atual compara
   IDs do manifest entre si; fazê-lo comparar também o conjunto obrigatório
   derivado do backlog/perfil, sem aceitar atividade omitida por manifest reduzido.
   Não escrever receipt manual
   simulando revisão que não aconteceu.

## 4. Ordem finita da próxima fase

| Etapa | Atividades | Condição de saída |
|---|---|---|
| A | C0 e revalidação de FAC-142 concluída | Caminho operacional definido; verificar receipt/hash FAC-142 junto ao pacote final sem repetir a avaliação válida. |
| B | FAC-121 → FAC-130 | Inbound Telegram já coletado; completar decisão, transição, retorno e terceira rodada; auditar reaproveitamento UI/GitHub. |
| C | FAC-131 → FAC-132 → FAC-133 → FAC-134 | Discovery e plano aprovados; tags geradas, integradas e follow-up real. |
| D | FAC-135 e FAC-136 | Bug e remediação passam pelo mesmo executor, em fixtures sem solução. |
| E | FAC-137 e FAC-138 | Matriz de falhas, correlação, retenção e restore com evidência do runtime. |
| F | FAC-139 | Dependências obrigatórias, incluindo FAC-142 já concluída, qualidade final e receipt global válidos. |

As etapas B/C/D podem intercalar tarefas sem conflito de paths; isso não exige
agentes paralelos nem inferências simultâneas. TAG-FE pode começar com contrato
congelado enquanto TAG-DB/BE avançam; FAC-133 só é aceita após FAC-132.

## 5. FAC-121 — falta uma demanda inbound com transição e retorno

**Reusar:** outbox/allowlist/redaction/retry/deep link existentes;
`.runtime/artifacts/fac-121/live-transition-delivery.json` comprova transição de
origem sintética, e `inbound-help-reply.json` comprova `/help` real com reply.
Nenhum dos dois, isoladamente, cobre demanda inbound → transição de negócio.

1. **Evidência já coletada (2026-10-27):** um ciclo `telegram_intake_worker.py --once`
   importou duas mensagens. O inbound exato da solicitação visual virou demanda
   `bc16a11c-f654-4738-98f1-45daa2387faa`, external root `464393985:11`; texto
   original e payload hash estão no EventInbox e o ACK de registro tem outbox
   publicada em reply ao root. A outra mensagem importada, raiz `464393985:10`,
   contém texto diferente e demanda `f5611522-b85e-4452-9e7f-19b708114c68`; não
   usar como requisito FAC-130. Ambas estão em `new`. Não fazer novo polling para
   reencontrar updates já confirmados.
2. No próximo ciclo, operador autenticado deve abrir a demanda exata na UI, conferir
   texto/root, registrar revisão de requisito e decidir `approved` somente após
   conferir conteúdo e escopo. Intake/ACK não constituem autorização.
3. Criar plano aprovado e validar paths/dependências/hash antes do despacho. A API
   de conversa exige sessão de operador; não contornar auth nem converter inbound
   Telegram em identidade de operador. Se necessário, evoluir intake para ligar
   nativamente a demanda ao fluxo seguro de aprovação/conversa.
4. Executar somente depois de aprovação prévia; gravar transição via serviço de
   domínio, gerar evento/outbox de milestone para a mesma raiz, enviar com filtro
   `--authorized-demand-id bc16a11c-f654-4738-98f1-45daa2387faa` e verificar
   recibo de transporte/reply. Não enviar transcript nem texto bruto do agente.
5. Para idempotência, reprocessar o mesmo update/evento já confirmado em ambiente
   descartável ou via harness sem novo polling externo; exigir zero nova demanda,
   zero milestone equivalente e zero segundo envio após recibo confirmado. Cobrir
   429, falha/retry e autor indevido nos testes existentes, ajustando apenas se C0 mudou.
6. Manter aprovações sensíveis na UI autenticada. Não é necessário habilitar
   equivalência Telegram→operador para fechar esta atividade.

**Concluída quando:** piloto e replay têm IDs/hash, thread correta, ausência de
vazamento, critério de autorização satisfeito e aceite independente da atividade.
Inserção idempotente da outbox não garante exactly-once de `sendMessage`: crash
após envio e antes do recibo pode duplicar transporte; registrar at-least-once e
comportamento de recuperação sem prometer a garantia ausente no Bot API.

**Parada:** sem inbound ou sem autorização específica, registrar bloqueio e
continuar outras atividades; não fazer polling repetido para simular progresso.

## 6. FAC-130 — terceira origem e auditoria das duas provas existentes

**Reusar sob conferência:** `.runtime/artifacts/fac-130/current-implementation-update-20261026.json`
e receipts em `agent-runs/`. UI tem run `dbe38f01-e5b5-4003-ab74-fccb73b3e428`,
SHA `724288e67e73d8f72c2067c323b5da595d1fcabc`; GitHub tem run
`73aa83b1-b0c4-4413-ab13-bdaa9a520bda`, SHA
`122a9b326ae574d031e3a4e87d57a2ae3fc67785`. Há build, browser e review, mas
`requirement_decision=proposed` em ambos impede tratá-los como jornadas
integralmente autorizadas apenas pelo receipt.

1. Conferir decisões, timestamps, hash do requisito/plano e despacho desses dois
   runs no domínio e artefatos. Guardar resultado `reusable` ou `needs_rerun`
   por critério. Se a aprovação prévia não existir ou não vincular o payload,
   preservar os commits como prova parcial e repetir **somente a trilha afetada**
   depois de C0; não aprovar retroativamente nem editar receipt histórico.
2. **Entrada real já recebida:** demanda `bc16a11c-f654-4738-98f1-45daa2387faa`,
   raiz Telegram `464393985:11`, texto literal correto e ACK publicado. Usá-la como
   origem, sem outro polling. A raiz `464393985:10` (“tema dado”) é uma mensagem
   separada; ACK enviado, mas não autorizar nem executar essa demanda.
3. Auditar decisões e despacho das provas UI/GitHub, repetir somente trilha que
   não provar autorização prévia/hash-bound.
4. Na demanda correta, operador autenticado deve conferir baseline e escopo, aprovar
   requisito/plano, e então executar patch visual gerado em baseline limpo próprio.
   Reusar a decisão registrada sobre “Adicionar cliente” e `--button-dark` local;
   não reabrir produto resolvido sem fato novo.
5. Registrar discovery com path:line do commit, revisão e plano finais aprovados
   antes de disparar o agente. Gerar patch novo por Ollama sem copiar solução
   das rodadas UI/GitHub.
6. Rodar no SHA resultante build e browser com cor computada/contraste,
   hover/focus/disabled, light preservado e desktop/mobile. Identificar autoria
   do harness: teste da orquestração não é teste produzido pelo coder.
7. Reviewer distinto revisa diff e provas do mesmo SHA. Conferir retorno no canal
   inicial: usar outbox autorizada para Telegram; GitHub só escreve sob autorização
   própria. Se retorno remoto GitHub não estiver habilitado, documentar entrega
   local e a condição do contrato, sem afirmar comentário enviado.
8. Consolidar três origens independentes válidas e fechar FAC-121 antes do aceite.

**Concluída quando:** matriz UI/Telegram/GitHub sem lacunas de autorização,
autoria, resultado visual, review e entrega. Existência de AgentRun não basta.

## 7. FAC-131 — discovery grounded e plano final de tags

**Reusar:** baseline sem tags, decisões do operador e decisão EARS delegada
`1fab0606-74f5-4faf-9231-fbc48ee138db`, hash
`717314b84f20f80fed68988382c7050442b4bbff13d8739b87525fa15db5a9ab`.
`fac131-delegated-dag.json` registra sete tarefas propostas. A delegação não
comprova autoria das personas nem aprovação do payload final de um plano futuro.

1. Analyst da Factory investiga models/migrations/API/UI/testes no baseline sem
   solução. Produzir fatos com path:line/blob verificáveis, impactos, hipóteses e
   vínculo de conversa. Não usar o Registry atual com tags como descoberta inédita.
2. Reconciliar decisões já existentes com a revisão persistida. Conferir o
   conteúdo real: o receipt tem 10 clauses/20 scenarios, o Markdown lista oito
   EARS, e `TAG-R08` diz rejeitar quando houver **10**, enquanto o default admite
   **até 10**. Fixar a correspondência e testar limites 9/10/11. Corrigir texto
   draft não altera silenciosamente uma revisão aprovada; diferença material
   exige nova versão/decisão dentro da autorização aplicável.
3. Planner real produz/valida DAG com owner, scopes, arquivos novos, contrato,
   base, riscos, testes, outputs e budgets. Vincular aos sete IDs existentes
   quando equivalentes; evitar criar tasks duplicadas só para mudar proveniência.
   O DAG delegado ainda tem `TAG-FE` dependendo de `TAG-DB`; justificar uma
   dependência técnica real ou ajustar o plano antes da decisão final para
   permitir frontend a partir do contrato congelado, como exige o aceite.
4. Registrar a decisão sobre **o plano final** e seu hash. Reutilizar a decisão
   EARS delegada se conteúdo/hash permanecem idênticos; não inventar aprovação
   humana e não pedir confirmação administrativa já concedida.
5. Provar rejeição e changes_requested com nova versão preservando a aprovada;
   teste pode ser determinístico independente, sem invalidar a entrega principal.

**Concluída quando:** Analyst/Planner rastreáveis, contrato sem contradição,
revisão e plano aprovados/hash-bound e DAG persistido, liberando tasks autorizadas.

## 8. FAC-132 — gerar DB/backend em vez de revalidar tags manuais

**Reusar como controles:** `.runtime/artifacts/fac-132/postgres-migrations.json`
e testes do componente atual. Eles ajudam a conferir o oráculo; não comprovam
autoria da Factory no novo baseline.

1. Após FAC-131, executar TAG-DB/TAG-BE no worker versionado, em worktrees do run
   sem tags prontas; registrar base, contexto, inferência, patch e commit por task.
2. TAG-DB gera migration/models/constraints. Testar upgrade em PostgreSQL vazio
   e populado com dados sintéticos legados; conferir dados e integridade.
3. TAG-BE gera catálogo, associação e filtro conforme contrato congelado. Testar
   trim/casefold com acentos significativos, 1/32/33 caracteres, 0/10/11 tags,
   IDs desconhecidos/repetidos, omitido/[] e transação sem alteração parcial.
4. Executar downgrade/rollback e novo upgrade na estratégia revisada. Documentar
   se dados da feature são removidos; preservar dados legados segundo o contrato.
5. Gates e reviewer independente nos commits gerados, com run/task/SHA e hash de
   artefato. Corrigir apenas falhas observadas dentro do budget, sem transplantar
   a implementação atual para chamar de patch gerado.

**Concluída quando:** autoria DB/backend, compatibilidade/migração/rollback e
contratos estão comprovados no código gerado; FAC-131 aceita.

## 9. FAC-133 — frontend, integração e conflito controlado

**Reusar como controle:** E2E do Registry atual em `.runtime/artifacts/fac-133/`;
o resultado não dispensa testar o SHA realmente integrado das tasks.

1. Com o contrato aprovado, TAG-FE gera UI/cliente em worktree distinta. Pode
   iniciar junto de TAG-DB/BE; uma inferência pesada por vez respeita a GPU.
2. Integrar commits de DB/BE/FE em branch isolada, depois das dependências.
   Documentação/testes fazem parte do escopo previsto; mudança de contrato volta
   ao controle de versão/aprovação pertinente.
3. Exercitar **um** conflito controlado reproduzível em branch descartável,
   gerar child task de resolução e integrar a correção. Não fabricar conflito
   no checkout do operador nem alterar contrato só para provocar a prova.
4. Rodar browser→React→API→PostgreSQL sem mocks: criar/associar/remover/filtrar,
   busca AND, reload, vazio, erro recuperável, teclado/mobile e regressão
   cadastro/telefone. Confirmar API/migrations importadas do worktree certo.
5. Rodar gates aplicáveis e review novo no SHA integrado/resolvido; provas dos
   SHAs individuais não substituem integração. Guardar diff, screenshots e IDs.

**Concluída quando:** FAC-132 aceita, UI gerada funciona no integrado, isolamento,
conflito/resolução e regressão possuem evidências ligadas ao mesmo SHA final.

## 10. FAC-134 — adicionar um teste de verdade via follow-up QA

1. Após FAC-133, escolher cenário contratual ainda sem teste. Registrar snapshot
   dos requisitos, decisões e tasks terminais originais.
2. Abrir conversa Factory `@qa` no card concluído. QA propõe child task com paths,
   aceite e SHA entregue; decisão aceita o payload pelo fluxo suportado.
3. Consumidor real de follow-up executa somente QA com discovery reutilizado.
   O agente cria um teste novo, executa-o e obtém review no novo SHA.
4. Comparar os registros originais: preservar conteúdo/revisões/estados terminais;
   novos eventos/child task podem acrescentar histórico. Replay não cria outra task.
5. Se o pedido exigir regra fora do contrato, abrir revisão; não usar esse caso
   para declarar follow-up puramente QA entregue.

**Concluída quando:** proposta aceita → child task → teste novo → gates/review,
sem reiniciar todo discovery nem mutar a entrega original. Proposta inerte
`pending_review` existente é prova parcial, não a saída final.

## 11. FAC-135 — bug CPF no fluxo completo

1. Usar fixture sintética defeituosa em worktree limpa, autorizando explicitamente
   os paths da fixture fora do alvo padrão quando necessário. CPF não vira campo
   do cadastro. Executar e guardar o teste **vermelho antes**.
2. Fazer intake normal e deixar Analyst/Planner conduzir contexto, requisito e
   plano aprovados. Worker da Factory gera o fix por Ollama sem patch fornecido.
3. Aplicar/testar em sandbox sem rede; comprovar teste verde depois, regressões
   pertinentes e ausência de alteração fora do escopo ou enfraquecimento do teste.
4. Reviewer independente usa diff/linhas corretas e gates do SHA final. A revisão
   anterior `uncertain` com confiança 0,75 não satisfaz mínimo 0,8; diagnosticar
   a inconsistência e executar nova revisão baseada em provas, sem repetir até
   obter aprovação por acaso.
5. Registrar AgentRun/GateEvidence, vermelho/verde, commit, review e resultado.

**Concluída quando:** ciclo real rastreável completo. Reusar a fixture e os
controles existentes; o experimento isolado anterior não é o run de aceite.

## 12. FAC-136 — scanner, patch e regressão no mesmo run

1. Congelar fixture/lockfile vulnerável e fonte de advisories reproduzível.
   Distinguir direto/transitivo e achado aplicável; não depender de contagem que
   muda no feed para provar o before/after congelado.
2. Intake e agente produzem proposta/escopo; worker aplica upgrade/lockfile da
   **fixture autorizada** em sandbox e registra inferência, diff e commit.
3. Rodar scanner antes/depois com a mesma fonte, testes e regressão da fixture.
   Provar remediação e ausência de high/critical no alvo segundo policy.
4. Usar candidato intermediário insuficiente como controle de veto. Os scans
   históricos 21→18→0 comprovam o scanner, não a integração ao runtime.
5. Review independente do patch e evidências por SHA. Mudança do lockfile real
   do projeto ou publicação exige decisão própria; não é necessária para uma
   demo válida na fixture prevista pelo escopo.

**Concluída quando:** scanner→proposta→patch→scanner/regressão→review compartilham
demanda/task/run e proveniência, com o candidato insuficiente corretamente vetado.

## 13. FAC-137 — matriz limitada de recuperação real

Usar processo worker real e PostgreSQL/checkpointer descartáveis. O provedor
externo pode ser simulado quando a matriz indicar; rotular essa dimensão. Não
exigir falha no Telegram/GitHub de produção nem envio duplicado live para testar
recuperação. Preservar prova anterior `postgres-process-restart.json` como controle.

| Caso | Interrupção/falha | Prova de retomada exigida |
|---|---|---|
| R01 | Intake após persistir e antes do cursor/ack | Uma demanda, evento deduplicado, cursor consistente. |
| R02 | Discovery após gravar resposta/checkpoint | Mesmo contexto/revisão e retomada sem perder pergunta. |
| R03 | HITL durante espera e após decisão | Approval preservado e consumido uma vez. |
| R04 | Inferência com timeout/indisponibilidade Ollama | Budget e retry explícitos; sem patch/commit fictício. |
| R05 | Patch aplicado antes de registrar recibo | Reconciliação da árvore; não aplicar duas vezes. |
| R06 | Commit criado antes de registrar resultado | Reusar commit comprovado; não gerar segundo efeito. |
| R07 | Integração em andamento | Recuperar branch/conflito e retestar SHA final. |
| R08 | Push/PR simulado após efeito e antes do ack | Transporte real contra destino simulado reconcilia branch/PR. |
| R09 | GitHub/Telegram indisponíveis/429 | Backoff e cursor/outbox duráveis; domínio não duplica. |
| R10 | Redis indisponível | Estado PostgreSQL íntegro; recuperação/fallback previsto demonstrado. |
| R11 | Lease expirada com worker antigo vivo | Novo claim progride; token antigo não grava nem publica. |
| R12 | Retry esgotado, DLQ, reprocessamento e cancelamento | Limites/decisões auditados; cancelado não retoma efeito proibido. |

1. Preparar roteiro controlado por caso: ponto de falha, dado inicial, comando,
   PID antigo/novo, IDs/contagens antes, efeito esperado, cleanup.
2. Injetar falha e reiniciar processo distinto; verificar domínio, checkpointer,
   Git e journal do transporte. Não basta callback retornar run ID.
3. Exigir uma aprovação para push e outra para PR em R08; conferir stale SHA/
   ação negados. Resolve a integração pendente de FAC-127 sem publicação real.
4. Consolidar 12 linhas pass/fail/infra com artefatos. Repetir apenas linha falha
   e regressão afetada após correção. Transporte Telegram segue at-least-once:
   não prometer ausência absoluta de duplicata de mensagem em janela sem ack.

**Concluída quando:** 12 casos cobertos, nenhuma perda/duplicação de efeitos de
domínio, fencing correto e limitações do transporte explícitas e compatíveis
com o contrato. Simulador externo não deve ser chamado de piloto live.

## 14. FAC-138 — correlação, proteção e restore do conjunto

1. Escolher uma jornada já aceita e percorrer intake/demand/task/run/thread/
   checkpoint/model/tool/gates/review/entrega no backend e dashboard. Todos os
   links devem apontar ao mesmo run/SHA. Publish desabilitado aparece como
   desabilitado, não como publicação comprovada.
2. Conferir fila/load/generation/tokens, GPU quando disponível e rework/aceite
   por task/persona. Indisponível é `null` com motivo; separar tempo, estimativa
   e dinheiro sem fonte. Phoenix não é obrigatório.
3. Exercitar critérios ainda só descritos de FAC-129: trial baseline/candidato
   vinculado a runs reais, feedback independente, promoção autorizada da versão
   e próxima execução usando-a; rollback muda a seguinte. Se faltar wiring,
   implementá-lo uma vez no caminho comum. Judge numérico permanece advisory.
4. Usar marcadores **sintéticos** para testar redaction no chat/context/output/
   logs/artefatos, acesso não autenticado e leitura de artefato de outra demanda.
   Autenticação de operador único não justifica ausência de vínculo/escopo.
5. Executar retenção/GC controlados: remover expirados permitidos e preservar
   worktree ativa, evidência essencial, checkpoints/decisões necessários.
6. Conferir hashes/readback em `fac-138/restore-summary.json`: já há restore de
   Factory, Registry, checkpoint, OpenBot SQLite e artefato sintético com smoke.
   Reusar partes intactas. Acrescentar restore coerente da jornada escolhida e
   artefatos finais em alvos descartáveis, retomada/consulta pela aplicação e
   cleanup. Não refazer tudo apenas porque um texto antigo diz inexistente.

**Concluída quando:** correlação navegável, métricas honestas, prompt/run efetivo,
redaction/acesso/GC e restore/readback comprovados, sem apagar run ativo.

## 15. FAC-142 — concluída; preservar e reutilizar sua evidência

O backlog registra FAC-142 como `done`. A decisão vigente do operador em
2026-10-27 autorizou casos sintéticos com resultado determinístico e revisão
independente por IA. Não exigir labels humanos nesta atividade. O aceite
registrou `human_agreement=null` e não alegou calibração humana. As exigências
antigas de anotação humana são histórico, não bloqueio vigente.

1. Reusar o harness e pacote existentes. Congelar dataset versionado com casos
   corretos, parciais, defeituosos, perigosos e sem evidência. Cada caso contém
   ID, slice, entrada, oráculo/resultado esperado, severidade e hash. Separar
   desenvolvimento dos casos usados na avaliação final.
2. Validar o oráculo por execução determinística independente do Judge. Cobrir
   positivos/negativos, contraditórios, sem evidência e variantes de ordem,
   verbosidade, autoria alegada, referência fabricada e injeção. Transformações
   cosméticas preservam fatos; mudanças materiais são controles não equivalentes.
3. Antes de executar o modelo, congelar modelo/digest, prompt/configuração,
   critérios e limites por slice, amostra, seeds e protocolo A/B/ordem trocada.
   Não selecionar thresholds após observar resultados nem misturar versões.
4. Executar casos e guardar saídas reproduzíveis. Calcular matriz de confusão
   (positivo=defeito), falsos negativos críticos, falsas reprovações,
   abstention/coverage/schema, latência/tokens e incerteza. Preservar convenções
   legadas e não tratar `confidence` como probabilidade.
5. Comparar cada saída ao oráculo; conferir invariância dos casos adversariais e
   documentar falhas por caso/slice. Não ocultar erros em médias agregadas.
6. Montar pacote com dataset, hashes, oráculo, comandos, modelo, resultados e
   conclusão. Um reviewer de IA diferente do executor confirma integridade,
   cobertura, resultados e fidelidade da conclusão.
7. Registrar conclusão por slice. Um resultado válido pode ser `advisory_only`
   e `promotion_eligible=false`, mantendo Judge desligado se inadequado. Não é
   necessário demonstrar desempenho bom nem promover automaticamente.

**Critério registrado como concluído:** dataset/oráculo determinísticos,
execuções e métricas reproduzíveis; revisão independente aprovou pacote e
conclusão por slice; campos de concordância humana permanecem nulos. O resultado
de 2026-10-26 (63 casos; 37/63 agreement, 2 FN críticos, 3 falsas reprovações e
falha de invariância) e o receipt independente aprovado
(`a7fc5149ed191700d48b`, confiança 0,95) são reaproveitáveis. A validação foi
reconciliada com `audit.independent_review` no backlog; conferir o receipt/hash
no aceite global, sem repetir FAC-142 se íntegros.

## 16. FAC-139 — fechamento e assinatura sem ciclo de hashes

1. Confirmar FAC-121 e FAC-130–138 aceitas e C0 coberto. Revalidar o receipt
   FAC-142 concluído conforme §15. FAC-139 é avaliada neste próprio passo por
   meio da revisão global do snapshot candidato, não deve ser pré-marcada como
   aceita. Montar matriz
   requisito→atividade/owner→run/SHA→gate/artefato/hash→review/decisão. Incluir
   disposições dos vínculos históricos e opcionais; nenhum obrigatório omitido
   por já estar `done`. Não aceitar lista de IDs obrigatórios reduzida pelo próprio
   manifest sem compará-la ao backlog e perfil contratado.
2. No snapshot final estável, rodar `make quality-fast` para feedback e
   `make quality-full` para encerramento com PostgreSQL/browsers/scanners/DAST/
   Sonar/performance. Exigir full realmente verde; sem reduzir cobertura 80%.
   Se Sonar falhar por cobertura, corrigir e repetir o afetado antes de novo full.
3. Verificar gates, skips e hashes por snapshot. Mudança de código/suite invalida
   a prova afetada; mero reaproveitamento entre jornadas exige compatibilidade
   demonstrada. `git_sha` sozinho não identifica o checkout sujo: guardar também
   tree/source hash.
4. Depois do checklist, preparar em `.runtime` um **snapshot candidato final**
   do backlog e documentos, com FAC-139 projetada como concluída, contagens e
   metadados coerentes. Ele é uma proposta de estado pós-aceite, não status
   oficial nem prova fabricada. O backlog oficial continua `in_progress` até a
   revisão final. Se necessário executar qualidade em checkout do candidato,
   identificá-lo como tal e não misturar hashes com o checkout oficial anterior.
5. Via emissor versionado C0.3, reviewer distinto avalia pacote e bytes exatos
   do candidato, inclusive os critérios FAC-139. Emitir manifest/prompt/resposta/
   receipt global `all-required-activities`, decisão real, confiança mínima 0,8,
   hashes e HMAC. A revisão global fornece o aceite da própria FAC-139; não
   exigir da CLI por atividade um receipt global que ela não sabe emitir. Chave
   local restrita; nenhum receipt deve integrar o conjunto que ele próprio assina.
6. Verificar o receipt contra o candidato, incluindo o conjunto obrigatório
   derivado do backlog/perfil, gates do snapshot e integridade. Se reject/uncertain,
   o backlog oficial fica pendente. Se approve verificável, publicar os **mesmos
   bytes** do candidato como backlog oficial e validar novamente. Publicação local
   deve ser recuperável/idempotente: manter candidato/receipt e comparação de hash
   para crash entre revisão, troca do arquivo e geração do relatório. Não inserir
   a assinatura de volta no backlog assinado nem editá-lo após a troca.
7. Rodar o verificador existente:

   ```bash
   uv run --frozen --all-packages --group api python scripts/acceptance_report.py --approval .runtime/artifacts/uat/ai-approval.json
   ```

   Conferir também os hashes de código/suites dos gates. O relatório é saída
   derivada: se a geração mudar arquivos cobertos pelo source manifest, registrar
   essa diferença de documentação explicitamente e verificar que código/config/
   suites testados são idênticos; não reapresentar o source hash antigo como atual.
   Ele gera o relatório, mas **exit 0 sozinho não significa aceite**. Conferir
   `status=accepted_by_ai`, `pending_required=[]`, receipt válido e hashes atuais.
8. Entregar branch/commits locais, instruções reproduzíveis, relatório e resultado
   nos canais autorizados. Não presumir push/merge/deploy. Não editar o backlog
   depois da assinatura: qualquer alteração requer novo pacote/revisão global.

**Concluída quando:** 174/174 no marco contratado, 11/11 pendências atuais desta fase
fechadas com evidência, full verde e scorecard global validado. Se a revisão
rejeitar, manter o aceite global pendente e corrigir a causa específica.

## 17. Regras para não reiniciar o ciclo sem necessidade

- Cada atividade termina com checklist critério→prova, não com “rodar mais testes”.
  `remaining_work` contém só lacunas atuais; histórico fica em `validation`/audit.
- Antes de repetir, dizer qual evidência falta e por que o teste escolhido a prova.
  Não repetir suite global para resolver falta de inbound, label ou approval.
- Diagnosticar `fail`, `infra`, bloqueio de autorização, dado externo ausente e
  evidência inválida separadamente. Gate de cobertura é falha de qualidade mesmo
  se o wrapper tiver devolvido 2; ajustar classificação com prova do erro.
- Respeitar orçamento finito por run. Nova tentativa após exaustão exige uma
  mudança identificada de código/configuração/entrada, não só outro prompt igual.
- Marcar PASS apenas no mesmo SHA/run testado; `uncertain`, skipped e ausente não
  viram PASS por média. Nova correção requer review do novo SHA.
- Um piloto pode fornecer evidência para várias tasks: Telegram FAC-121/130,
  tags FAC-131–134, fault injection FAC-137, trace/restore FAC-138 e matriz FAC-139.
  Cada critério continua apontando à sua prova específica.
- Não adicionar features, novos benchmarks ou integrações opcionais no caminho
  crítico. Descoberta material fora deste contrato vai para decisão/backlog próprio.
- Atualizar `state.md`, backlog e índice após cada fechamento; não anexar outro
  resumo contraditório. Preservar artefatos anteriores e sua proveniência.

## 18. Pacote mínimo de evidência por jornada

| Grupo | Conteúdo verificável |
|---|---|
| Entrada e autoridade | Canal/origem/identidade, evento e message/Issue ID, requisito/versão/hash, plano/hash, decisão anterior ao efeito e seu escopo. |
| Execução | demand/task/run/attempt/thread/checkpoint, worker, lease/fencing, modelo/digest, prompt/context/skills, budgets e timestamps. |
| Código | Baseline Git sem solução, worktree, diff/patch hash, commit/tree/source hash e isolamento do alvo. |
| Qualidade | Comando/tool/config/suite hash, exit/status real, artefato/hash, testes/gates aplicáveis e motivo de N/A/skip permitido. |
| Review e entrega | Reviewer distinto/read-only, SHA revisado, decisão/confiança/citações, rework e retorno autorizado no canal. |
| Aceite | Manifest e receipt de atividade; no final, pacote/receipt global verificáveis sobre backlog final congelado. |

Paths novos de runners, matrizes e manifests sugeridos neste plano são trabalho
para a próxima fase. Referências `.runtime` existentes foram inspecionadas como
evidência local; não se presume que existam em outro checkout nem que seus
resumos substituam readback autoritativo e conferência de hashes.
