# Quality gates locais — operação e cobertura

Atualizado em 2026-10-25. Esta etapa implementa e valida a infraestrutura de qualidade solicitada após a auditoria. O aceite de uma fábrica autônoma continua no [plano E2E](../specs/08-PLANO-CONCLUSAO-E2E.md).

## Executar

Pré-requisitos: Docker com Compose, uv, pnpm e Chromium do Playwright. Instalação das dependências, a partir da raiz:

```bash
uv sync --frozen --all-packages --group api
pnpm --dir apps/factory-web install --frozen-lockfile
pnpm --dir apps/customer-registry/web install --frozen-lockfile
pnpm --dir apps/factory-web exec playwright install chromium
pnpm --dir apps/customer-registry/web exec playwright install chromium
make quality-fast
```

Há dois comandos de ciclo, com um único JSON e exit code `0`/`1`/`2` cada:

```bash
# Ciclo rápido padrão: lint, TypeScript/build, contrato OpenAPI e evals
make quality
# Equivalente explícito
make quality-fast

# Fechamento completo: testes/E2E, SAST/SCA/secrets, DAST, Sonar local e perf no final
make quality-full
```

`make quality` é o alias curto para `quality-fast`. O fast executa Ruff, ESLint,
TypeScript, build de Factory/Registry, drift OpenAPI, integridade dos datasets,
eval determinístico de contexto e calibração local do Judge. Não executa pytest,
Vitest, E2E, scanners ou carga; esses ficam para o fechamento completo ou a fase
de melhoria de qualidade.

`make quality-full` executa os gates completos: Python com mypy/pytest,
frontend com Vitest/ESLint/TypeScript/build, E2E dos dois produtos,
SAST/SCA/secrets, DAST, SonarQube local e Locust por último. Ele constrói os
frontends, gera snapshot, recria somente a stack `factory-quality-local`, migra
os dois bancos e usa PostgreSQL temporário. Os containers/volumes operacionais
não são alterados. Execuções simultâneas do coordenador completo são recusadas.

```bash
# Mecanismo interno do gate completo:
uv run --frozen --all-packages --group api python scripts/quality.py run --perf
# Apenas preparar/recriar alvos de teste, sem certificar os gates:
make quality-up
# Parar somente a stack de qualidade:
make quality-down
# Repetir scanners sem subir a stack:
make quality-security
# Repetir DAST contra a stack atual, se seu código/run ainda corresponder:
make quality-dast
```

Serviços locais de teste: Factory Web `http://127.0.0.1:18803`, Factory API `http://127.0.0.1:18801`, Registry Web `http://127.0.0.1:18804`, Registry API `http://127.0.0.1:18810`. PostgreSQL de teste fica em `127.0.0.1:18832`. Todas as portas são de loopback. A rede dos scanners é interna; os alvos também usam uma bridge para permitir as portas locais. A senha sintética do operador e os segredos de teste ficam em `.runtime/quality/private/credentials.json`, com diretório 0700 e arquivo 0600. Não se usa a senha operacional nem o `.env` do projeto. Integrações externas estão desabilitadas nos alvos.

## Gates e política

| Gate | Execução e limite |
|---|---|
| Python | Cliente OpenAPI sem drift, Ruff, mypy nos alvos explicitados no runner, pytest. No fluxo completo, os testes PostgreSQL recebem exclusivamente o banco descartável e não precisam ser ignorados. A ampliação do mypy permanece em FAC-117. |
| Frontend | Vitest, ESLint, TypeScript e build de Factory e Registry. URLs de teste são injetadas no build; os testes unitários usam sua configuração normal. |
| E2E | Chromium sobre os builds e APIs reais: demanda, SSE de auditoria e aprovação na Factory; criação, busca, edição e desativação de cliente no Registry. Teste ignorado ou suíte vazia impede PASS. |
| SAST | Bandit com achados médios e altos no relatório; altos bloqueiam. Semgrep com seis regras locais para Python e JS/TS/TSX: execução dinâmica, shell, interpolação SQL, TLS desabilitado e HTML bruto em React. Não é cobertura completa de todas as CWEs. |
| Verificação do SAST | Fixtures isoladas em `infra/security/canaries`: sete achados esperados exercitam as seis regras; chamada benigna ao runner não deve ser sinalizada. A fixture nunca é executada. Regra removida ou scanner incompleto gera erro. |
| Dependências e secrets | `uv export` de todo o workspace e grupos, pip-audit, pnpm audit dos dois lockfiles, Gitleaks sobre snapshot sanitizado. Advisory Python bloqueia quando não há severidade; Node high/critical e qualquer secret detectado bloqueiam. |
| DAST | ZAP Baseline passivo nas duas interfaces e ZAP API Scan ativo sobre os OpenAPIs das duas APIs. Altos/críticos bloqueiam; médios/baixos continuam registrados. Relatório ausente, nenhum URL alcançado ou falha operacional gera erro. |

As imagens de Python, PostgreSQL, nginx, Semgrep, Gitleaks e ZAP estão fixadas por digest. As regras Semgrep são locais, sem envio para SaaS. O snapshot exclui segredos também em diretórios aninhados, dependências, caches e dados operacionais.

O ZAP recebe uma sessão sintética e header CSRF restritos ao hostname da Factory de teste. Antes da varredura, um smoke exige 401 sem login, 200 com login e 403 na escrita sem CSRF. A superfície ativa da Factory limita-se a demandas, tarefas e aprovações. Conversas/LLM, run-fake, webhooks, publicação, releases, observabilidade e SSE não são alvo desse scan; o SSE é coberto pelo E2E. O arquivo `dast/coverage.json` enumera os paths incluídos e excluídos. Importar um path com parâmetro não prova todas as combinações de IDs ou todos os estados de negócio.

ZAP distingue alertas de falhas operacionais: seus exits 0/1/2 são interpretados junto com o JSON e a política de severidade; exit 3 impede aprovação. `-I` evita tratar avisos como erro operacional, mantendo-os no relatório. Ver [API Scan oficial](https://www.zaproxy.org/docs/docker/api-scan/) e [Baseline oficial](https://www.zaproxy.org/docs/docker/baseline-scan/). As regras locais seguem a operação documentada do [Semgrep OSS](https://docs.semgrep.dev/deployment/oss-deployment).

## Evidências e resultado

Cada execução gera `.runtime/quality/runs/<run_id>/source-manifest.json` e logs/relatórios. O agregado completo do core fica em `aggregate.json`; o fast e o full têm seus próprios JSONs. `.runtime/quality/aggregate.json` aponta para o último core completo. Resultados registram `run_id`, Git HEAD, SHA-256 do conteúdo do checkout (incluindo arquivos novos) e hashes dos artefatos. Mudança de código durante a execução impede aprovação; os alvos também carregam labels do run/snapshot. Um JSON velho, outro run, artefato modificado ou gate completo ausente não produz PASS.

O validador não aceita mais `{schema:1,ok:1}`. O agregado completo pode ser conferido com:

```bash
uv run --frozen --all-packages --group api python scripts/quality_aggregate.py --run-id ID_DA_EXECUCAO
```

Contrato dos runners: `0` passou pela política, `1` reprovação por teste/achado, `2` problema operacional, configuração ou evidência inválida. Não equivale a zero avisos. Os relatórios de scanner e os logs preservam os achados menores; credenciais sintéticas são removidas dos artefatos textuais. Traces de browser ficam desabilitados nessa stack para não guardar ações de login com senha.

Reexecutar um gate no mesmo run atualiza seus artefatos e invalida agregado anterior cujo hash mudou. Para aceite completo execute `make quality-full`; para feedback cotidiano use `make quality-fast`. Os diretórios locais não são armazenamento imutável nem substituem o registro autoritativo de task/attempt/modelo previsto em FAC-105.

## Sonar e performance no fechamento completo

```bash
make quality-full
```

O `quality-full` lê o token Sonar do `.env` sem imprimi-lo e usa a instância
Docker local em `127.0.0.1:9001`. Primeiro executa todos os gates funcionais e
de segurança; depois roda Sonar; Locust roda por último. Esse perfil é um smoke
de liveness e não substitui benchmark do agente/LLM ou teste de carga de negócio.

Para subir SonarQube Community local isolado dos stacks de qualidade, use
`docker compose --env-file .env -f infra/compose/sonar-local.yml up -d --wait`.
Ele publica somente em `127.0.0.1:9001` e persiste dados em volumes locais.
Configure `SONAR_HOST_URL=http://127.0.0.1:9001`, `SONAR_ENABLED=true` e um
token de usuário com permissão de análise; o token fica apenas no `.env` com
permissão 0600. A senha administrativa inicial rotacionada fica em
`.runtime/sonar-admin-password.txt` (permissão 0600). Para parar sem apagar os dados:
`docker compose --env-file .env -f infra/compose/sonar-local.yml stop`.

Sonar Community é local e isolado dos alvos de qualidade. `sonar-local.yml` inclui scanner com imagem presa por digest no mesmo projeto/rede Docker da instância local; o runner monta o snapshot sanitizado para análise. Mantenha `SONAR_HOST_URL=http://127.0.0.1:9001` e token de análise no `.env` (0600). O `quality-full` inicia/aguarda `sonarqube`; o scanner usa o DNS interno `sonarqube:9000`. Em 2026-10-25, o Quality Gate do projeto `agentic-factory-local` passou (run `20261025T210718Z-9b7fa6ff`); o smoke Locust anterior passou com 24 requisições/zero falhas (`20261025T210851Z-58077717`). FAC-074 é concluída no nível de componente. A operação SAST completa inclui Semgrep + Bandit, independente do Sonar.

O Sonar analisa o código para bugs e segurança, mas não usa testes/E2E, migrations, CLIs auxiliares ou componentes web no percentual de cobertura. As aplicações web são verificadas por Playwright, Vitest, lint, tipos e build; APIs e domínio Python mantêm a cobertura Sonar. CLIs e rotinas auxiliares são verificadas por contratos, lint e testes Python. Essas exclusões evitam cobrar cobertura unitária de arquivos exercitados por outras suítes, sem retirá-los das análises estáticas; a configuração está versionada em `sonar-project.properties`. O `quality-full` provisiona o gate local `A-Fabric Local` a partir do gate padrão Sonar, preserva a exigência de zero violações novas e usa mínimo de 78% de cobertura nova Python para comportar esta base atual; o scanner inclui essa configuração em cada execução.

## Pendências de qualidade

FAC-153 registra os achados menores reproduzidos: NUL em filtros que chega ao banco e retorna 500, headers ausentes nas APIs, diretivas CSP/inline style, avisos Bandit e advisories moderados de frontend. O agente não deve criar suppressions para liberar um gate. FAC-105/117 ainda exigem integração com task/attempt, sandbox do executor, seleção por impacto, cobertura de tipos e retrabalho limitado do agente. Jornadas com LLM e canais externos continuam pendentes; a stack saudável não comprova a fábrica completa.
