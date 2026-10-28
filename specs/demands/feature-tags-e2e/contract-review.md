# FAC-131 — contrato reconciliado de etiquetas

Revisado em **2026-10-27**. A revisão canônica é a v2 persistida na Factory:
demand `5719882c-1e1d-49b9-a0d4-1f965762489e`, revision
`994f041d-736b-4d8c-a08d-0de8ea2391e2`. Ela contém 10 critérios EARS e 20
cenários (um positivo e um negativo por critério). Os 8 itens `TAG-R01..TAG-R08`
do draft anterior foram substituídos pela lista canônica abaixo; nenhum registro
aprovado foi editado in-place.

## Discovery grounded no baseline

Baseline Git: `00d1a782ece691ad510fb4ef318590eea3540fff`. Inventário read-only e
discovery assistido por Codex registrados em
`.runtime/artifacts/next-five/fac131-grounded-discovery.json`; o artefato não
alega autoria do Analyst Factory.

| Local no baseline | Fato verificado | Impacto para etiquetas |
|---|---|---|
| `apps/customer-registry/api/src/customer_registry/models/user.py:10` | `User` é a entidade persistida; não há `Tag`, associação ou relação de etiquetas. | Migration deve criar catálogo/associação sem exigir tags para clientes legados. |
| `apps/customer-registry/api/src/customer_registry/repositories/users.py:19-41` | Repositório lista/busca usuários e cria registros; não filtra nem persiste tags. | Incluir filtro no repositório e manter busca/status existentes. |
| `apps/customer-registry/api/src/customer_registry/main.py:28-56,104-146` | Schemas e rotas cobrem CRUD de usuários; não há `/api/v1/tags` nem `tag_ids`. | Criar schemas/rotas e validar atomicidade no servidor. |
| `apps/customer-registry/api/alembic/versions/0001_create_users.py:13-28` | Migration inicial cria somente usuários e índices/constraints originais. | Migration nova precisa preservar usuários/telefone e suportar rollback seguro. |
| `apps/customer-registry/web/src/App.tsx:16-39,112-120` | UI mantém busca e estados de lista, sem catálogo/filtro/associação. | Integrar estados recuperáveis sem quebrar a busca e o vazio existentes. |
| `apps/customer-registry/web/src/api.ts:29-34` | Cliente HTTP oferece list/create/update de usuário; não há chamadas de tags. | Adicionar endpoints e provar reload/filtro pelo caminho real. |
| `apps/customer-registry/api/tests/test_users.py:117-181` | Testes existentes cobrem ciclo de usuário/telefone, não associação de tags no baseline. | Preservar regressões e adicionar casos positivos/negativos específicos. |

Descoberta: o contrato mínimo precisa de catálogo compartilhado, vínculo muitos-para-muitos,
filtro por uma tag combinado por AND com a busca, compatibilidade com usuários sem
associações, política explícita de normalização/limites e atualização transacional.

## Decisões de produto registradas

O operador aprovou os defaults em `.runtime/artifacts/fac-131-134/fac131-product-decisions.json`;
hash da decisão `b199768efac42341f9a3b0b1af0c680d660eb937eabc5f55206e563c3b23eb63`.
O artefato cobre estas escolhas:

- Catálogo compartilhado; vários tags por cliente; desvincular não apaga catálogo.
- Nome trim + casefold para unicidade; acentos permanecem significativos.
- Nome de 1 a 32 caracteres; até 10 tags por cliente; filtro por uma tag.
- Busca textual e tag combinam por AND; associação omitida preserva; `[]` limpa.
- Renomear/excluir tag fora deste escopo; permissões seguem operador local único.

A decisão da revisão EARS v2 está registrada como delegada ao Codex, não como
assinatura humana, no artefato `fac131-delegated-ears-decision.json`. Ela preserva
os defaults humanos acima e explicita validação/atomicidade.

## EARS canônico — 10 critérios

| ID | Condição e resposta esperada |
|---|---|
| TAG-R01 | Quando uma tag válida for criada, persistir no catálogo compartilhado e retornar o mesmo ID/nome após reload. |
| TAG-R02 | Se o nome após trim/casefold duplicar outra tag ou estiver fora de 1–32 caracteres, rejeitar a criação sem registro parcial; acentos são significativos. |
| TAG-R03 | Ao criar/editar cliente com IDs válidos, persistir exatamente as associações selecionadas. |
| TAG-R04 | Se `tag_ids` for omitido no PATCH, preservar todas as associações existentes. |
| TAG-R05 | Se a lista vazia for enviada, limpar as associações e preservar itens do catálogo. |
| TAG-R06 | Com filtro por uma tag e busca textual ativos, retornar a interseção dos resultados. |
| TAG-R07 | Cliente legado sem tags permanece legível/editável e não recebe tag automaticamente. |
| TAG-R08 | ID de tag desconhecido ou repetido rejeita toda a atualização e preserva campos e associações anteriores. |
| TAG-R09 | Mais de 10 tags rejeita toda a alteração; independentemente, nome fora de 1–32 após trim é rejeitado; casofold serve à unicidade e acentos continuam distintos. |
| TAG-R10 | Remover vínculo de um cliente preserva o catálogo e vínculos dos demais clientes. |

Critério de fronteira resultante: 9 e 10 associações são aceitas; 11 é rejeitada.
Para nomes, 1 e 32 são válidos; vazio/só espaços e 33 são rejeitados. Isso resolve
TAG-R08 do draft, que incorretamente rejeitava exatamente 10.

## Cenários pareados — 20 cenários persistidos

O gerador da Factory registra `acceptance-1..10-positive` e
`acceptance-1..10-negative`. A tabela concretiza a finalidade de cada par:

| Par | Positivo | Negativo/controle |
|---|---|---|
| 1 | Criar tag válida e conferir mesmo ID/nome após reload. | Omitir persistência/reload; não declarar R01 cumprido. |
| 2 | Criar nome único válido, incluindo nome de 1 e 32 chars. | Duplicata após trim/casefold ou nome 0/33 chars; nenhuma criação parcial. |
| 3 | Criar/editar cliente com seleção válida e conferir vínculos exatos. | Seleção diverge do payload; não declarar associação correta. |
| 4 | PATCH sem `tag_ids` preserva os vínculos anteriores. | PATCH remove vínculo sem campo; falha R04. |
| 5 | PATCH `tag_ids: []` limpa vínculos e mantém tags no catálogo. | Limpar cliente também apaga catálogo; falha R05. |
| 6 | Tag e termo de busca retornam somente interseção. | Resultado retorna cliente que só satisfaz um dos filtros. |
| 7 | Ler/editar cliente legado sem tags, sem associação automática. | Criar associação implícita para cliente legado. |
| 8 | IDs desconhecidos/repetidos retornam erro e transação preserva estado. | Atualização parcial de campos/vínculos após erro. |
| 9 | Aceitar 9 e 10 vínculos; nome com 1/32 chars válido. | Rejeitar 11 vínculos ou nome 0/33 sem alterar vínculos antigos. |
| 10 | Desvincular um cliente; preservar catálogo e demais clientes. | Apagar tag compartilhada ou associação de outro cliente. |

Estados de loading/erro recuperável, vazio e acessibilidade da UI são critérios
complementares de TAG-FE/TAG-QA/FAC-133, não cláusulas extras disfarçadas nesta
revisão EARS. O E2E PostgreSQL atual comprova fluxo mobile, reload, foco e vazio;
erro de duplicata é coberto pelo spec recém ampliado.

## Plano, histórico e teste de rejeição

O plano final foi aprovado com hash `ee17d86fc2c69b19add16cbdc174a5e88bdb87ce400f8cbc3f127f3af3a2c701`,
approval `5558756d-dc6b-4a16-8710-b4ba104b5fec`. Snapshot e sete IDs preservados em
`.runtime/artifacts/next-five/tags-final-plan-and-runs.json`. TAG-FE tem dependência
vazia e pode trabalhar em paralelo; TAG-BE depende de TAG-DB; integração consome FE+BE.

O endpoint de requisito mantém revisões aprovadas imutáveis e versiona novas
revisões; testes `apps/factory-api/tests/test_requirement_revision_api.py` e
`tests/integrations/test_intake_connectors.py::test_refinement_creates_history_and_approved_revision_is_immutable`
passaram (2 testes). Isso cobre hash stale, decisão vinculada, replay e histórico;
rejeição/`needs_changes` é coberta pelo contrato do endpoint e deve ser mantida no
histórico, sem editar v1/v2.

Não alegar autoria de persona Analyst/Planner Factory: os fatos acima são discovery
assistido pelo Codex com paths/linhas verificáveis; a aprovação dos defaults é do
operador e a decisão EARS/plano está identificada conforme seu ator real.
