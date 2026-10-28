# Agentic Factory Local v2 — RUNBOOK de implantação e operação

> Revisão documental 2026-10-27: iniciar pelo [state](../state.md) e pelo [roteiro das 12 pendências](10-FECHAMENTO-DAS-12-PENDENCIAS.md). Instruções de instalação abaixo são referência; não reiniciar bootstrap/M0 em ambiente já preparado. O worker/coordenador operacional ainda precisa de composição versionada C0; não confundir boot das APIs com execução autônoma.

## 0. O que existe hoje neste pacote?

O cadastro e os componentes de API/UI, Task Engine, contexto, OpenBot, LangGraph, execução, qualidade e evals possuem implementação. Há evidência histórica de persistência PostgreSQL e testes atuais, mas o fluxo agêntico completo ainda não está integrado/validado. A [auditoria atual](../docs/auditoria-projeto-2026-10-24.md) e o [plano de fechamento](08-PLANO-CONCLUSAO-E2E.md) prevalecem sobre afirmações históricas. FAC-100/106 fecham instalação e boot/supervisão por perfil.

## 1. Pré-requisitos no computador

- Git, Python 3.12+ (script de preflight suporta 3.11+), `uv`, Docker Desktop com Docker Compose v2; para React, Node.js LTS + `pnpm`/Corepack.
- Ollama instalado no host, driver NVIDIA e GPU RTX 4060 Ti 8 GB; `nvidia-smi` disponível para diagnósticos, quando aplicável.
- Espaço de disco para modelos Ollama + imagens Docker + worktrees. Evite subir Sonar + Phoenix + múltiplos modelos simultaneamente na primeira sessão.
- Seu PC local continua sendo responsável por workflows/agentes. Sem necessidade de GitHub Secrets, CI remoto, túnel, LangSmith ou VPS.

## 2. Primeira instalação segura

### Passo 1 — Inspecionar arquivos / segredos

```bash
git status --short
uv run --frozen pytest -q
# Apenas valida sintaxe JSON, não completude/dependências do plano:
python -m json.tool specs/implementation-backlog.json > /dev/null
```

### Passo 2 — Criar `.env` local com segredos únicos

Em instalação nova, usar o utilitário abaixo. No checkout auditado, `.env` já está configurado e contém credenciais; não refazer setup nem substituir o arquivo durante uma validação.

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

### Passo 5 — Iniciar apps existentes

```bash
# Cada comando permanece ativo; usar terminais próprios e parar com Ctrl+C.
python scripts/local_boot.py --factory
python scripts/local_boot.py
```

Use `make doctor` para Registry, `make doctor-factory` para API/DB/Redis da
fábrica, e `make doctor-agent` para exigir também modelos Ollama configurados.

Workers de intake são opt-in e separados da API. Configure `TELEGRAM_ENABLED` e as
duas allowlists para `make telegram-intake`; para GitHub configure `GITHUB_ENABLED`,
`GITHUB_AUTH_MODE=pat`, `GITHUB_OWNER`, `GITHUB_REPO`, `GITHUB_TOKEN` somente leitura
e execute `make github-intake`. Use `--once` diretamente no script para um ciclo
controlado. O polling GitHub consulta Issues abertas e fechadas, grava snapshots
versionados no EventInbox junto da demanda e avança o cursor somente após sucesso;
nenhuma escrita é feita no provedor.
Cada linha JSON distingue serviço configurado, alcançável e funcional; chaves e
URLs com credenciais não aparecem na saída. OpenBot é verificado com health e
probe autenticado somente quando habilitado.

Instalar previamente dependências conforme os READMEs. FAC-100 deve corrigir diferenças de import no comando raiz versus ambiente do pytest; FAC-106 fecha o boot por perfil. Os scripts acima iniciam APIs/UIs, sem coordenador completo de agentes.

## 3. Entrada de tarefas sem expor URL pública

Manual e intake Telegram têm implementação. GitHub/Jira/Projects e retorno
bidirecional ainda precisam do fechamento operacional descrito em FAC-120–128.
As frequências e modos abaixo são referências de desenho, não processos já ativos.

**Modo 1 (P0):** pela UI, criar Demand manual, vincular descrição e selecionar tipo bug/feature/security. **Modo 2 (P0):** GitHub Issues por polling a cada 120s, com cursor persistido no DB, escopo fixo ao único repo; o evento pode ser buscado depois que PC reiniciar. **Modo 3 (P1):** Telegram `getUpdates` long polling com allowlist e `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` e `TELEGRAM_ALLOWED_USER_IDS`; nenhum webhook/túnel é requerido. **Modo 4 (P2):** Jira polling e GitHub Projects v2. Webhooks ficam para outra fase.

Quando habilitar GitHub: preencher `GITHUB_ENABLED=true`, `GITHUB_OWNER`, `GITHUB_REPO`, `GITHUB_AUTH_MODE=pat`, `GITHUB_TOKEN`; validar:

```bash
python scripts/validate_env.py --env .env --mode local --require github
python scripts/validate_env.py --env .env --mode live --require github
```

Preflight PAT autentica `/user`; não prova acesso ao repo, polling operacional nem permissão de PR. Owner/repo precisam ser fornecidos ao cliente com política fixa em FAC-122. Publicação exige FAC-127 e decisões específicas.

## 4. Processo diário: issue -> tarefas -> execução

Fluxo alvo a concluir em FAC-110–139; os componentes isolados atuais não
executam automaticamente toda esta sequência.

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

Os gates foram corrigidos em 2026-10-25. `make quality` e `make quality-fast` rodam lint, builds, contrato OpenAPI e evals para feedback funcional rápido. `make quality-full` executa testes, browsers/PostgreSQL, SAST/SCA/secrets, DAST, Sonar local em Docker e Locust por último; reservar para o fechamento da onda de features. `make quality-up` prepara apenas os alvos; `make quality-down` remove somente a stack descartável. O agregador verifica run, snapshot e hashes dos artefatos. Ver [runbook de qualidade](../docs/quality-gates-runbook.md) para instalação, portas, limiares e limites. FAC-105/117 ainda exigem integração com task/attempt e execução autônoma.

## 7. Métricas, evals e performance

Usar fakes nos testes determinísticos; ensaios deliberados de autonomia e integração exigem Ollama real, além dos benchmarks. Medir per task `first_pass_success`, `tasks_accepted/hour`, `rework`, `input/output tokens`, `load_duration`, `eval_duration`, uso GPU/VRAM e tempo esperando aprovação. Evals por persona + Human-in-the-Loop. Reexecutar pares de prompts no mesmo fixture com budgets iguais. Controlar quantização/tag e contexto. Phoenix/OTel só quando fase P12: self-hosted, não bloqueante, sem LangSmith obrigatório.

## 8. Parada, backup e recuperação

```bash
docker compose --env-file .env -f infra/compose/base.yml stop
# Ao reiniciar a fábrica depois de implementar workers, reconcile todos os leases expirados
# Não executar docker compose down -v sem backup e consentimento explícito: apaga dados!
```

Backup/restore de banco existem; recuperação do conjunto com artefatos/OpenBot/checkpoints/GC permanece em FAC-138. Checkpoints duráveis usam PostgreSQL. Nunca executar `git clean -fdx` em home/repo da fábrica, pois poderia apagar `.env`, trabalhos e artefatos.

## 9. Gestão de segredos e escopo de publicação

- `.env` do checkout auditado contém credenciais e não deve ser compartilhado ou impresso.
- Toda chave externa no backend/conector, nunca no OpenBot prompt/thread nem no React.
- GitHub PAT fine-grained para leitura inicial; GitHub App depois; sem GitHub Secrets ou CI neste estágio.
- Integração OpenBot upstream no host/contêiner isolado; ferramenta shell livre indisponível para chat.
- Projeto destino fixo: o monorepo atual, path default `apps/customer-registry/**`. Mudanças de `agents/policies/**` ou `packages/task-engine/**` requerem HITL reforçado.

## 10. Próximo comando sugerido para a IA implementadora

Ler `07-INSTRUCOES-PARA-AGENTE-CODING.md` e `10-FECHAMENTO-DAS-12-PENDENCIAS.md`; executar C0 e a ordem das 12 abertas. FAC-100–109 já têm marcos de componente concluídos. Confirmar o worker versionado e as aprovações antes de novas demos; não reiniciar M0. Commit/push/merge seguem autorização do escopo.
