# Pacote de revisão técnica independente por IA

**Diretriz vigente:** por solicitação do operador em 2026-10-25, o aceite técnico será feito por reviewer local de IA; assinatura humana de UAT está temporariamente substituída. A [política de aceite por IA](ai-acceptance-policy.md) define o receipt e seus limites. O procedimento de assinatura humana abaixo é histórico e não deve ser usado para o aceite atual.

Revisão de 2026-10-24: este pacote não está pronto para aceite global. A
[auditoria](auditoria-projeto-2026-10-24.md) reabriu atividades técnicas e
identificou falhas de proveniência/UAT. FAC-108/129/139 exigem fechamento e provas
das jornadas reais antes da assinatura; rótulos e um JSON de aprovação,
isoladamente, não concluem o projeto.

O arquivo [`evals/human-review-packet.json`](../evals/human-review-packet.json)
reúne os 10 rótulos provisórios de FAC-076 e os campos de decisão do UAT para
FAC-093. Os campos de reviewer, rótulo final e rationale estão intencionalmente vazios. Um reviewer de IA independente deve comparar cada item com seu fixture de origem; os rótulos atuais continuam provisórios e não viram goldset humano.

## Evidências para consulta

- Datasets e hashes congelados: [`evals/dataset-manifest.json`](../evals/dataset-manifest.json)
- Rubrica do judge: [`evals/rubrics/judge-v1.json`](../evals/rubrics/judge-v1.json)
- Última calibração local: `.runtime/evals/judge-calibration.json` (3 casos; accuracy 1.0, recall 1.0, FPR 0; labels provisórios; sem alteração de gate/aprovação)
- Scorecard de quality gates: `.runtime/quality/aggregate.json` e relatórios por gate em `.runtime/quality/`
- Smoke de inferência real: `ollama-gpu-inference-smoke` em `.runtime/acceptance-validation.json` (17 tokens de prompt, 98 tokens gerados, 11.93 s, 66.01 tokens/s; RTX 4060 Ti)
- Relatório UAT atual: [`docs/acceptance-report.md`](acceptance-report.md)

## Como concluir

1. Abra os quatro fixtures referenciados no JSON e examine critérios e evidências.
2. Não edite os labels diretamente. Um reviewer local separado do executor deve produzir decisão estruturada por caso e citar refs de evidência verificáveis.
3. O reviewer deve receber o pacote completo, operar sem tools de escrita e aprovar apenas com gates e hashes conferidos. Gere o receipt no fluxo de IA; não fabrique um JSON manualmente.
4. Após a revisão, atualize os rótulos nos fixtures, regenere o manifest e rode
   `uv run python scripts/validate_eval_datasets.py` e
   `uv run python scripts/evaluate_judge.py`.
5. Grave o receipt IA em `.runtime/artifacts/uat/ai-approval.json` e regenere o scorecard com `uv run python scripts/acceptance_report.py`.

Até o receipt por IA ser emitido e verificado, FAC-076/077 e FAC-093 devem permanecer pendentes e o scorecard deve continuar `pending_ai_acceptance`.
