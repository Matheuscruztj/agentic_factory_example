# Instrução de execução — concluir as 10 pendências restantes

Estado reconciliado em 2026-10-27: **174 atividades, 164 done, 10 in_progress**.
Ler [state.md](../state.md), [roteiro](10-FECHAMENTO-DAS-12-PENDENCIAS.md) e
`closure_plan` do [backlog](implementation-backlog.json). O nome histórico do
roteiro não representa a contagem atual. FAC-135 e FAC-142 já foram aceitas.

## Escopo e decisão vigente

As abertas são FAC-121, FAC-130–134 e FAC-136–139. Implementação Codex assistida
está autorizada em `assisted_delivery_policy`: bundle/hash/escopo anteriores ao
efeito, `executor_kind=assisted_patch`, `model_digest=null`, gates/review reais.
Não reintroduzir geração exclusiva Ollama como condição de entrega funcional.
Não chamar execução assistida de autonomia local ou aprovação humana.

FAC-142 usa referência sintética determinística já aprovada; não exigir labels
humanos. FAC-135 possui receipt independente válido; não refazer o bug CPF.
Decisões EARS delegadas permanecem válidas para o mesmo conteúdo/hash.

## Procedimento finito

1. Preservar checkout/worktrees. Ler critério e dependências da atividade escolhida.
2. Reusar worker `scripts/factory_worker.py` e emissor `scripts/global_acceptance.py`:
   já existem e têm testes. Não recriar C0. Usar filtro `--demand-id` em pilotos.
3. Conferir revisão/plano/escopo aprovado antes de efeito. Não aprovar retroativamente
   os antigos runs FAC-130 com requisito proposed; refazer apenas trilha inválida.
4. Executar a próxima linha da tabela do state. Para tags, congelar contrato/DAG,
   executar DB/BE/FE em worktrees, integrar/revisar e então follow-up QA.
5. Antes de testar, nomear o critério faltante e a prova esperada. Respeitar budget;
   repetir só após causa identificada e mudança concreta. Fakes não provam live.
6. Registrar run/attempt/SHA, comandos/gates/hash e revisão independente. Só limpar
   remaining_work quando cada critério tiver prova; não limpar para destravar CLI.
7. Fechar recuperação R01–R12 e observabilidade/restore finais. Reusar artefatos
   íntegros; não exigir live externo onde matriz autoriza transporte simulado.
8. Corrigir Sonar sem baixar 80%; rodar full final. Em FAC-139, preparar candidato,
   revisar e publicar bytes aprovados; exigir scorecard accepted_by_ai.
9. Atualizar backlog/state/índice juntos. Histórico fica preservado em auditoria.

## Restrições práticas

Não reiniciar M0, reabrir componentes sem falha concreta, criar 90 novas tasks
para completion_tasks ou ativar opcionais no caminho crítico. Não repetir polling
Telegram para reconstruir inbound já persistido. Segredos não entram em logs.
Envio externo/publicação/push/PR/merge/deploy seguem autorizações próprias.

A CLI de atividade (`ai_acceptance.py`) e a CLI global têm finalidades distintas.
Receipt de atividade aceita seu critério/evidências; receipt global precisa do
snapshot final completo. Não inventar recibos, assinaturas ou aprovação humana.
