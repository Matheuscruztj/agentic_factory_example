# Fases e status

Use esta pasta para acompanhar cada fase de `03-TASKS-POR-FASES.md` sem alterar a especificação original.

- `[]` — não começou.
- `[~]` — em andamento (inclui atividades implementadas que ainda aguardam gate de ambiente/aceite).
- `[x]` — concluída conforme o aceite disponível.

O [`state.md`](../../state.md) na raiz é o controle operacional: registra o que ainda falta, dependências, próxima wave e bloqueios. Ao concluir uma atividade, atualize o status aqui e remova-a da lista de pendências em `state.md`. Detalhes de escopo, dependências e critérios permanecem em [`../03-TASKS-POR-FASES.md`](../03-TASKS-POR-FASES.md).

## Fases

| Fase | Estado | Arquivo |
|---|---|---|
| P00 — Inventário, decisões, segurança e preflight | [~] | [p00.md](p00.md) |
| P01 — Bootstrap da stack local e serviços | [~] | [p01.md](p01.md) |
| P02 — Customer Registry | [x] | [p02.md](p02.md) |
| P03 — Persistência operacional e Task Engine | [x] | [p03.md](p03.md) |
| P04 — Factory API e UI operacional inicial | [x] | [p04.md](p04.md) |
| P05 — Entrada de demandas e integração externa controlada | [] | [p05.md](p05.md) |
| P06 — Context Engine, personas, skills e orçamento | [] | [p06.md](p06.md) |
| P07 — OpenBot | [] | [p07.md](p07.md) |
| P08 — LangGraph | [] | [p08.md](p08.md) |
| P09 — Git worktree, sandbox e execução de código | [] | [p09.md](p09.md) |
| P10 — Quality gates locais e segurança | [] | [p10.md](p10.md) |
| P11 — Agent Evals e evolução de prompts | [] | [p11.md](p11.md) |
| P12 — Observabilidade e recursos | [] | [p12.md](p12.md) |
| P13 — Demonstrações e testes adversariais | [] | [p13.md](p13.md) |
| P14 — Integrações opcionais e hardening | [] | [p14.md](p14.md) |
