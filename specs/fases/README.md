# Fases e status auditados

Revisão documental em 2026-10-27. `[x]` componente concluído; `[~]` parcial/reaberto/aceite pendente; `[ ]` futuro não iniciado.

O [state.md](../../state.md) organiza as próximas ondas. O [backlog](../implementation-backlog.json) registra cada atividade; a [auditoria](../../docs/auditoria-projeto-2026-10-24.md) explica evidências e limitações.

Contagem atual do backlog: 174 atividades, 164 `done` e 10 `in_progress`; nenhuma `todo`. Todos os itens foram iniciados. O encerramento de componente não equivale a completar jornadas operacionais; ver `audit.completion_tasks` e `audit.deferred_scope` no backlog.

| Fase | Estado | Done / parcial / futura | Arquivo |
|---|---|---|---|
| P00 | [x] | 6 / 0 / 0 | [p00.md](p00.md) |
| P01 | [x] | 7 / 0 / 0 | [p01.md](p01.md) |
| P02 | [x] | 7 / 0 / 0 | [p02.md](p02.md) |
| P03 | [x] | 7 / 0 / 0 | [p03.md](p03.md) |
| P04 | [x] | 7 / 0 / 0 | [p04.md](p04.md) |
| P05 | [x] | 6 / 0 / 0 | [p05.md](p05.md) |
| P06 | [x] | 6 / 0 / 0 | [p06.md](p06.md) |
| P07 | [x] | 7 / 0 / 0 | [p07.md](p07.md) |
| P08 | [x] | 7 / 0 / 0 | [p08.md](p08.md) |
| P09 | [x] | 7 / 0 / 0 | [p09.md](p09.md) |
| P10 | [x] | 7 / 0 / 0 | [p10.md](p10.md) |
| P11 | [x] | 6 / 0 / 0 | [p11.md](p11.md) |
| P12 | [x] | 6 / 0 / 0 | [p12.md](p12.md) |
| P13 | [x] | 7 / 0 / 0 | [p13.md](p13.md) |
| P14 | [x] | 6 / 0 / 0 | [p14.md](p14.md) |
| P15 | [x] | 10 / 0 / 0 | [p15.md](p15.md) |
| P16 | [x] | 11 / 0 / 0 | [p16.md](p16.md) |
| P17 | [~] | 8 / 1 / 0 | [p17.md](p17.md) |
| P18 | [~] | 0 / 10 / 0 | [p18.md](p18.md) |
| P19 | [x] | 1 / 0 / 0 | [p19.md](p19.md) |
| P20 | [~] | 12 / 1 / 0 | [p20.md](p20.md) |

L0–L4: **21 atividades de melhoria com marco de componente concluído**, incluindo `LLMG-T21` no [documento de melhoria](../melhoria/08-LITELLM-GATEWAY-BENCHMARK-CODING-JUDGE.md). LiteLLM/benchmark seguem opcionais e não bloqueiam a fábrica usando Ollama direto.

Os documentos originais 01–07 continuam definindo o escopo. O [plano de fechamento](../08-PLANO-CONCLUSAO-E2E.md) acrescenta integração operacional e aceites reais; diferenças de escopo estão explicitadas ali.

P20 é transversal: [FAC-140–152](p20.md) e [especificação de evals/rubricas](../09-EVALS-RUBRICAS-E-HARNESS.md). Catálogo, controles e simuladores locais foram validados; rubricas/casos continuam drafts e não certificam calibração ou capacidade live.

FAC-153 (P16) e LLMG-T21 estão `done` no backlog; não reabrir automaticamente por observações históricas. FAC-153 tem quatro achados médios Bandit documentados com controles compensatórios; o Sonar global continua sendo pendência de qualidade final, não reabertura automática desse escopo.

As 10 abertas são **FAC-121, FAC-130–134 e FAC-136–139**. O [roteiro atual](../10-FECHAMENTO-DAS-12-PENDENCIAS.md) detalha cada uma, C0 operacional e regras de reaproveitamento. FAC-142 está `done`, integra os obrigatórios do relatório e sua evidência/revisão deve ser revalidada no aceite global de FAC-139. Há 90 componentes `done` com referências históricas `completion_tasks`: conciliar cobertura no pacote final sem criar 90 novas atividades.

Os relatos de 2026-10-24/25/26 preservados nos arquivos de fase são históricos; afirmações antigas de pendência/validação não prevalecem sobre esta revisão e o backlog atual. `done` de componente não certifica experimento, piloto live ou operação autônoma.
