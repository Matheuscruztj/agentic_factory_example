# Evals v2 — drafts de desenho e calibração

**Estado: planejamento, não ativado e não executado.** Esta pasta não é lida pelo runner atual nem foi adicionada ao `evals/dataset-manifest.json`. Não contém gabarito humano aprovado, resultados de benchmark ou holdout secreto.

- [Pesquisa e fontes primárias](../../docs/pesquisa-fabricas-agenticas-evals-rubricas-2026-10-24.md).
- [Contrato detalhado de evals](../../specs/09-EVALS-RUBRICAS-E-HARNESS.md).
- [Atividades FAC-140–152](../../specs/fases/p20.md).
- [Rubricas propostas](rubrics-v2-draft.json): oito papéis e 24 critérios, cada um com quatro âncoras observáveis.
- [Cenários candidatos](scenarios-v2-draft.json): 32 casos com pré-condições, decisões de produto, oráculos e controles negativos.
- [Manifest de design](manifest-draft.json): hashes dos dois JSONs e URLs pesquisadas; não é manifest de runtime.

## Rubricas

| Papel | Critérios propostos |
|---|---|
| Analyst | Fatos/hipóteses, pergunta material, refinamento proporcional. |
| Planner | Dependências/contratos, proporcionalidade, prontidão para execução. |
| Backend | Contrato compatível, dados/transação, mudança coesa. |
| Frontend | Jornada funcional, coerência visual/acessibilidade, estado do cliente. |
| QA | Cobertura de risco, qualidade das assertions, relato fiel. |
| Reviewer | Achados verificáveis, independência, bloqueio proporcional. |
| Orchestrator | Handoff, coordenação, correspondência entre estado e conclusão. |
| Judge | Evidência válida, resistência a vieses, incerteza/autoridade. |

Escala candidata: **0** contradiz/viola; **1** parcial; **2** atende ao contrato;
**3** atende e verifica aspecto adicional pertinente, preservando o escopo.
As descrições específicas de cada nível estão no JSON. Mais texto, código,
features, perguntas ou agentes não significam nota melhor.

`unassessable` usa nota `null`; ausência de evidência não vira aprovação nem
falha funcional inventada. `not_applicable` precisa de regra/motivo aprovados.
Uma LLM não reclassifica um gate determinístico nem concede permissão. Não há
média global que compense vazamento, publicação indevida ou requisito crítico quebrado.

A escala 0–3 não é conversão automática da escala 1–5 ativa. Para ativá-la,
implementar migração explícita do schema e manter interpretação histórica.
Manifests de agentes, prompts e rubrica `judge-v1.json` permanecem inalterados.

## Famílias dos cenários

| Casos | Objetivo |
|---|---|
| EV2-001–007 | No-op correto, consulta, esclarecimento necessário/redundante, conflito, escopo protegido e cancelamento. |
| EV2-008 | Limite de budget e relato honesto. |
| EV2-009–011 | Referências alternativas, defeitos semeados e caso inválido: testar o avaliador. |
| EV2-012–017 | Ordem, verbosidade, autoria alegada, referências, injeção e abstenção do Judge. |
| EV2-018 | Semântica das métricas de detecção. |
| EV2-019–021 | Sessão nova, resumo obsoleto e preservação de evidência após compaction. |
| EV2-022 | Comparação controlada de arquiteturas. |
| EV2-023–024 | Simulação de múltiplas etapas GitHub/Telegram. |
| EV2-025–029 | CSV import/export e paginação compatível: demandas inéditas de capability. |
| EV2-030 | Invariância entre paráfrases, acentos e canais. |
| EV2-031 | Recuperação a partir de erro de ferramenta e eficiência do contexto. |
| EV2-032 | Recursos, repetição e insuficiência amostral. |

Casos baseados em comportamento já previsto indicam `extends_existing`: a
novidade pode estar na forma de medir ou no controle negativo, não em adicionar
outra implementação da mesma função. Casos que exigem feature nova possuem
`requires_new_product_feature=true`; são diagnósticos opcionais de capacidade.

## Tornar um caso executável

1. Escolher família e perfil do ensaio, revisar semântica do pedido e aprovar
   decisões de produto/segurança necessárias. Definir contexto/tempo/tokens e
   comportamento do usuário antes de executar.
2. Criar baseline limpo sem solução, dados sintéticos, ambiente, solução de
   referência e oráculo protegido. Controle correto passa; defeito semeado falha.
3. Revisar com humano independente onde a anotação assim exige; registrar
   divergências. `human_label:null` não pode ser transformado em gold por confiança do Judge.
4. Separar dev/calibração/holdout por família e origem. Estes casos publicados
   são drafts de desenvolvimento; holdout precisa de novos casos fora das
   permissões/contexto do executor e sem exposição nos exemplos de prompt.
5. Executar primeiro lote pequeno de sanity checks; depois rodadas reais em
   baselines independentes. Persistir run/attempt/SHA/config e erros do laboratório.
6. Só promover rubrica ou caso mediante evidência/decisão pertinente. Capability
   difícil não reprova automaticamente uma entrega antiga fora desse escopo;
   regression selecionada precisa preservar seu contrato.

Não produzir estatísticas de concordância com humanos a partir apenas das
âncoras escritas aqui. Sem avaliadores independentes, registrar a limitação.

## Métricas e desenho experimental

Reportar por caso/família, além do agregado: sucesso funcional, violações,
aceitação indevida de defeito crítico, abstenção/coverage, retrabalho, tarefas
aceitas por hora, tokens/tempo de coordenação e erro de ferramenta. Recursos,
cache, modelo/digest, sampling, orçamento e roteamento devem ser comparáveis.

Para repetição, distinguir `pass@k` (pelo menos um sucesso) e `pass^k` (todos os
k sucessos), com unidade amostral e fórmulas da especificação. Se somente
tentativas válidas entram em `n`, identificar o resultado como condicional e
mostrar também a taxa operacional completa. Retry interno não incrementa `n`
como se fosse experimento independente.

A classe positiva das métricas novas de defeito é **defeito presente**. O
relatório legado usa `pass` como positivo; migrar com versão e matriz explícita.
Confiança numérica emitida pelo Judge é autorrelato, até validação empírica.

Na GPU local de 8 GB, executar sequencialmente e com orçamento. Começar com
ensaios curtos; aumentar casos/repetições quando a decisão exigir. Não copiar
escala, modelos ou gasto dos estudos externos. Esta pasta não requer cloud,
LiteLLM, um modelo novo ou um serviço de avaliação pago.
