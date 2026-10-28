# Estado atual e plano de fechamento

Revisão documental: **2026-10-27**. Fonte dos estados e critérios por atividade:
[backlog](specs/implementation-backlog.json). Este arquivo é o handoff operacional;
o [roteiro detalhado](specs/10-FECHAMENTO-DAS-12-PENDENCIAS.md) descreve execução,
provas e critérios de saída. O [estado anterior](docs/auditoria/state-anterior-2026-10-27.md)
preserva o histórico.

## Situação atual

- O backlog contém **174 atividades: 163 `done`, 11 `in_progress`, nenhuma `todo`**.
- As 11 abertas são **FAC-121 e FAC-130–139**. Não reiniciar P00/M0 nem
  reimplementar componentes `done` sem evidência específica de regressão.
- `done` representa marco de componente, não necessariamente jornada integrada.
  **90 atividades `done`** apontam provas complementares em
  `audit.completion_tasks`; devem ser conciliadas no aceite global, sem virarem
  90 atividades novas.
- Aceite global segue **`pending_ai_acceptance`**. Não há demonstração de receipt
  global válido nem certificação de autonomia ponta a ponta.
- Nesta continuação, foi feito um único ciclo de intake Telegram. A mensagem exata
  foi persistida como demanda `bc16a11c-f654-4738-98f1-45daa2387faa`, raiz
  `464393985:11`, e seu ACK foi enviado em reply à mensagem original. Uma segunda
  mensagem importada no mesmo ciclo, com texto diferente, está registrada como
  `f5611522-b85e-4452-9e7f-19b708114c68`, raiz `464393985:10`; recebeu apenas
  ACK de registro e não foi selecionada para execução. Nenhuma das duas avançou
  além de `new`; ainda falta transição de negócio, decisão e retorno de resultado.
- FAC-135 tem receipt local `.runtime/artifacts/closure-20261027/cpf-journey/83f4b6084891-receipt.json`:
  baseline vermelho, run `5d2efb85-3058-46bc-9801-8250ac791af6`, resultado
  `28e8b16f2e0888b6f802a124c518d19d6ed0a1eb`, tests 9 passed, review assistido
  aprovado em 0,95. Discovery/plan e autoria estão marcados codex-assisted e
  operador sintético; portanto é evidência parcial, não aceite FAC-135.
- `quality-fast` passou no run `20261027T155755Z-2b814aaf` antes das atualizações
  documentais desta continuação; isso não substitui `quality-full`.

## Por que as tentativas anteriores não encerram o trabalho

1. **Falta o caminho operacional composto.** Existem módulos e provas isoladas,
   mas não foi localizado em `apps/`, `workers/` ou `scripts/` um consumidor
   versionado que ligue intake, decisão/plano aprovado, outbox/follow-up,
   execução, gates, review e retorno. Callbacks fornecidos por chamador e scripts
   em `.runtime` não provam um worker instalável e reiniciável.
2. **Alguns runs não provam autorização anterior ao efeito.** Receipts UI/GitHub
   recentes de FAC-130 registram `requirement_decision=proposed`. Conferir e
   proteger aprovação, plano/hash, escopo e despacho antes de claim/execução.
   Aprovação posterior não autoriza retroativamente. A transição para `done`
   também precisa verificar gates persistidos para o mesmo SHA/attempt.
3. **Jornada Telegram começou, mas não concluiu.** Uma mensagem real com a frase
   FAC-130 foi importada uma vez e o ACK foi respondido no root correto. A demanda
   permanece `new`: intake não executa transição de negócio nem cria plano. O
   segundo texto importado recebeu somente ACK e não deve ser confundido com o
   requisito aprovado. Ainda faltam decisão/plano, execução/review/retorno e replay
   controlado da mesma raiz para provar idempotência. O outbox da mensagem incidental
   também foi drenado com filtro explícito de sua própria demanda; ela segue sem
   transição ou execução.
4. **As provas cobrem critérios diferentes.** Testes do Registry, `quality-fast`
   ou scanner em fixture validam seus componentes; não provam intake aprovado,
   execução agêntica, revisão e retorno integrados.
5. **Qualidade final reprovou.** O full histórico
   `20261026T171041Z-c865e753` passou testes e outros gates, mas Sonar mediu
   cobertura nova de **61,5% frente ao mínimo de 80%**. O erro do wrapper não
   muda a causa: cobertura abaixo do limite. Corrigir os caminhos descobertos e
   repetir primeiro o gate afetado, depois o full final.
6. **O aceite global tem um ciclo de estado/hash.** O relatório requer FAC-139
   concluída, enquanto o aceite dessa atividade exige receipt global. Preparar
   e revisar um snapshot candidato com FAC-139 projetada como concluída; somente
   após aprovação publicar exatamente os mesmos bytes no backlog oficial.

## As 11 atividades abertas e o que falta

| Atividade | Lacuna concreta | Saída verificável |
|---|---|---|
| FAC-121 — retorno Telegram | Inbound real e ACK de registro já comprovados para `bc16a11c-f654-4738-98f1-45daa2387faa`; demanda ainda `new`, sem transição nem retorno de resultado. | Transição válida após decisão/plano, outbox de milestone ligada à raiz `464393985:11`, readback do envio e replay idempotente, mais aceite. |
| FAC-130 — atualização visual | Inbound exato Telegram registrado, mas sem decisão aprovada, AgentRun, patch visual ou review; UI/GitHub ainda requer auditoria de autorização prévia. | Três trilhas autorizadas ligadas a requisito/plano aprovado, AgentRun, gates, review, SHA e retorno; reusar este inbound somente após completar a jornada. |
| FAC-131 — discovery/plano tags | Usar baseline sem solução; conectar Analyst grounded ao contrato aprovado e Planner/binding reais. | Requisito reconciliado com contrato, DAG/paths/dependências/hash finais e aprovação anterior à execução. Reutilizar decisão EARS válida; não pedir cópia. |
| FAC-132 — DB/backend tags | Gerar por Factory as tasks TAG-DB/TAG-BE; controles manuais atuais não provam autoria integrada. | Tasks/run/SHA, migration e contratos, testes em PostgreSQL vazio e legado, rollback e review. |
| FAC-133 — frontend/integração tags | Produzir TAG-FE em worktree distinta e integrar com DB/BE. | UI funcional, isolamento entre worktrees, conflito/resolução controlados, browser/gates e review do SHA integrado. |
| FAC-134 — follow-up QA | Consumir proposta QA hoje inerte após a feature aceita. | Child task aceita que cria teste novo, executa/revisa o novo SHA e preserva demanda, decisões e tasks terminais originais. |
| FAC-135 — bug CPF | Fixture isolada anterior não comprova ciclo Factory; review antigo `uncertain` (0,75). | Teste vermelho prévio, intake/plano aprovado, fix sem patch fornecido, verde/regressão, review independente ≥0,8 no SHA final e proveniência completa. |
| FAC-136 — dependência | Scanner isolado 21→18→0 não prova remediação orquestrada. | Mesmo run: scanner→proposta→patch em fixture autorizada→scanner/regressão→review; candidato insuficiente vetado. |
| FAC-137 — recuperação | Completar matriz de falhas com processos reais e estado persistido. | R01–R12 com restart de processo, PostgreSQL/checkpointer, reconciliação de efeitos, leases/fencing e resultados separados de infra. Push/PR simulados com aprovações separadas. |
| FAC-138 — observabilidade/restore | Correlacionar uma jornada final e completar segurança, retenção e restore coerente. | Links intake→task/run/thread/checkpoint/model/tool/gate/review/SHA; métricas honestas, redaction/acesso/GC e restore/readback em alvos descartáveis. |
| FAC-139 — aceite global | Resolver qualidade final, cobertura das evidências e emissão global sem ciclo de hashes. | Matriz dos obrigatórios, full verde, snapshot candidato, receipt global verificável e publicação dos mesmos bytes; scorecard `accepted_by_ai`. |

FAC-142 **não está entre as pendências atuais**: o backlog registra status `done`,
avaliação sintética concluída, `human_agreement=null`, `promotion_eligible=false`
e revisão independente aprovada (confidence 0,95). A mensagem antiga em
`validation` que dizia “aguarda revisão” foi reconciliada com `audit.independent_review`;
reutilizar receipt e artefatos no aceite global, reabrindo somente se hash ou
verificação falhar. Isso não equivale a calibração humana.

## Ordem de execução da próxima fase

1. **C0, preparação compartilhada:** preservar checkout/worktrees; separar
   controlador e baseline Registry sem as soluções; fixar versões, suites,
   limites e hashes; preparar banco/serviços descartáveis. Implementar uma vez
   o worker/compositor versionado e validar autorização/plano/gates antes de
   efeitos. Mapear eventos reais e definir orçamento finito por run.
2. **Preparar entradas em paralelo ao trabalho local:** a demanda visual Telegram
   já foi obtida; preservar seu root e definir a aprovação/execução autenticada.
   Conferir o receipt e hashes de
   FAC-142 para reaproveitamento no pacote final; não repetir a avaliação se a
   prova vigente passar a verificação.
3. **FAC-121 → FAC-130:** inbound exato já existe e recebeu ACK. No próximo ciclo,
   autenticar operador pela UI, revisar a demanda `bc16a11c-f654-4738-98f1-45daa2387faa`,
   registrar/decidir requisito, aprovar plano e só então executar a trilha Telegram.
   Antes do próximo `getUpdates`, resolver ou descartar explicitamente a demanda
   `f5611522-b85e-4452-9e7f-19b708114c68`; não executar a frase alterada. Auditar
   UI/GitHub para aprovação prévia e repetir apenas a trilha que não provar autorização.
4. **FAC-131 → FAC-132 → FAC-133 → FAC-134:** contrato e plano finais; geração
   DB/BE; geração FE e integração; follow-up QA com teste novo. Não copiar a
   implementação pronta para o baseline experimental.
5. **FAC-135 e FAC-136:** executar duas jornadas independentes em fixtures
   autorizadas, reaproveitando o worker comum. Cada uma deve ter evidência
   antes/depois, SHA e review coerentes.
6. **FAC-137 → FAC-138:** executar matriz finita R01–R12; então usar jornada
   aceita para correlação, proteção, retenção e restore. Reusar readbacks
   históricos que ainda coincidam por hash e conteúdo.
7. **FAC-139 por último:** reconciliar os 174 marcos e 90 referências
   complementares; corrigir cobertura Sonar; obter full verde; montar candidato;
   revisar/assinar globalmente; verificar receipt e scorecard; publicar os mesmos
   bytes como backlog oficial. Não alterar o backlog após assinatura.

## Regras operacionais para não reiniciar o ciclo

- Antes de qualquer repetição, registrar o critério faltante, a evidência que o
  demonstrará, o SHA/run esperado e o limite de tentativas. Não rodar suite global
  para suprir inbound, autorização ou decisão ausente.
- Distinguir `fail`, `infra`, falta de autorização, entrada externa ausente e
  evidência inválida. Corrigir e repetir só a linha afetada e suas regressões.
- Marcar PASS apenas para a mesma versão/SHA efetivamente testada e revisada.
  `uncertain`, skip ou relatório exit 0 não significam aceite.
- Uma jornada pode servir a várias atividades, mas cada critério aponta à sua
  própria prova. Preservar logs e artefatos anteriores; não reclassificar falhas
  como sucesso nem apagar histórico.
- Telegram é at-least-once no transporte em janela sem ack; exigir idempotência
  dos efeitos de domínio sem prometer exactly-once de mensagem.
- A revisão documental não autoriza envio externo, publicação, push, merge ou
  deploy; seguir os gates de autorização específicos quando a próxima fase os
  alcançar.
- Manter opcionais fora do caminho crítico. Não ativar gateway, cloud, Jira ou
  novas features para fechar estas 11 atividades.

## Evidências locais a revalidar

Os artefatos `.runtime` são locais/ignorados e podem não existir em outro
checkout. Verificar existência, origem, SHA e readback antes de reutilizá-los:

- FAC-121: `.runtime/artifacts/fac-121/live-transition-delivery.json` e
  `inbound-help-reply.json` (históricos); estado corrente no banco local: demanda
  `bc16a11c-f654-4738-98f1-45daa2387faa` (`464393985:11`, status `new`, ACK publicado)
  e demanda incidental `f5611522-b85e-4452-9e7f-19b708114c68` (`464393985:10`, status
  `new`, ACK publicado). Não repetir polling para reconstruir estas entradas.
- FAC-130: `.runtime/artifacts/fac-130/current-implementation-update-20261026.json`
  e `agent-runs/fac130-{ui,github}-factory-receipt.json`.
- FAC-131: `.runtime/artifacts/fac-131-134/fac131-delegated-ears-decision.json`,
  `fac131-delegated-dag.json` e `fac131-baseline-inventory.json`.
- FAC-132/133: `.runtime/artifacts/fac-132/postgres-migrations.json` e
  `.runtime/artifacts/fac-133/postgres-e2e.json`.
- FAC-137/138/142: `.runtime/artifacts/fac-137/postgres-process-restart.json`,
  `.runtime/artifacts/fac-138/restore-summary.json` e
  `.runtime/artifacts/fac-142/comparison-20261026.json`.
- Qualidade: `.runtime/quality/runs/20261026T171041Z-c865e753/full.json` e
  `full/sonar-local.json`.
