# Aceite futuro — pedido visual com LLM local

Estado consolidado em 2026-10-27: **UI/GitHub têm provas parciais por SHA e Telegram sem demanda inbound; FAC-130 em andamento**. Os receipts registram `requirement_decision=proposed`: conferir autorização/plano anterior ao efeito e despacho operacional antes de considerar jornadas aceitas. Preservar as provas; repetir apenas trilha sem autorização comprovada. Ver [roteiro FAC-130](../../10-FECHAMENTO-DAS-12-PENDENCIAS.md). Atividade FAC-130; [plano operacional](../../08-PLANO-CONCLUSAO-E2E.md).

A decisão delegated-AI persistida define `--button-dark` localmente em `.submit-button`, sem tema global. Ambas as tasks começaram do baseline limpo `00d1a782ece691ad510fb4ef318590eea3540fff`: UI `724288e67e73d8f72c2067c323b5da595d1fcabc`; GitHub #3 `122a9b326ae574d031e3a4e87d57a2ae3fc67785`. Os receipts `fac130-ui-factory-receipt.json` e `fac130-github-factory-receipt.json` registram AgentRun, gates e revisão vinculados ao SHA. Qwen2.5-Coder gerou CSS; o harness Playwright foi escrito/reutilizado pela orquestração e essa autoria está explícita.

A origem Telegram ainda não trouxe a solicitação: novo long poll retornou `imported=0`, offset `960529131`; `/help` e eventos sintéticos não contam. FAC-121 permanece dependência aberta. Não há aceite IA global, merge, push nem mensagem enviada. Status permanece `in_progress`. Estado atualizado em `.runtime/artifacts/fac-130/current-implementation-update-20261026.json`.

Entrada literal a preservar: `alterar cor do botao para o tema dark`.

Uma sondagem histórica anterior às correções retornou `ask` sem proposta; ela não é diagnóstico atual recertificado. Corrigir a classificação é condição necessária, mas insuficiente: o aceite exige mudança visual produzida pelo agente, validada no navegador e entregue dentro do fluxo.

## Discovery proporcional

Identificar botão e tela. O alvo padrão candidato é “Adicionar cliente” do Registry, não arquivos protegidos da fábrica. Verificar como cores/tema são definidos no commit-base e se há dark mode. Esclarecer significado de tema dark e cor/contraste desejados quando isso não estiver definido. Se for necessário criar um sistema de temas, apresentar expansão de escopo antes de executar.

Gerar requisito pequeno com aceites de normal/hover/focus/disabled, contraste aprovado, desktop/mobile e preservação de light. Não criar tarefa de backend sem impacto real identificado.

## Execução e prova

| Etapa | Evidência |
|---|---|
| Entrada | Três rodadas independentes: frontend, Telegram autorizado e GitHub Issue no repo de teste. |
| Refinamento | Perguntas/respostas e requisito/plano final aprovados, com paths/budget autorizados. |
| Implementação | Inferência Ollama real, patch novo e commit em worktree, sem CSS/patch de solução previamente entregue ao agente. |
| Teste | Cor computada/tokens e estados do botão no tema correto; screenshots, interação por teclado e regressão funcional. |
| Qualidade | Checks do frontend alterado, segurança/escopo e reviewer no mesmo commit. |
| Entrega | Diff/evidências na UI e resultado no canal inicial; publicação opcional separada de entrega local. |

Começar cada rodada na mesma base sem a alteração. Testar replay, pedido ambíguo, falha de gate e solicitação referente à Factory UI protegida. Nenhum deles pode concluir o card com simulação ou alterar permissão por texto de LLM.

Sem campos/backend adicionais no caso puramente visual. Sem alegar autonomia se o operador precisou aplicar o patch, chamar os módulos de execução manualmente ou marcar tasks como concluídas.
