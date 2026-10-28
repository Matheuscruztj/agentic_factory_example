# Validação das integrações

Atualizado em 2026-10-25. A [auditoria atual](auditoria-projeto-2026-10-24.md)
prevalece sobre evidências históricas abaixo. O [plano E2E](../specs/08-PLANO-CONCLUSAO-E2E.md)
complementa o intake com discovery, execução, qualidade e retorno ao canal.
Ordem operacional aprovada pelo escopo atual:
infraestrutura local → APIs/UI → Telegram/intake → contexto e agentes.
`state.md` controla o andamento; este documento define a execução e o aceite.
Os critérios originais de `specs/03-TASKS-POR-FASES.md` continuam válidos.

## Configuração atual

- `.env` local gerado, permissão 600, ignorado pelo Git. Segredos de aplicação e
  PostgreSQL gerados automaticamente; senha do operador em
  `.runtime/operator-password.txt` (também ignorado, permissão 600).
- Telegram habilitado para o bot `test_agentic_maz_bot`; autenticação `getMe`
  validada ao vivo e intake autorizado depois exercitado em um ciclo controlado.
- Intake worker usa allowlists `TELEGRAM_ALLOWED_CHAT_IDS` e
  `TELEGRAM_ALLOWED_USER_IDS`; `.env` atual está configurado com IDs autorizados.
- Jira fora do escopo desta etapa e explicitamente desativado no `.env`.
- GitHub está habilitado com o PAT já configurado no `.env` local. O worker
  valida o nome do repositório fixo antes de consultar Issues. O preflight live
  passou; os polls one-shot retornaram `pass`, uma página e zero Issues elegíveis.
  Cursor está em modo 0600 em `.runtime/github-cursor.json`; não houve escrita.
  PAT de privilégio mínimo fica como hardening futuro, sem bloquear o trabalho.
- SonarQube Community está habilitado localmente em `127.0.0.1:9001`, com token
  autenticado e dados persistentes; análise `agentic-factory-local` passou o
  Quality Gate em 2026-10-25. O scanner Docker compartilha a rede Compose.
  Ollama e OpenBot estão habilitados; Phoenix e OTEL permanecem desativados.
- A sondagem atual alcançou Factory API, PostgreSQL, Redis e Ollama. Registry/UIs
  e API OpenBot no host não estavam disponíveis naquele instante; o container
  OpenBot estava saudável internamente, sem gateway host ativo. Flags e URLs
  não comprovam disponibilidade nem workflow.
- Modelos listados: `qwen2.5-coder:7b` e `qwen3:4b`. Não foi realizado ensaio
  de geração de feature por agentes nesta análise.

### Smoke live read-only — 2026-10-25

Foi executado novo preflight com o `.env` local, sem registrar valores dele:

- Telegram: `getMe` e `getChat` passaram. `getUpdates` em offset 0 retornou
  quatro registros disponíveis; não foram processados nem o offset foi alterado.
- Ollama: `/api/tags` passou e o adapter real executou chat estruturado em
  `qwen2.5-coder:7b`; digest, schema JSON e contadores de tokens foram obtidos.
  O caminho `qwen3:4b` também respondeu à API, mas gastou o limite curto
  raciocinando e não produziu conteúdo útil, então não conta como smoke aprovado.
- PostgreSQL: `SELECT 1`; Redis: `PING` — ambos passaram sem mutação.
- OpenBot configurado, mas endpoint local não alcançável. O doctor também não
  alcançou as APIs Factory/Registry durante a sondagem.
- GitHub: preflight live falhou por falta de token; owner/repo/allowlist não
  estavam configurados naquele instante. Jira estava desativado. Sonar foi
  configurado depois desta sondagem, conforme seção abaixo.

Após o preflight inicial, o PAT configurado no `.env` autenticou `GET /user`,
`GET /repos/Matheuscruztj/agentic_factory_example` e o endpoint de Issues. O
worker repetiu o polling com validação do nome esperado do repositório. A
credencial permanece no `.env` local, que é ignorado pelo Git e tem modo 0600;
seu valor não foi registrado. O operador autorizou seu uso atual. Avaliar uma
credencial de privilégio mínimo como melhoria futura.

Artefato sanitizado: `.runtime/integration-live-2026-10-25.json` (modo 0600).
Naquela etapa de preflight não houve processamento de mensagens, criação/edição
de Issue, envio de mensagem, escrita no banco, avanço de offset ou publicação.
Para testar intake
Telegram de ponta a ponta, é necessário que o operador envie uma nova mensagem
de teste autorizada e então acompanhar o worker; a fila existente foi deixada
intacta.

### GitHub + normalização + Ollama — Issue sintética

Para validar a leitura real, foi criada a Issue sintética
[#1](https://github.com/Matheuscruztj/agentic_factory_example/issues/1), com
label `bug`, reaberta temporariamente durante o teste e fechada ao final. O
`GitHubClient` e `poll_github` leram o cartão depois de 7 s de espera para a
indexação da coleção do GitHub; a primeira leitura imediata após criação/reabertura
não o listou, embora o endpoint de detalhe já o mostrasse. O poll subsequente
importou 1 item no callback de teste, sem persistir no PostgreSQL.

O normalizador preservou source, ID `owner/repo#issue`, tipo `bug`, título,
corpo, URL HTTPS e event ID determinístico. O Ollama `qwen2.5-coder:7b` produziu
JSON estruturado válido, reconheceu o bug e os critérios da UI, delimitou
escopo frontend e não inventou mudança backend/API. Ainda fez perguntas
redundantes sobre campos/casos já descritos; o resultado é parcial e não prova
discovery sem esclarecimentos desnecessários. A Issue ficou fechada; o PAT de
escopo amplo não foi salvo. Nenhum banco, branch ou PR foi alterado.

Evidência: `.runtime/github-llm-smoke.json` (modo 0600). O atraso de indexação
deve ser coberto por retry/overlap do consumidor antes de considerar o polling
robusto contra leitura imediatamente após criação.

### Sonar local

SonarQube Community foi iniciado com `infra/compose/sonar-local.yml`, imagem
presa a digest, volumes persistentes, healthcheck exigindo API `UP` e porta
loopback `9001`. A senha `admin` inicial foi substituída; a recuperação local
fica em `.runtime/sonar-admin-password.txt` (0600). Token de usuário foi
gerado, autenticado e guardado somente no `.env` (0600), com
`SONAR_ENABLED=true` e URL loopback. Preflight isolado `--require sonar` passou.
O scanner local está no mesmo Compose/rede `a-fabric-sonar`; a análise do
snapshot `agentic-factory-local` passou o Quality Gate. Artefato:
`.runtime/quality/runs/20261025T210718Z-9b7fa6ff/extended/sonar-quality-gate.log`.
Resumo sanitizado: `.runtime/sonar-local-config.json`.

Evidência inicial: Compose com ambos os serviços saudáveis; preflight live em
2026-10-24 retornou exit 0, quatro verificações aprovadas, sem falhas. Resumo em
`.runtime/integration-preflight.json`. Migrações e restart foram concluídos; veja
`.runtime/integration-infra.json` e `state.md` para os registros mais recentes.

## 1. Infraestrutura e persistência — FAC-009, FAC-011

1. Subir PostgreSQL/Redis com o Compose base e aguardar healthchecks.
2. Executar preflight live usando o `.env` real.
3. Aplicar Alembic de Factory e Registry com as variáveis carregadas do `.env`;
   não usar os defaults SQLite para essa evidência.
4. Validar as duas bases e persistência de um registro sintético após restart.

Comandos iniciais:

```bash
docker compose --env-file .env -f infra/compose/base.yml up -d --wait
python scripts/validate_env.py --env .env --mode local --require core,postgres,redis,telegram
python scripts/validate_env.py --env .env --mode live --require core,postgres,redis,telegram
```

Aceite: autenticação PostgreSQL e PING Redis aprovados, ambas as migrações em
head, registro preservado após restart. Preflight offline não substitui conexão.
`--require` acrescenta serviços obrigatórios; outros habilitados também são testados.

## 2. APIs e interfaces — FAC-006, FAC-010–013, FAC-028–034

1. Iniciar Registry e Factory usando o `.env`, com as migrações concluídas.
2. Validar health/live e health/ready, login real, cookie, CSRF e status sanitizado.
3. Validar Factory → Registry com leitura de dados sintéticos e serviço indisponível.
4. Executar fluxos de UI para Registry, demanda manual, tarefas, aprovação e SSE.
5. Conferir doctor com todos os serviços ativos.

O intake manual usa um `external_id` estável enquanto o conteúdo do formulário
não mudar. Repetição idêntica é idempotente; a mesma chave com payload diferente
deve retornar conflito.

Aceite: UI conversa com a API real; API usa PostgreSQL; erros de dependência são
visíveis sem credenciais nas respostas; aprovação e SSE mantêm consistência.
A demanda manual deve funcionar mesmo sem os conectores externos.

## 3. Telegram até demanda — FAC-035, FAC-040

1. Criar testes com transporte fake para allowlists de chat/usuário, duplicatas,
   falha no processamento, reinício e offset persistido somente após sucesso.
2. O worker implementado em `scripts/telegram_intake_worker.py` conecta o poller
   ao normalizador e à persistência idempotente de demandas. Offset atômico fica
   em `.runtime/telegram-offset.json` e só avança após sucesso do processamento.
3. Obter do operador chat ID e user ID autorizados e configurá-los no worker via
   `TELEGRAM_ALLOWED_CHAT_IDS` e `TELEGRAM_ALLOWED_USER_IDS`.
   Nunca aceitar qualquer chat/usuário como default.
4. Com as allowlists definidas e uma mensagem de teste enviada pelo operador ao bot,
   executar `uv run python scripts/telegram_intake_worker.py --env .env --once`
   e conferir a demanda na API/UI. Para polling contínuo, omitir `--once`.

Aceite: uma mensagem autorizada gera uma demanda, replay não duplica, mensagens
não autorizadas não geram demandas e reinício retoma o offset persistido.
Testes fake cobrem persistência, replay, allowlists e offset não avançado após
falha. Intake live foi executado em um ciclo: 4 mensagens autorizadas criaram 4
demandas no PostgreSQL e o offset foi persistido em arquivo modo 0600. Evidência
sanitizada em `.runtime/integration-telegram-intake.json`; nenhum conteúdo de
mensagem foi copiado para o artefato de evidência.
Nenhum envio de mensagem pelo bot é necessário nesta etapa.

## 4. GitHub e contexto — FAC-036–039, FAC-041–046

- Executar testes fake de GitHub/polling: paginação, overlap, cursor, backoff,
  reconciliação e limites por repositório. PAT/App e repositório por operação
  são dependências para a futura validação live; não exigir owner global no `.env`.
- Executar aceites de manifests, skills, router, context pack e compaction.
- FAC-046 tem avaliação determinística local disponível; integrá-la às entradas
  reais e ao contexto do agente em FAC-111/124.
- Validar Ollama/OpenBot por perfil e compor chamadores reais em FAC-106/110/124.
  Phoenix continua opt-in; Jira permanece adiado.

## 5. O que falta além do intake

Intake validado significa mensagem/Issue persistida. Não comprova comandos,
esclarecimento, planejamento, código ou retorno ao canal. FAC-120–127 cobrem
Telegram bidirecional, GitHub sem perda, comentários, seis personas, frontend
operacional e publicação com decisões específicas. FAC-130–139 demonstram as
jornadas completas com LLM local e recuperação sob falhas.

Pilotos futuros precisam de destino autorizado. Esta auditoria não enviou
mensagens, consumiu updates, criou Issues/PRs ou alterou a base operacional.

## Evidências

Registrar comando, horário, exit code e resumo sem segredos em `.runtime/`.
Atualizar `state.md` e o arquivo de fase apenas para critérios efetivamente
comprovados. Não registrar `.env`, senha, token, cookie ou mensagens pessoais.
