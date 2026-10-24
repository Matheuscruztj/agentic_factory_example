# 06 — Preflight de ambiente e credenciais (LOCAL-ONLY)

**Status:** adendo para implementação da Agentic Factory. **Não adicionar GitHub Actions, GitHub Secrets, deployment ou testes remotos nesta etapa.**

## Propósito

Antes de iniciar FastAPI, React, OpenBot, LangGraph, Ollama ou os workers, rodar um **preflight read-only** para separar falhas em `CONFIG` (variável ausente/formato), `AUTH` (credencial inválida/permissão negada), `NETWORK` (serviço inacessível), `SERVICE` (serviço responde inadequadamente) e erros de aplicação posteriores. O script está em `scripts/validate_env.py` e os testes em `tests/test_validate_env.py`.

O preflight não altera Issues, envia mensagens no Telegram, cria PRs, executa migrations ou inicializa workloads de LLM. Apenas consulta endpoints de leitura ou executa `SELECT 1` / `PING`. Todos os testes com terceiros só ocorrem ao passar `--mode live` explicitamente.

## Pré-requisitos locais

- Python 3.11 ou superior (preferência Python 3.12+). Modo `local` usa somente biblioteca padrão.
- Modo `live` com GitHub PAT, Telegram, Jira, Ollama e SonarQube: biblioteca padrão suficiente.
- Para GitHub App + PEM: instalar `cryptography` no ambiente do preflight (`uv add cryptography`, no projeto; `uv run` para executar).
- Para PostgreSQL em `live`: `psycopg[binary]`; para Redis em `live`: `redis`.
- Arquivo `.env` real na raiz do repositório, fora do Git. Usar `.env.example` como modelo sem chaves verdadeiras.
- Python deve rodar no **mesmo contexto de rede** que a API real: no host `localhost`, no contêiner nomes do Docker Compose. Exemplo: `OLLAMA_BASE_URL=http://host.docker.internal:11434` em Docker no Windows, se Ollama está no host.

## Comandos operacionais (somente local)

```bash
# 1. Antes de iniciar a aplicação: verificar variáveis/formato. NÃO acessa a internet.
python scripts/validate_env.py --env .env --mode local --require github,ollama,postgres,redis

# 2. Quando os serviços locais estiverem de pé: conexão e credenciais, somente leitura.
python scripts/validate_env.py --env .env --mode live --require github,ollama,postgres,redis

# 3. Testar também Telegram, quando configurado.
python scripts/validate_env.py --env .env --mode live --require github,telegram,ollama,postgres,redis

# 4. Modo local offline de autoavaliação do validador (não usa credenciais).
python -m unittest discover -s tests -p 'test_validate_env.py' -q
```

**Importante:** `--require` define o conjunto obrigatório daquele comando. Serviços opcionais habilitados por `<NOME>_ENABLED=true` também serão validados. Se nenhum estiver habilitado ou exigido, a saída indicará `skipped`; **zero checks executados não significa que o ambiente esteja pronto**. No bootstrap do MVP, exigir pelo menos `github,ollama,postgres,redis` e fazer `live` antes de disparar agentes.

### Contrato de saída

STDOUT: **exatamente uma linha JSON sem secrets nem URLs contendo credenciais**. Exemplos ilustrativos:

```json
{"schema":1,"check":"env-preflight","mode":"live","status":"pass","ok":1,"metrics":{"passed":4,"failed":0,"errors":0,"skipped":3,"duration_ms":420},"checks":[{"service":"github","status":"pass","detail":"READ_AUTH_VALIDATED_PERMISSIONS_NOT_PROVEN","duration_ms":97}]}
```

```json
{"schema":1,"check":"env-preflight","mode":"live","status":"fail","ok":0,"metrics":{"passed":2,"failed":1,"errors":0,"skipped":4,"duration_ms":500},"checks":[{"service":"telegram","status":"fail","category":"AUTH","reason":"HTTP_401"}]}
```

- Exit **0**: todas as checagens exigidas/habilitadas passaram no nível de teste realizado; `--mode local` **não valida a autenticidade de tokens**.
- Exit **1**: falha comprovada de configuração (`CONFIG`) ou autenticação (`AUTH`): corrigir `.env` ou credenciais antes de depurar a aplicação.
- Exit **2**: serviço inacessível, resposta inválida, dependência de preflight ausente ou problema operacional: verificar rede, serviços e ambiente antes de culpar o código de negócio.
- Checks podem produzir `pass`, `fail`, `error` ou `skipped`; `duration_ms` disponível por integração aprovada.
- Nunca usar este preflight para provar permissão de escrita: chamadas de leitura ao GitHub não confirmam capacidade de criar PR; `getMe` não confirma capacidade de enviar mensagem a um chat.

## Integrações cobertas

| Serviço | Variáveis principais | Validação local | Validação live, read-only | O que NÃO prova |
|---|---|---|---|---|
| GitHub fine-grained PAT | `GITHUB_AUTH_MODE=pat`, `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO` | presença, owner/repo | GET `/repos/{owner}/{repo}` autenticado | permissão de escrita, Issues/PR/Projects |
| GitHub App | `GITHUB_AUTH_MODE=app`, `GITHUB_APP_ID`, `GITHUB_INSTALLATION_ID`, `GITHUB_APP_PRIVATE_KEY_PATH`, owner/repo | campos e PEM existente | JWT assinado localmente; GET `/app` e instalação | geração de installation token, acesso ao repo, escopos de escrita |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` opcional | padrão do token | `getMe` e `getChat` se Chat ID informado | direito de enviar para o chat, polling funcionando |
| Jira Cloud | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` opcional | formato URL e campos | GET `/rest/api/3/myself` (+ project opcional) | alteração de Issues, webhook |
| Ollama | `OLLAMA_BASE_URL`, `OLLAMA_MODEL_CODING`, `OLLAMA_MODEL_JUDGE` | URL e campos | GET `/api/tags`, existência dos modelos especificados | inferência, memória VRAM, qualidade |
| SonarQube | `SONAR_HOST_URL`, `SONAR_TOKEN` | URL e token | GET `/api/authentication/validate` | permissão de análise ou existência do projeto |
| PostgreSQL | `DATABASE_URL` | formato da URL | `SELECT 1` via `psycopg` | migrations e privilégios DDL |
| Redis | `REDIS_URL` | formato da URL | `PING` via `redis` | permissão para gravar jobs |

O GitHub App é o padrão preferencial para a integração permanente. O PAT fine-grained é permitido no bootstrap local e deve ficar restrito ao único repositório. Não usar PAT classic por padrão. **Nenhuma chave `.pem`, token ou `.env` real pode entrar no Git**.

## Pipeline LOCAL e gates

O comando `make preflight` (ou equivalente `uv run python scripts/validate_env.py ...`) será executado manualmente ou antes de iniciar os agentes, preferencialmente após iniciar PostgreSQL/Redis/Ollama locais. O backend deve registrar o resultado resumido e bloquear o início de novas execuções se `--mode live` produzir 1 ou 2 para serviços necessários. Isso não deve apagar jobs nem desativar aprovações já registradas.

Ordem: `preflight --mode local` → `docker compose up -d` → `preflight --mode live` no host/contêiner apropriado → migrations → API/worker/React → smoke local com Fake LLM → benchmark real opcional. O smoke local só roda se o preflight passar.

Para CI no futuro, criar design separado. **Nesta fase não cadastrar secrets no GitHub e não depender de GitHub Actions** para verificar credenciais da máquina.

## Segurança operacional

1. Endpoints `getMe`, GET do GitHub/Jira, `SELECT 1` e `PING` não alteram dados. Não usar POST de teste nem mensagens de Telegram só para confirmar configuração.
2. Nunca imprimir tokens, chaves privadas, senhas, URL com credenciais, request/response bodies, stack traces ou variáveis completas no stdout; não enviar esse JSON a um LLM contendo dados sensíveis.
3. Timeout curto por integração (`--timeout 8` por padrão), sem retries agressivos nem múltiplas requisições de inferência.
4. Garantir que o `.env` não seja comitado (`.gitignore` e scanner de secrets); restringir permissões do PEM.
5. Uma falha de autenticação do GitHub/Jira pode ser também permissão insuficiente; verificar o erro específico no provedor. O validador é diagnóstico, não certificação exaustiva.
6. `HTTP_429` ou indisponibilidade do provedor é `2`, não credencial inválida.
7. Modo `local` confirma formato e presença, **não validade nem expiração real**; executar `live` ao menos uma vez antes de começar a trabalhar.
8. O parser `.env` é propositalmente limitado (sem interpolação de variáveis nem escapes complexos); ajustar o arquivo a valores literais ou usar loader padronizado na integração futura. Não duplicar variáveis.

## Critérios de aceite — PRE-001 a PRE-010

- PRE-001: instalação local; execução em Python 3.11+.
- PRE-002: sintaxe, duplicação e ausência de campos em `.env` detectadas.
- PRE-003: live autentica GitHub, Telegram e Jira por consultas de leitura, quando habilitados.
- PRE-004: live verifica presença de modelos Ollama sem gerar tokens.
- PRE-005: live verifica Sonar local, PostgreSQL e Redis quando habilitados.
- PRE-006: saída JSON compacta com códigos 0/1/2 e motivos categorizados.
- PRE-007: stdout nunca contém segredos, senhas ou PEM.
- PRE-008: testes offline usam mocks; nenhum contato real com terceiros.
- PRE-009: bootstrap não inicia agentes com dependências obrigatórias reprovadas.
- PRE-010: nenhuma modificação em GitHub Actions, GitHub Secrets ou implantação remota.

### Testes de aceitação

Executar `python -m unittest discover -s tests -p 'test_validate_env.py' -q`; checar que falhas têm códigos distintos e que o modo offline não dispara requisições. O arquivo fornecido é um **script de preflight de referência executável**, não uma afirmação de que seus tokens foram testados: o usuário precisará fornecer `.env` localmente para autenticação live.
