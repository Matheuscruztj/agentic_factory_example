# Instrução mestre para a IA que implementará a Agentic Factory

> Este é o texto de orientação para colocar junto dos documentos no repositório. Não é um comando para autorizar escrita fora do escopo.

## Objetivo

Implementar progressivamente a **Agentic Factory local v2**, com 1 monorepo próprio e a aplicação real `customer-registry`. Seguir os documentos nesta ordem de autoridade: `01-SPECIFY-ESCOPO.md` → `02-DESIGN-ARQUITETURA.md` → `03-TASKS-POR-FASES.md` → `04-VARIAVEIS-ENV-E-SEGREDOS.md` → `05-RUNBOOK-OPERACAO-LOCAL.md`. Estes documentos substituem os antigos de NiceGUI/multi-tenant/repositórios remotos. Adaptar paths somente após inspecionar arquivos realmente presentes no repositório.

## Procedimento obrigatório a cada sessão

1. **Inspeção:** executar `git status --short`; ler diretórios atuais e a task `FAC-...`; confirmar dependeOn e spec version. Nenhum assumptions de que docs == código.
2. **Config check:** `python scripts/validate_env.py --mode local --require core,postgres,redis` quando o `.env` estiver pronto; `--mode live` só se serviços devem estar ativos. Não abrir arquivo `.env` em prompt/context; script emite códigos seguros.
3. **Plano curto:** citar task id, arquivos-alvo, impacto, testes e gates; pedir decisão humana somente para dados/ações sensíveis. Não ativar todas as skills: carregar 0–2 por task, L0-L3.
4. **Implementação:** alterações pequenas com testes, sem sobrepor trabalho de outros agentes. Usar worktree quando runtime já estiver implementado; antes disso branch local manual com aprovação do operador.
5. **Validação:** comandos determinísticos antes de chamar LLM Judge; sempre capturar códigos e métricas em uma linha JSON. Um gate que não existe deve ser marcado `not_implemented`, jamais PASS.
6. **Revisão:** resumir evidências verificáveis e links; avisar pendências ou bloqueio. `exit=2` é infra/configuração, **não** bug de código; não tentar corrigir via 10 conversas LLM.
7. **HITL:** não editar `.env`, `.pem`, políticas, agentes ativos, workflow core, nem fazer push/merge/deploy sem autorização clara. Prompts candidatos são dados, nunca nova política ativa automática.
8. **Controle de contexto:** nunca injetar logs inteiros no LLM. Se fail, carregar até 30 linhas relevantes por artifact e explicar por que mais contexto é necessário. Tool-output/compressor salva log completo fora do modelo.

## Primeiro marco de sucesso antes de LLM real

Preflight passa; Compose Postgres e Redis sobe; `customer-registry` React/FastAPI salva usuário; Task Engine aceita uma demanda manual e DAG com duas tasks; fake workers executam e atualizam states; UI mostra status; HITL bloqueia publicação; testes e status 0/1/2 são evidenciados. **Somente depois** conectar OpenBot e LangGraph reais.

## Segundo marco de sucesso com agentes reais

Enviar `@qa ISSUE-42: acrescente um teste para telefone colado` na tela do card. OpenBot responde com contexto da Issue, gera proposta vinculada, Task Engine verifica política/escopo, LangGraph executa o subworkflow QA, Test Runner passa, humano revisa diffs. Requisito original permanece com histórico preservado.

## O que não fazer

- Não substituir OpenBot por LangGraph: ambos têm responsabilidades diferentes.
- Não modificar arquitetura para multi-tenant, não criar marketplace/repository onboarding.
- Não criar GitHub Actions, GitHub Secrets, pipeline remota, VPS nem integração Jira antes de prioridade definida.
- Não declarar que Ollama model 20B/30B oferece boa performance em VRAM 8GB sem benchmark.
- Não copiar todos os dados de Issue, logs, código-fonte ou segredos para as prompts; use context pack com fonte e budget.
- Não executar `run_shell` irrestrito do OpenBot como mecanismo de sandbox.
- Não depender de LangSmith; preferência Phoenix opcional + métricas locais.

## Formato compacto de reporte ao operador

```json
{"task_id":"FAC-004","status":"pass","exit_code":0,"metrics":{"tests_passed":24,"tests_failed":0},"changed_files":2,"artifact_refs":[".runtime/artifacts/..."]}
```

No chat enviar, no máximo, resumo de alterações, resultados numéricos, risco/pendências e decisão humana requerida. Documentação detalhada permanece no repositório.
