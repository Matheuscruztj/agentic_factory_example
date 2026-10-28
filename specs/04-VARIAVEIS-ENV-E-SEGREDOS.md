# Agentic Factory Local v2 — Variáveis do .env, segredos e pré-requisitos

Este é o catálogo **de referência**, incluindo variáveis futuras. Não afirma que
toda variável já seja consumida pelo runtime. FAC-106 deve classificar configuração
consumida, default suportado e proposta futura. Ver [auditoria atual](../docs/auditoria-projeto-2026-10-24.md).

O `.env` local atual já contém credenciais e é ignorado pelo Git; não o imprimir,
compartilhar nem recriar durante validação. Para instalação nova, o utilitário
`python scripts/setup_local_env.py` gera segredos e hash scrypt sem imprimi-los.
Ele recusa sobrescrever `.env` já configurado.

Diferenças confirmadas em 2026-10-24:

- Variáveis `_CONTAINER` deste catálogo não estão no exemplo atual nem configuram
  automaticamente serviços; cada processo/container precisa da URL correta.
- Polling GitHub recebe owner/repo na construção do cliente. Preflight PAT em
  `/user` não prova repo permitido nem configura worker; FAC-122 fecha a composição.
- Worker Telegram exige **ambas** `TELEGRAM_ALLOWED_CHAT_IDS` e
  `TELEGRAM_ALLOWED_USER_IDS`; `TELEGRAM_CHAT_ID` do probe não substitui allowlist.
- Projects usa atualmente `GITHUB_PROJECT_V2_ID`, não os nomes genéricos da tabela.
- Judge/evaluador e runtime precisam unificar nomes de modelo/base URL/budgets;
  declarar variável não comprova aplicação de limite/política. FAC-110/129 tratam isso.

## A. Obrigatórios para a fase base (local)

| Variável | Exemplo/valor | Função / onde atua |
|---|---|---|
| `FACTORY_ENV` | `local` | Impede habilitar perfis de cloud sem decisão explícita |
| `FACTORY_HOST` | `127.0.0.1` | Bind local da API |
| `FACTORY_API_PORT` | `8001` | FastAPI Factory |
| `FACTORY_WEB_PORT` | `5173` | Vite React |
| `FACTORY_WEB_URL`, `FACTORY_API_URL`, `FACTORY_CORS_ORIGINS` | URLs localhost | Navegador, client e CORS de desenvolvimento |
| `APP_SECRET_KEY` | **segredo gerado automaticamente** | Sessão/autorização; não versionar |
| `OPERATOR_PASSWORD_HASH` | **scrypt hash gerado** | Autenticação do operador; hash não é senha em texto puro |
| `OPERATOR_HASH_SCHEME` | `scrypt` | A implementação de autenticação deve verificar a codificação `scrypt:n:r:p:salt_hex:digest_hex` (delimitadores `:` seguros em .env/Compose) gerada pelo utilitário |
| `LOCAL_AUTH_ENABLED` | `true` | Exigir sessão no painel |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` | valores gerados/local | Compose PostgreSQL; senha gerada automaticamente |
| `DATABASE_URL` | `postgresql+psycopg://...@127.0.0.1:5432/factory` | Scripts e API rodando no host |
| `DATABASE_URL_CONTAINER` | `...@postgres:5432/factory` | App dentro do Docker Compose (futuro) |
| `REGISTRY_DATABASE_URL` e `_CONTAINER` | `customer_registry` | Banco separado do sistema de cadastro |
| `REDIS_ENABLED`, `REDIS_URL`, `REDIS_URL_CONTAINER` | `true`, `redis://...` | Fila/eventos e workers; nunca fonte da verdade |
| `RUNTIME_DIR` | `.runtime` | Logs, checkpoints materializados, worktrees, artifacts e dados gitignored |
| `LOG_LEVEL`, `LOG_JSON`, `LOG_REDACT_SECRETS` | `INFO,true,true` | Logs compactos e mascarados |
| `REGISTRY_API_URL`, `REGISTRY_WEB_URL` | localhost 8010/5174 | App real de cadastro em desenvolvimento |

### Atenção a senhas em URLs

O utilitário `setup_local_env.py` gera uma senha URL-safe e a aplica ao Compose e às três URLs da base de dados. Se editar manualmente e usar caracteres especiais em URL, aplique codificação percent-encoding, pois senha e URL precisam permanecer consistentes. Banco `customer_registry` é criado no **primeiro bootstrap do volume**; se o volume já existia antes da adição do script, a inicialização não o recria, devendo executar a migração/admin SQL explicitamente em ambiente de desenvolvimento.

## B. Ollama / RTX 4060 Ti 8 GB

| Variável | Inicial | Observação |
|---|---|---|
| `OLLAMA_ENABLED` | `true` | Endpoint local usado pela Factory |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Scripts no Windows/WSL/host (ajustar se WSL bridge) |
| `OLLAMA_CONTAINER_BASE_URL` | `http://host.docker.internal:11434` | Contêiner Docker Desktop para Ollama no host; testar alcance |
| `OLLAMA_MODEL_CHAT` | `qwen3:4b` | Conversa, Discovery e assistentes leves |
| `OLLAMA_MODEL_CODING` | `qwen2.5-coder:7b` | Edição de código / testes;
| `OLLAMA_MODEL_JUDGE` | `qwen3:8b` | Judge separado para avaliar, inicialmente desabilitado |
| `OLLAMA_NUM_CTX` | `4096` | Contexto inicial conservador para 8GB VRAM |
| `OLLAMA_NUM_PREDICT` | `1024` | Limite de saída por solicitação |
| `LLM_MAX_CONCURRENT_REQUESTS` | `1` | GPU compartilhada, fila de inferência |
| `LLM_TOOL_CALL_LIMIT` | `12` | Ferramentas no máximo por tentativa |
| `LLM_RETRY_LIMIT` | `2` | Evita loops caros |
| `LLM_PER_TASK_TOKEN_BUDGET` | `18000` | Budget total inicial; medir e ajustar |
| `LLM_JUDGE_ENABLED` | `false` | Ativar apenas após dataset/evals inicial |

**Importante:** `OLLAMA_NUM_CTX` é um limite passado pela aplicação; `OLLAMA_NUM_PARALLEL` é configuração do processo/servidor Ollama. A fábrica limitará requisições por um semáforo/queue; não significa que todos os agentes possam inferir simultaneamente. As tags são sugestões de benchmark; confirme em `/api/tags` e faça `ollama pull` conforme necessidade. Ollama não exige API key local.

## C. OpenBot e LangGraph

| Variável | Requerida quando | Função |
|---|---|---|
| `OPENBOT_ENABLED` | P07 | Habilita adapter e validação |
| `OPENBOT_BASE_URL` | P07 | URL local do servidor upstream; porta não conflita com Factory API |
| `OPENBOT_HEALTH_PATH` | P07 | Rota verificável da versão upstream fixada |
| `OPENBOT_AUTH_PROBE_PATH` | Quando precisar validar chave live | Rota protegida confirmada durante spike; sem ela health não comprova API key |
| `OPENBOT_API_KEY` | P07 | Segredo da API OpenBot; deve casar com a config no servidor upstream |
| `OPENBOT_WORKING_DIRECTORY` | Opcional em discovery/review isolados | Diretório relativo já existente sob `WORKSPACE_ROOT` do OpenBot; valor vem da configuração da Factory, nunca do texto do usuário |
| `FACTORY_REPOSITORY_SHA` | Com `OPENBOT_WORKING_DIRECTORY` | SHA do snapshot de código que a conversa deve inspecionar; deve corresponder ao diretório selecionado |
| `OPENBOT_DEFAULT_ACTOR`, `OPENBOT_MAX_BOT_HOPS` | P07 | Defaults internos de roteamento e loop limit |
| `LANGGRAPH_CHECKPOINT_BACKEND` | P08 | `postgres`, para retomar após restart |
| `WORKER_ENABLED`, `WORKER_MAX_CONCURRENT_TASKS` | P03/P08 | Execução e paralelismo de atividades |
| `TASK_LEASE_SECONDS`, `TASK_HEARTBEAT_SECONDS` | P03 | Leasing/heartbeat para evitar tarefa duplicada |
| `TASK_MAX_ATTEMPTS`, `TASK_RETRY_BACKOFF_SECONDS` | P08 | Backoff e limites de tentativas |
| `ALLOW_AGENT_EDIT_FACTORY_CORE` | `false` | Nunca liberar core sem revisão reforçada |
| `ALLOW_AGENT_PUBLISH_PR` | `false` | Push/PR bloqueados inicialmente |
| `ALLOW_AGENT_MERGE`, `ALLOW_AGENT_DEPLOY` | `false` | Proibidos no local MVP, inclusive via preflight |
| `HITL_REQUIRED_FOR_*` | `true` | Regras de aprovação transacional |

O OpenBot é **um serviço upstream separado**: ele pode ter seu próprio `.env` e configuração do provedor Ollama na interface/banco. Não assumir que o `.env` da Factory configura automaticamente o OpenBot. Recomendações de segurança: port bind 127.0.0.1, API key e **sem `run_shell` irrestrito para bots de chat**. A documentação upstream descreve `run_shell` como não sandboxed; Tool Gateway e runner devem ficar fora desse processo. Quando `OPENBOT_WORKING_DIRECTORY` é definido, o adapter valida que seja relativo e o OpenBot confirma que o diretório existe dentro do workspace permitido.

## D. GitHub (somente se habilitado)

| Variável | Onde obter | Obrigatoriedade |
|---|---|---|
| `GITHUB_ENABLED` | `true/false` | `false` no primeiro boot offline |
| `GITHUB_AUTH_MODE` | `pat` ou `app` | escolher um |
| `GITHUB_API_URL` | `https://api.github.com` | valor padrão para GitHub.com |
| `GITHUB_OWNER`, `GITHUB_REPO` | Conta/repositório próprio | necessário para polling |
| `GITHUB_ALLOWED_REPOSITORIES` | Allowlist explícita `owner/repo` separada por vírgula | Obrigatória para aceitar eventos de webhook; HMAC válido sozinho não autoriza repositório |
| `GITHUB_TOKEN` | PAT atualmente configurado para o repositório de trabalho | somente modo `pat`; armazenado apenas no `.env` local |
| `GITHUB_APP_ID`, `GITHUB_INSTALLATION_ID`, `GITHUB_APP_PRIVATE_KEY_PATH` | GitHub App settings/installation | somente modo `app`; `.pem` fora do Git |
| `GITHUB_WEBHOOK_SECRET` | segredo gerado por você | somente webhook (não necessário no MVP) |
| `GITHUB_POLL_SECONDS`, `GITHUB_POLL_OVERLAP_SECONDS` | configuração própria | sincronização e reconciliação |
| `GITHUB_PROJECTS_ENABLED`, `GITHUB_PROJECT_V2_ID` | Projects v2 | futuro/opt-in; o client recebe o ID GraphQL do Project v2, sem número genérico |

**Estado atual:** o PAT já configurado no `.env` é usado para as operações GitHub autorizadas neste ambiente. O preflight autenticado e o worker de intake validam leitura do repositório configurado. A troca futura por uma credencial de privilégio mínimo é melhoria de hardening; não é pré-requisito para continuar o trabalho atual. Push e criação de PR continuam sujeitos às aprovações HITL específicas, vinculadas ao repositório e ao SHA. GitHub App permanece uma opção para identidade duradoura. Para Projects pessoais, credenciais podem exigir permissões diferentes de repositório; tratar como spike específico.

`GITHUB_TOKEN` no `.env` **não é** o token automático de GitHub Actions. Nenhum GitHub Secret ou pipeline remoto é necessário nesta fase.

## E. Telegram/Jira opcionais

| Serviço | Variáveis | Como obter |
|---|---|---|
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ALLOWED_CHAT_IDS`, `TELEGRAM_ALLOWED_USER_IDS`, `TELEGRAM_FACTORY_UI_URL`, `TELEGRAM_ENABLED`, `TELEGRAM_SEND_ENABLED`, `TELEGRAM_MODE`, `TELEGRAM_POLL_TIMEOUT_SECONDS` | BotFather `/newbot`; `getMe` e `getUpdates` após iniciar conversa para chat/user IDs; ambas allowlists são obrigatórias no worker; `TELEGRAM_SEND_ENABLED=false` mantém saída remota desligada até um ensaio autorizado; long polling sem webhook; decisões sensíveis apontam para a UI autenticada porque ID Telegram ainda não equivale à identidade de operador |
| Telegram webhook futuro | `TELEGRAM_WEBHOOK_SECRET` | gerar segredo local; não habilitar agora |
| Jira Cloud | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`, `JIRA_CLOUD_ID`, `JIRA_POLL_SECONDS` | token no portal Atlassian; URL e project key na instância Jira |
| Jira webhook futuro | `JIRA_WEBHOOK_SHARED_SECRET` | segredo próprio em Automation; validar header no receiver |

Para validar token Telegram sem enviar mensagem, o preflight usa `getMe`; quando `TELEGRAM_CHAT_ID` está definido, tenta `getChat`. ID do bot pode ser obtido em `getMe` e não precisa ser hardcoded.

## F. Observabilidade, segurança e extras

| Variável | Papel |
|---|---|
| `OTEL_ENABLED`, `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT` | Tracing OpenTelemetry opcional |
| `OTEL_CAPTURE_RAW_PROMPTS=false` | Evitar registrar conteúdo sensível do prompt |
| `PHOENIX_ENABLED`, `PHOENIX_BASE_URL` | Arize Phoenix self-hosted opcional |
| `GPU_METRICS_ENABLED`, `METRICS_SAMPLE_INTERVAL_SECONDS` | Métricas NVIDIA locais |
| `ARTIFACT_RETENTION_DAYS`, `TRACE_RETENTION_DAYS` | Limpeza e privacidade |
| `SONAR_ENABLED`, `SONAR_HOST_URL`, `SONAR_PROJECT_KEY`, `SONAR_TOKEN` | SonarQube local opt-in |
| `SECURITY_SCAN_ENABLED`, `ZAP_ENABLED`, `LOAD_TEST_ENABLED` | Quality gates opcionais por perfil |
| `REMOTE_LLM_ENABLED`, `REMOTE_LLM_API_KEY`, `HF_TOKEN` | Por padrão `false` ou vazio; não exigidos por LLM local |

## G. Preflight: como evitar perder tempo com erro de configuração

1. **Preparar**: `python scripts/setup_local_env.py` (executar interativamente, sem fornecer senha ao agente).
2. **Offline (sem network)**: `python scripts/validate_env.py --env .env --mode local --require core,ollama,postgres,redis`.
3. **Subir Postgres/Redis**: `docker compose --env-file .env -f infra/compose/base.yml up -d`.
4. **Live local**: `python scripts/validate_env.py --env .env --mode live --require core,ollama,postgres,redis` (instalar `scripts/requirements-preflight.txt` para probes de PostgreSQL/Redis).
5. **GitHub depois**: alterar `GITHUB_ENABLED=true`, preencher token e revalidar `--require github`.
6. **OpenBot depois**: `OPENBOT_ENABLED=true`, setar `OPENBOT_API_KEY`, confirmar health path e revalidar `--require openbot`. Sem `OPENBOT_AUTH_PROBE_PATH` live valida conectividade apenas, não a chave.
7. **Telegram/Jira/Phoenix/Sonar**: habilitar um por vez, confirmar e registrar check JSON no dashboard.

Códigos: `0 PASS` (atenção: status individual pode indicar validação parcial, por exemplo OpenBot health), `1 CONFIG/AUTH inválida`, `2 SERVICE/NETWORK/DEPENDENCY erro operacional`. **Não imprimir variáveis no terminal**. O script não faz escrita no GitHub, não envia mensagens Telegram e não executa inferência LLM. `local` só testa forma/exigência; `live` prova conectividade para probes implementados, não substitui teste de permissão de escrita ou E2E.

## H. Segurança e uso no Windows

- Windows + Docker Desktop/WSL: rotas `127.0.0.1` funcionam no host adequado; bridge `host.docker.internal` normalmente é o destino do host em contêiner Docker Desktop, mas precisa de teste em seu setup. Não copie cegamente a URL do container para o host.
- Preferir não executar o projeto como Administrator. Definir ACL de `.env`/PEM apenas para seu usuário; chmod 0600 do script é melhor esforço em sistemas POSIX.
- `git check-ignore .env`, `git check-ignore .runtime`, `git check-ignore '*.pem'` devem corresponder; **gitignored não é criptografado**. Nunca enviar o ZIP com o `.env` preenchido.
- Teste `preflight` depois de rotacionar token, trocar modelo ou mudar Docker networking; logue somente `reason code` e latência.
