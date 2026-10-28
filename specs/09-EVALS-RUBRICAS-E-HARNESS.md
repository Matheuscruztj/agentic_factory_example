# Evals e rubricas: especificação complementar

> Decisão vigente do operador em 2026-10-27: FAC-142 usa casos sintéticos com resultado determinístico e revisão independente por IA. Exigências anteriores de labels humanos dessa atividade foram substituídas; não se alega calibração humana. O histórico permanece identificado.
Documento original: 2026-10-24. **Escopo complementar; status revisto em 2026-10-27:** P20 tem 12 componentes done e FAC-142 aberta. Critérios de calibração/ensaios continuam exigindo provas próprias; ver [roteiro das 12 pendências](10-FECHAMENTO-DAS-12-PENDENCIAS.md). Fontes e limites na [pesquisa aplicada](../docs/pesquisa-fabricas-agenticas-evals-rubricas-2026-10-24.md). Complementa o [plano E2E](08-PLANO-CONCLUSAO-E2E.md), sem substituir Task Engine, Ollama, policies, qualidade determinística ou HITL.

## 1. Unidade de avaliação

Cada caso deve declarar o pedido, baseline de código/dados, decisões de produto, capacidades disponíveis, orçamento, comportamento esperado e resultados proibidos. Uma **tentativa externa** começa em ambiente limpo; ela pode conter várias chamadas de modelo, correções internas e pausas. Retry interno não é uma tentativa independente de benchmark.

Registrar separadamente:

| Dimensão | Exemplo | Como verificar |
|---|---|---|
| Resultado funcional | Lote importado uma vez; filtro mostra os registros corretos | Banco/API/browser no ambiente do run. |
| Processo permitido | Escopo/HITL, origem da evidência, limites e ausência de efeito proibido | Eventos/artefatos/ferramentas visíveis e políticas do servidor. |
| Qualidade da interação | Pergunta necessária, plano proporcional, relato fiel | Rubrica e roteiro controlado do usuário. |
| Eficiência | Tempo, tokens, ferramentas, espera, reload e retrabalho | Instrumentação e orçamento comparáveis. |
| Validade da avaliação | Fixture solucionável, grader alinhado, ambiente íntegro | Controles positivos/negativos e auditoria do caso. |

Não avaliar raciocínio interno oculto. São suficientes ações observáveis, decisões registradas, chamadas/resultados de ferramentas e uma justificativa curta com evidência. Não exigir uma trajetória exata: dois planos ou algoritmos diferentes podem satisfazer o mesmo contrato. Exigir sequência específica somente quando fizer parte da permissão/segurança ou do comportamento pedido.

## 2. Resultados e denominadores

Separar `task_outcome` de `evaluation_status`. Proposta:

- `task_outcome`: `satisfied`, `not_satisfied`, `waiting_required_decision`, `cancelled_as_requested`, `no_change_needed`, `not_observed`.
- `evaluation_status`: `valid`, `infra_error`, `grader_error`, `invalid_case`, `incomplete_evidence`.
- `policy_result`: `allowed`, `violation`, `not_observed`.

`waiting_required_decision` pode ser o resultado correto de um ensaio de discovery; não significa que a feature foi entregue. `cancelled_as_requested` e `no_change_needed` só são sucesso em casos cujo contrato assim define, com pós-condições comprovadas. Uma pausa eterna não satisfaz um caso de implementação.

Publicar ao menos:

1. Total agendado, iniciado, completo, válido, infraestrutura, grader inválido e caso inválido.
2. Taxa operacional sobre todas as tentativas iniciadas e taxa funcional condicional às avaliações válidas, lado a lado.
3. Violações de policy e falsa alegação de conclusão, sem removê-las do relatório por falta de elegibilidade de qualidade.
4. Custo/tempo de todas as tentativas, inclusive as que falharam; média por task aceita usa numerador completo e denominador explícito.

Classificações de falha devem ser revisáveis. Não excluir OOM automaticamente: se limites estavam íntegros e o agente escolheu uma estratégia que excedeu seu orçamento, isso pode ser falha de capacidade sob aquele perfil. Se o laboratório não entregou a reserva contratada, é falha de ambiente. Reportar ambas as situações e justificar.

## 3. Métricas de repetição

Para um caso com `n` tentativas externas comparáveis e `c` sucessos, estimadores candidatos para `1 ≤ k ≤ n`:

- `pass@k = 1 - C(n-c,k)/C(n,k)`: chance estimada de pelo menos um sucesso em k tentativas.
- `pass^k = C(c,k)/C(n,k)`: chance estimada de k sucessos no mesmo conjunto amostrado.
- `pass@1 = c/n`. Não confundir isso com aprovação na primeira correção **dentro** de uma tentativa.

Definir `C(a,k)=0` quando `a<k`; se `n<k`, retornar `insufficient_evidence`. Essas fórmulas exigem desenho amostral apropriado; cache, histórico compartilhado, versão de usuário simulador, mudanças de máquina e warm-up podem invalidar a comparação. Não estimar confiabilidade de produção com três rodadas dependentes.

Relatar por caso/família e macro média entre casos, além dos números agregados. Intervalos devem respeitar a unidade de amostragem; comparações de candidatos usam pares por caso, com análise de variabilidade entre tarefas. Com poucos casos, dar contagens e aviso de insuficiência, sem p-values decorativos ou promoção automática.

Se `n` excluir tentativas inválidas ou de infraestrutura, rotular o estimador como
condicional às avaliações válidas e apresentar também confiabilidade operacional
completa. Não apresentar seleção filtrada como confiabilidade de produção.

## 4. Contrato de rubrica proposto

Rubrica é um conjunto versionado de critérios observáveis. Cada critério contém:

| Campo | Regra proposta |
|---|---|
| `id`, `version`, `role` | Identidade estável e versão independente de modelo. |
| `criterion`, `applies_when` | Uma dimensão avaliável e sua condição de aplicação. Evitar misturar várias qualidades não relacionadas na mesma nota. |
| `grader_kind` | Determinístico, humano/modelo ou híbrido; explicitar qual evidência tem precedência. |
| `anchors` | Descrição concreta de cada nível da escala. |
| `required_evidence` | Tipos/IDs de evidência aceitáveis e relação com o run/requisito. |
| `critical_failures` | Condições de veto verificáveis, sem compensação por média. |
| `unknown_policy` | Sem evidência → `unassessable`, nota `null`; não preencher com zero, médio ou PASS. |
| `not_applicable_policy` | Requer regra de aplicabilidade aprovada e motivo; o próprio agente avaliado não descarta critério. |
| `calibration_refs` | Exemplos revisados e divergências adjudicadas; drafts não são goldset. |

A escala **0–3** dos drafts é uma proposta de design: 0 viola/contradiz; 1 parcial com lacuna relevante; 2 satisfaz o contrato; 3 satisfaz e trata um aspecto adicional pertinente sem expandir escopo. Cada critério especifica suas próprias âncoras. Não mapear automaticamente para a nota global 1–5 de `JudgeVerdict` atual.

Um critério objetivo é decidido pelo verificador pertinente. A LLM pode explicar o resultado, sem transformar reprovação em aprovação. A nota 3 não premia mais arquivos, perguntas, agentes, texto ou features. Uma mudança simples pode ter nota alta com execução pequena e justificada.

Não haverá nota única obrigatória que esconda veto. Perfis de entrega podem exigir todos os critérios essenciais com evidência e nível mínimo definido **depois da calibração humana**. Não adotar “média ≥ 2,5” ou pesos estéticos genéricos como condição universal. Para frontend, coerência com o design aprovado e uso funcional têm precedência sobre originalidade gratuita.

## 5. Calibração e metaeval

### Antes de confiar nas rubricas

Dois avaliadores humanos, quando disponíveis para a revisão independente, pontuam exemplos sem ver notas do outro ou identidade do executor. Comparar por critério: acordo exato, acordo dentro de um nível, distribuição das notas e matriz de confusão. Kappa ponderado só quando amostra/distribuição sustentarem interpretação; não substitui inspeção das divergências.

Adjudicar casos ambíguos, corrigir critério/fixture e reservar exemplos não usados no ajuste. Não forçar consenso por média. Se existir apenas um anotador, registrar single-rater e não declarar concordância independente. Dimensões com desacordo persistente ficam descritivas ou pedem humano, sem falsa precisão.

### Antes de confiar no Judge

Usar pacote independente com respostas corretas, parcialmente corretas, falsas, incompletas e perigosas. Testar troca A/B, anonimização, texto prolixo versus curto com o mesmo conteúdo, estilos diferentes, autoria alegada, citação inventada e instrução maliciosa dentro do artefato avaliado. Mudança legítima de conteúdo pode mudar a nota; transformação puramente cosmética não deveria mudar a decisão factual.

Modelo separado é requisito de isolamento do papel, não prova de independência estatística. `confidence=0.9` não é uma probabilidade de acerto validada. Comparar aceitação indevida de defeitos críticos, reprovação indevida de soluções válidas, abstention/coverage, schema válido, acordo humano e latência. Escalar quando evidência ou calibração forem insuficientes.

**Vocabulário explícito de erros:** nas métricas novas de detecção, positivo = defeito presente. Reportar recall de defeitos, falso negativo crítico e falsa reprovação de solução correta. Preservar nomes/convenção do relatório legado ou migrá-los com versão; não renomear seu recall de `pass` para defect recall silenciosamente.

### Antes de confiar no grader determinístico

Uma solução de referência deve passar, e defeitos semeados devem falhar. Quando houver liberdade de implementação, pelo menos duas alternativas funcionalmente corretas devem passar sem exigir nome/path/helper não contratado. Verificar que testes não cobram comportamento não especificado nem deixam passar retorno fixo, remoção de assertions ou escrita direta em fixtures.

Um caso impossível/contraditório vai para quarentena como `invalid_case`. Essa regra não permite ao agente editar o grader para fazer sua solução passar. Alteração do oráculo é tarefa de curadoria independente, com revisão e reexecução de controles.

## 6. Handoff e ablation da fábrica

**Handoff:** avaliar reset de contexto, compaction e sessão nova com o mesmo estado autoritativo. Pacote deve preservar objetivo, revisão/plano aprovados, SHA real, tasks/artefatos/decisões e próximo passo permitido. Comparar com PostgreSQL antes de confiar no resumo. Medir obrigações perdidas, trabalho repetido, custo de reorientação e retomada correta. Não exigir copiar conversa inteira nem aceitar instrução de resumo que amplie permissão.

**Ablation:** comparar executor simples, executor com planner e conjunto com reviewer/QA especializado, conforme capacidades disponíveis. Manter políticas, testes e gates em todos os braços. Igualar orçamento total de inferência/ferramentas e registrar tokens de coordenação, fila, reload, retrabalho e qualidade final. Papel lógico não exige modelo simultâneo na GPU. Escolher a menor arquitetura que sustente qualidade medida; o resultado pode justificar reduzir passos para tarefas simples.

Essas comparações são pesquisa local planejada. Não representam autorização para criar agentes paralelos nesta sessão, alterar a arquitetura ativa ou desabilitar revisão humana/policies.

## 7. Novas demandas de capability

| Família | Pedido candidato | Novo comportamento exercitado |
|---|---|---|
| Importação de clientes | “Quero importar um CSV, revisar a prévia e confirmar só quando estiver correto.” | Upload/parsing, validação por linha, decisão do lote, atomicidade/idempotência e UI de erros. |
| Exportação segura | “Exporte os clientes que aparecem neste filtro para um CSV.” | Consistência UI/API/arquivo, escaping e política de células interpretáveis como fórmula. |
| Paginação compatível | “A lista está grande; pagine a consulta sem quebrar os clientes atuais da API.” | Contrato legado, ordenação/filtros, estado da UI e estratégia compatível escolhida no refinamento. |

Nenhum detalhe adicional vira requisito oculto: tamanho/encoding/separador do arquivo, regra de duplicata, atomicidade, segurança de exportação e forma de compatibilidade precisam constar do contrato aprovado ou ser decididos no discovery. Os casos de CSV e paginação no catálogo são candidatos, sem patches, banco/rotas novos ou execução nesta etapa.

## 8. Suites e simuladores

Manter suites separadas: `grader_meta`, `judge_calibration`, `interaction`, `capability`, `regression`, `harness_reliability` e `tool_usability`. O catálogo em `evals/design` é público/de desenvolvimento; **não é holdout secreto**. O holdout real deve ser criado depois, em storage fora das permissões do executor, com manifest/hashes e separação por família/origem para reduzir vazamento por paráfrase.

Dados de incidente entram como candidatos sanitizados, revisados quanto a escopo, rótulos e reprodutibilidade. Promoção de capability para regression precisa de decisão e histórico; aumentar score não autoriza trocar o teste de lugar para esconder falha.

Simuladores GitHub/Telegram devem implementar só o subconjunto de comportamento usado pelo projeto: paginação, updates/edits, threads/replies, 429, timeouts e confirmação/duplicata de efeitos. Estado e relógio controlados permitem cenários longos sem postar em serviços reais. Contratos precisam ser comparados com amostras live autorizadas quando disponíveis. Sucesso no simulador não é certificação live.

## 9. Entrega incremental e escopo

[P20 / FAC-140–152](fases/p20.md) materializa os aceites. Relações com FAC-105/109/110/117/119/129 e LLMG são complementares; não duplicam sua implementação. Primeira entrega: rubricas, controles do grader e ciclo das suites. Depois agentes reais, simuladores e famílias de capability; por fim comparações de repetição, recursos e arquitetura.

FAC-129 passa a depender de FAC-140/141/143/148 para seus contratos de avaliação.
FAC-142 é dependência condicional antes de usar notas do Judge em comparação ou
promoção. O Judge pode permanecer desligado com resultado indisponível explícito;
isso não elimina gates determinísticos nem revisão humana. A ordem segue a DAG,
não a posição numérica da fase.

Os requisitos dos drafts são `EVAL2-001–013`, de rastreabilidade local a esta extensão. Não substituem os 43 requisitos do escopo original nem transformam import/export/paginação em funcionalidades obrigatórias do MVP sem seleção explícita. As regras de confiança do Judge são necessárias se suas notas forem usadas em comparação/promoção; se ele estiver desligado, os gates determinísticos e o aceite técnico independente por IA continuam válidos conforme `docs/ai-acceptance-policy.md`.

## 10. Rastreabilidade da extensão

| Requisito | Obrigação planejada | Atividade |
|---|---|---|
| EVAL2-001 | Rubricas observáveis por papel, aplicabilidade e calibração humana. | FAC-140 |
| EVAL2-002 | Graders aceitam alternativas corretas e detectam defeitos semeados. | FAC-141 |
| EVAL2-003 | Judge calibrado resiste a vieses/ataques e explicita abstenções/erros. | FAC-142 |
| EVAL2-004 | Repetição, pass@k/pass^k e denominadores respeitam unidade amostral. | FAC-143 |
| EVAL2-005 | Comparações controlam recursos e distinguem suas causas de falha. | FAC-144 |
| EVAL2-006 | Contexto novo/compaction preservam obrigações, evidências e permissões. | FAC-145 |
| EVAL2-007 | Arquitetura é comparada sob orçamento e controles equivalentes. | FAC-146 |
| EVAL2-008 | Ferramentas são avaliadas pelo uso real e utilidade para a LLM. | FAC-147 |
| EVAL2-009 | Suites/casos têm curadoria, separação por origem e promoção auditada. | FAC-148 |
| EVAL2-010 | Avaliar agir/perguntar/responder/não alterar/cancelar conforme contrato. | FAC-149 |
| EVAL2-011 | Capability inclui famílias inéditas fullstack com oráculos justos. | FAC-150 |
| EVAL2-012 | Variantes equivalentes preservam obrigações e permissões por canal. | FAC-151 |
| EVAL2-013 | Simuladores locais stateful têm contratos e limites de fidelidade. | FAC-152 |
