# Agentic Factory Local v2 — RUNBOOK de implantação e operação

## 0. O que existe hoje neste pacote?

**Já executáveis:** `scripts/validate_env.py`, `scripts/setup_local_env.py`, `scripts/validate_checks.py`, `scripts/local_boot.py`, `scripts/doctor.py`, `tests/` e a configuração `infra/compose/base.yml`. O Customer Registry já oferece CRUD local com SQLite e UI React; a Factory API/UI já têm health, autenticação local e painel sanitizado em estado inicial. **Ainda pendentes:** boot e persistência PostgreSQL verificados com volumes, E2E, Task Engine, OpenBot adapter, LangGraph, ferramentas de execução, evals e workflows. Este pacote NÃO afirma que a fábrica já está pronta.

## 1. Pré-requisitos no computador

- Git, Python 3.12+ (script de preflight suporta 3.11+), `uv`, Docker Desktop com Docker Compose v2; para React, Node.js LTS + `pnpm`/Corepack.
- Ollama instalado no host, driver NVIDIA e GPU RTX 4060 Ti 8 GB; `nvidia-smi` disponível para diagnósticos, quando aplicável.
- Espaço de disco para modelos Ollama + imagens Docker + worktrees. Evite subir Sonar + Phoenix + múltiplos modelos simultaneamente na primeira sessão.
- Seu PC local continua sendo responsável por workflows/agentes. Sem necessidade de GitHub Secrets, CI remoto, túnel, LangSmith ou VPS.

## 2. Primeira instalação segura

### Passo 1 — Inspecionar arquivos / segredos

```bash
git status --short  # deve ser executado somente após integrar estes arquivos ao seu repo
python -m unittest discover -s tests -p 'test_*.py' -q
python scripts/validate_task_plan.py --file docs/03-TASKS-POR-FASES.md
```

### Passo 2 — Criar `.env` local com segredos únicos

O ZIP contém `.env` **somente com placeholders**. Execute:

```bash
python scripts/setup_local_env.py
```

Ele pede uma senha de operador **diretamente no seu terminal**, gera `APP_SECRET_KEY`, `POSTGRES_PASSWORD` e hash scrypt (a senha não é enviada a IA, não é escrita em claro, nem aparece em stdout). Não sobrescreve `.env` previamente preenchido. No Windows, confirme permissões do arquivo em sua conta; em Unix, aplica chmod 0600. Se quiser editar sem script, copie `.env.example` para `.env`, substitua **TODOS** os placeholders e gere um hash compatível com o serviço de autenticação a implementar.

Verificar:

```bash
python scripts/validate_env.py --env .env --mode local --require core,postgres,redis,ollama
```

**Importante:** `local` confirma sintaxe e campos; não confirma se token externo ou serviço está vivo. `core` também rejeita `ALLOW_AGENT_MERGE=true` e `ALLOW_AGENT_DEPLOY=true` no MVP.

### Passo 3 — Subir infraestrutura mínima

```bash
docker compose --env-file .env -f infra/compose/base.yml up -d
docker compose --env-file .env -f infra/compose/base.yml ps
```

Volumes duráveis no Docker para `factory` (DB padrão) e `customer_registry` (segundo DB criado no primeiro bootstrap de um volume novo). Se você já usa Postgres/Redis em 5432/6379, altere portas do compose e ambas URLs host/contêiner coerentemente.

Instalar dependências opcionais para probes do preflight no venv local:

```bash
python -m pip install -r scripts/requirements-preflight.txt
python scripts/validate_env.py --env .env --mode live --require core,postgres,redis
```

**Observação:** `pip install` acima é um comando provisório para o ambiente de preflight; depois do bootstrap `uv`, essas libs entram no lockfile Python. Não instalar globalmente se seu Python principal for gerenciado pelo sistema; preferir venv.

### Passo 4 — Ollama host: baixar só o essencial

```bash
ollama list
ollama pull qwen3:4b
ollama pull qwen2.5-coder:7b
# Ativar Judge após o MVP de Evals, não obrigatório no primeiro dia:
# ollama pull qwen3:8b
ollama ps
```

Como o `.env` declara também `OLLAMA_MODEL_JUDGE=qwen3:8b`, `--mode live --require ollama` só passa quando ele também estiver instalado. Se quiser economizar armazenamento/VRAM neste estágio, deixe `OLLAMA_MODEL_JUDGE=` **temporariamente vazio** e `LLM_JUDGE_ENABLED=false`; o preflight ignora modelo não declarado. Na evolução P11, instale e preencha. Confirme `OLLAMA_BASE_URL` pela API local e valide:

```bash
python scripts/validate_env.py --env .env --mode live --require ollama
```

`ollama ps` confirma se os pesos estão em GPU, CPU ou mistos após iniciar um modelo. Inicie com contexto de 4096, 1 requisição LLM ativa, sem prometer tokens/s antes da medição.

### Passo 5 — Iniciar apps somente DEPOIS de implementadas P01–P02

```bash
# PLANEJADO — executável apenas após gerar FastAPI apps, pyproject e package.json
uv sync
uv run uvicorn factory_api.main:app --host 127.0.0.1 --port 8001
pnpm --dir apps/factory-web dev --host 127.0.0.1 --port 5173
# registry API + web seguem comandos do README criado na P02
```

**Não executar esses comandos e concluir que há erro de configuração antes de implementar as apps.** Eles são contratos operacionais-alvo, não scripts que já estão presentes no pacote.

## 3. Entrada de tarefas sem expor URL pública

**Modo 1 (P0):** pela UI, criar Demand manual, vincular descrição e selecionar tipo bug/feature/security. **Modo 2 (P0):** GitHub Issues por polling a cada 120s, com cursor persistido no DB, escopo fixo ao único repo; o evento pode ser buscado depois que PC reiniciar. **Modo 3 (P1):** Telegram `getUpdates` long polling com allowlist e `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` e `TELEGRAM_ALLOWED_USER_IDS`; nenhum webhook/túnel é requerido. **Modo 4 (P2):** Jira polling e GitHub Projects v2. Webhooks ficam para outra fase.

Quando habilitar GitHub: preencher `GITHUB_ENABLED=true`, `GITHUB_OWNER`, `GITHUB_REPO`, `GITHUB_AUTH_MODE=pat`, `GITHUB_TOKEN`; validar:

```bash
python scripts/validate_env.py --env .env --mode local --require github
python scripts/validate_env.py --env .env --mode live --require github
```

A verificação live confirma leitura de repo/autenticação; não prova permissão de publicar um PR. O backend deverá verificar permissões específicas antes de tentar a ação com HITL.

## 4. Processo diário: issue -> tarefas -> execução

1. Verificar `preflight` somente nas integrações envolvidas, sem gastar tokens. 2. Receber Issue manual/GitHub. 3. Analyzer coleta evidências e pergunta apenas dúvidas de negócio relevantes. 4. Humano aprova requisitos. 5. Planner gera DAG com dependências, roles e escopo. 6. Task Engine seleciona tasks `ready`, reserva por lease. 7. OpenBot permite contato direto e recebe mensagens por Issue. 8. LangGraph executa workflows **somente** quando há task autorizada. 9. Runner usa worktree+ sandbox, executa quality scripts 0/1/2. 10. Judge/Evals opcional acrescenta evidência, mas não substitui determinismo. 11. Humano revisa resultados; publicação de branch/PR somente quando habilitada e aprovada. 12. Documentar decisões, métricas e trace IDs. 13. Se depois descobrir teste faltante, chamar `@qa ISSUE-42`, criar TaskProposal de follow-up e executar só esse subworkflow.

## 5. Política de falhas e diagnóstico

| Sinal | Categoria | Ação recomendada |
|---|---|---|
| `exit 1`, `CONFIG` | variável ausente, placeholder, URL inválida | corrigir `.env`, repetir preflight local |
| `exit 1`, `AUTH` | token revogado, senha incorreta, usuário sem acesso | renovar credencial sem colá-la em chat/log |
| `exit 2`, `NETWORK` | Ollama/DB/Redis/externo indisponível | verificar serviços/porta/firewall/WSL, retry com backoff |
| `exit 2`, `SERVICE` | dependência Python, timeout, protocolo inesperado | verificar instalação/versão e consultar artifact de erro |
| `exit 1` em quality gate | código/teste/scanner encontrou reprovação | entregar somente erro/linha relevante ao agente executor |
| Judge positiva + pytest falho | divergência LLM | bloquear entrega e priorizar testes objetivos |
| Worktree concorrente com mesmo path | conflito de escopo | segurar lease e sequenciar integração |
| PR sem aprovação | ação privilegiada bloqueada | apresentar diff/evidence ao humano; nunca publicar automaticamente |

**Não** repetir chamadas LLM para erro de credencial; o agente deve retornar um resumo (`service`, `category`, `reason`, `run_id`) e aguardar intervenção humana. Erros completos ficam em `.runtime` com retenção, não no contexto por padrão.

## 6. Quality gates sem GitHub Actions

P10 implementará wrappers para Ruff/mypy/pytest, tsc/ESLint/Vitest, Playwright, Gitleaks, Bandit, Semgrep/pip-audit; scans mais caros ZAP/Locust/Sonar por flag. Cada wrapper salva log sob `.runtime/artifacts/{run_id}/` e imprime um JSON compacto. O agregado local pode validar relatórios já produzidos:

```bash
python scripts/validate_checks.py .runtime/artifacts/run-123/python.json .runtime/artifacts/run-123/web.json
```

`validate_checks.py` **já existe** neste pacote, mas os scripts geradores `quality_python.py` e `quality_web.py` serão criados na fase P10. Se ainda não houver relatórios, não inventar métricas nem dados.

## 7. Métricas, evals e performance

Usar baseline com **fake LLM** em testes sempre, e Ollama real somente em benchmark deliberado. Medir per task `first_pass_success`, `tasks_accepted/hour`, `rework`, `input/output tokens`, `load_duration`, `eval_duration`, uso GPU/VRAM e tempo esperando aprovação. Evals por persona + Human-in-the-Loop. Reexecutar pares de prompts no mesmo fixture com budgets iguais. Controlar quantização/tag e contexto. Phoenix/OTel só quando fase P12: self-hosted, não bloqueante, sem LangSmith obrigatório.

## 8. Parada, backup e recuperação

```bash
docker compose --env-file .env -f infra/compose/base.yml stop
# Ao reiniciar a fábrica depois de implementar workers, reconcile todos os leases expirados
# Não executar docker compose down -v sem backup e consentimento explícito: apaga dados!
```

Backups e teste de restauração ficam na P14; checkpoints do LangGraph devem estar em Postgres, não em memória. Nunca executar `git clean -fdx` em home/repo da fábrica, pois poderia apagar `.env`, trabalhos e artefatos.

## 9. Gestão de segredos e escopo de publicação

- `.env` local está no ZIP **sem credenciais**; após preenchido, não compartilhar/uploadar.
- Toda chave externa no backend/conector, nunca no OpenBot prompt/thread nem no React.
- GitHub PAT fine-grained para leitura inicial; GitHub App depois; sem GitHub Secrets ou CI neste estágio.
- Integração OpenBot upstream no host/contêiner isolado; ferramenta shell livre indisponível para chat.
- Projeto destino fixo: o monorepo atual, path default `apps/customer-registry/**`. Mudanças de `agents/policies/**` ou `packages/task-engine/**` requerem HITL reforçado.

## 10. Próximo comando sugerido para a IA implementadora

Veja `07-INSTRUCOES-PARA-AGENTE-CODING.md`; comece pelas dependências de P00, depois um vertical slice fake/determinístico antes do OpenBot real. Nenhuma ação de commit, push ou merge sem confirmação humana.
