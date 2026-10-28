# Auditoria de fechamento — 2026-10-27

Entrada: 174 atividades, 163 done / 11 in_progress. Saída: 164 done / 10 in_progress.
FAC-135 aceita; outras atividades não foram promovidas.

## Evidência de FAC-135

- Jornada assistida existente: afd40e20cc5b; run d6f4fc7f-9a66-48d0-b7fd-40572fe90c26.
- Readback atual no PostgreSQL descartável: assert_completion_evidence passou;
  todos os arquivos de Artifact têm SHA-256 igual ao banco.
- Approval 2026-10-27 05:39:30.714733 UTC precede início do run
  2026-10-27 05:39:31.379321 UTC.
- Baseline exit 1; resultado 8ae305e521955640377f1fe97edc1efbdf36a5da,
  nove testes verdes. Nenhuma nova geração ou repetição dessa jornada foi necessária.
- Revisão de atividade executada nesta sessão: receipt 2e810762d7e27f4973e7,
  qwen2.5-coder:7b, approve/pass, confidence 1.0, executor codex-assisted.
- Antes de alterar status: HMAC, definição, prompt, resposta, manifest e hashes
  de artefatos verificados. Operador sintético identificado; nenhuma assinatura humana.

## Correção e validação

--demand-id agora restringe plan_pending e dispatch, além de execute_one.
Planejamento filtra antes de aplicar limit. A CLI --once retorna 1 se planejamento
falhar ou aguardar retry, mesmo que execução esteja idle.

Comandos executados após a alteração:

```bash
uv run --frozen --all-packages --group api pytest -q tests/workflows/test_local_worker.py tests/acceptance/test_global_candidate.py tests/acceptance/test_ai_acceptance_receipts.py tests/acceptance/test_uat_report_pending.py tests/agents/test_execution_safety_acceptance.py
uv run --frozen ruff check workers/src/factory_workers/planning.py workers/src/factory_workers/runner.py scripts/factory_worker.py tests/workflows/test_local_worker.py
```

Resultado: 42 passed em 6,33 s; Ruff All checks passed. As suites usam fakes/SQLite
onde declarado, não certificam os pilotos de canal nem a matriz PostgreSQL R01–R12.
Sem novo quality-full, benchmark, envio externo ou mudança em secrets.

## Pendências preservadas

FAC-121, FAC-130–134 e FAC-136–139. Ver tabela operacional em state.md e passos
em specs/10-FECHAMENTO-DAS-12-PENDENCIAS.md. Worker, guards e emissor global já
existiam; documentação anterior incorretamente os tratava como não implementados.
Provas integrais dos pilotos e pacote global continuam ausentes.
