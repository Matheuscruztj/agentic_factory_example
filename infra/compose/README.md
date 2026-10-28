# Local base services

Start PostgreSQL and Redis after generating a local `.env` with `python scripts/setup_local_env.py`:

```bash
docker compose --env-file .env -f infra/compose/base.yml up -d
docker compose --env-file .env -f infra/compose/base.yml ps
```

Both published ports bind only to `127.0.0.1`. PostgreSQL keeps persistent data in a named volume and creates `customer_registry` on first initialization. Redis is optional for app readiness and is an accelerator, never the source of truth.

Do not use `docker compose down -v` unless intentionally deleting local database data.

O `.env.example` contém os segredos gerados pelo setup, as conexões locais já
preenchidas e as credenciais das integrações opcionais. Não é necessário informar
`GITHUB_OWNER` ou `GITHUB_REPO`: o preflight verifica o PAT em `/user`; o destino
de uma operação deve ser definido na própria operação. Para GitHub App, descomente
as quatro opções correspondentes no exemplo.

As aplicações rodam no host (`python scripts/local_boot.py --factory`), portanto
as URLs usam `127.0.0.1`. O Compose já define usuário e banco `factory`, porta 5432
e Redis na porta 6379; esses valores não precisam ser repetidos no `.env`.
As antigas URLs com sufixo `_CONTAINER` não eram consumidas e foram removidas.
Se executar uma aplicação em um container na rede do Compose, configure suas URLs
com os hosts `postgres` e `redis` no ambiente desse container.

As APIs e interfaces usam suas portas locais padrão: Factory 8001/5173 e
Customer Registry 8010/5174. A autenticação local continua habilitada por padrão.
Opções avançadas continuam disponíveis onde o código as suporta, mas não precisam
constar no `.env` para usar os valores padrão.

O endpoint OTLP já aponta para Phoenix local (`http://127.0.0.1:6006`, OTLP/HTTP).
Phoenix e Sonar continuam opcionais. Ollama e OpenBot têm um Compose próprio:

```bash
python scripts/prepare_openbot.py
make ai-up
make ai-status
```

O script baixa a revisão fixa do OpenBot e aplica as alterações locais para
desabilitar `run_shell` e repassar a opção de raciocínio do Ollama. O Compose
vincula as portas ao loopback, restringe o OpenBot a uma rede interna e publica
sua API por um gateway sem ferramentas. Os modelos são `qwen3:4b` e
`qwen2.5-coder:7b`; o Judge fica opcional para não ocupar a GPU de 8 GB.
Para validar: `python scripts/validate_env.py --env .env --mode live --require ollama,openbot`.
As opções OTEL continuam reservadas: definir o endpoint não inicia um coletor nem
habilita tracing na API.


## Qualidade isolada

`quality.yml` é operado por `make quality`, `make quality-up` e `make quality-down`. Usa PostgreSQL descartável, APIs migradas e frontends compilados, com credenciais próprias. Semgrep/Bandit fazem SAST; ZAP cobre as duas interfaces e os dois OpenAPIs. Não executar esse compose com o `.env` operacional. [Instruções e limites](../../docs/quality-gates-runbook.md).
