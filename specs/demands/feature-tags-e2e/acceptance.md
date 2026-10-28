# Aceite e qualidade — feature inédita de etiquetas

**Estado em 2026-10-27: requisito e plano delegados; implementação assisted passou nos gates locais de API, build, integração de navegador e testes focados de etiquetas. Isso não equivale a aceite humano nem encerra FAC-131–133. A matriz abaixo segue sendo a fonte dos critérios; a evidência parcial e as lacunas estão discriminadas em [contract-review](contract-review.md) e no [roteiro FAC-131–134](../../10-FECHAMENTO-DAS-12-PENDENCIAS.md).

## Matriz de cenários

| ID | Camada / cenário | Evidência exigida |
|---|---|---|
| TAG-A01 | Criar etiqueta válida e listar após reload | Resposta API, registro PostgreSQL e UI exibindo o mesmo ID/nome. |
| TAG-A02 | Nome vazio, só espaços, acima do limite e tipos inválidos | Erro 4xx estável, sem gravação parcial, feedback compreensível na UI. |
| TAG-A03 | Nome duplicado normalizado, inclusive duas criações concorrentes | Constraint no banco, uma criação e conflito tipado; regra aprovada de case/acentos respeitada. |
| TAG-A04 | Criar cliente sem etiquetas, com uma e com várias dentro do limite | Clientes legados/novos válidos; associações exatas e sem duplicatas. |
| TAG-A05 | Editar associações: adicionar, remover uma, limpar todas e omitir campo | Semântica `[]`/omitido/null definida; persistência observada após refresh. |
| TAG-A06 | Tag ID desconhecido/malformado, IDs repetidos e acima do limite | Rejeição coerente, transação atômica e associações anteriores preservadas. |
| TAG-A07 | Filtro por etiqueta existente, sem resultados e combinação com busca | UI/API/banco concordam; limpar filtro restaura lista conforme status. |
| TAG-A08 | Cliente inativo e mudança de status com associações | Semântica active/include_inactive preservada e associação sem perda indevida. |
| TAG-A09 | Desvincular de um cliente com etiqueta usada por outro | Outro cliente/catálogo permanecem intactos conforme decisão aprovada. |
| TAG-A10 | Migration em base vazia e populada com telefone | Upgrade/readback, dados antigos preservados, estratégia de downgrade/rollback documentada e exercitada em cópia. |
| TAG-A11 | Rede lenta, API 4xx/5xx e retry do operador | Loading/erro visíveis; formulário não perde seleção indevidamente nem informa sucesso falso. |
| TAG-A12 | Uso por teclado, labels, foco, mobile e textos extensos | Playwright/interação acessível; layout funcional e erros anunciados. |
| TAG-A13 | Entrada HTML/script em nome e payload de filtro inválido | Renderização como texto, sem execução; validação no servidor e sem SQL concatenado. |
| TAG-A14 | Listagem com volume sintético e muitas associações | Número de queries sem crescimento N+1, latência e limite registrados contra orçamento acordado antes do teste. |
| TAG-A15 | Regressão de username/email/telefone/desativação | Suítes existentes, incluindo limpar telefone, permanecem aprovadas no SHA integrado. |
| TAG-A16 | Integração de front/back gerados em worktrees distintos | Commits independentes, merge isolado, testes no resultado; conflito não some silenciosamente. |
| TAG-A17 | Gate falho, output inconsistente ou arquivo de resultado adulterado | Veto determinístico; task/demanda não ficam done por resposta de LLM ou review antigo. |
| TAG-A18 | Restart em pergunta, inferência, após commit e antes de recibo | Continuidade em PostgreSQL/checkpointer e nenhum efeito duplicado, com contagens verificáveis. |
| TAG-A19 | Resultado e evidências vistos pelo canal de origem | Mesmo demand/run/commit na UI e no retorno Telegram/GitHub quando autorizado. |
| TAG-A20 | Follow-up QA após entrega | Nova task/commit de teste, requisito/histórico original imutáveis e discovery reutilizado quando suficiente. |

## Gates da entrega

| Gate | Execução necessária | Bloqueio |
|---|---|---|
| Python | Ruff, mypy com alvos justificados, unitários, contrato e integração Registry/Task Engine afetados | Falha de código impede entrega; erro de ambiente pausa/diagnostica. |
| Frontend | TypeScript, Vitest e build da UI alterada; lint conforme tooling contratado | Não aceitar só o build da Factory Web para mudança no Registry. |
| Dados | PostgreSQL real descartável, constraints concorrentes e migrações | SQLite sozinho não comprova semântica PostgreSQL. |
| E2E | Browser → React → API → PostgreSQL, sem mocks do comportamento de etiquetas | Fixtures de API não substituem rodada integrada. |
| Segurança | Secrets/paths/policy, SAST/SCA aplicáveis e casos de inputs maliciosos | High/critical conforme policy e qualquer quebra de autorização vetam. |
| Integridade | Tests/gates protegidos e asserts ocultos externos ao executor | Remover teste ou alterar resultado não é correção aceita. |
| Review | Reviewer independente com diff, requisito e gates do SHA entregue | Findings relevantes exigem correção/revisão nova. |
| Aceite técnico | Reviewer IA independente percorre provas e verifica hashes, conforme política vigente | Receipt sem artefatos completos não encerra atividade; decisões de produto/efeitos privilegiados permanecem separadas. |

Perf/DAST/Sonar/Phoenix e escaneamento estendido entram conforme risco/escopo selecionados. Não fabricar SLA para TAG-A14: medir baseline, acordar limite e publicar amostra/config. Não registrar medição ausente como zero.

## Registro de proveniência

Para cada resultado: `demand_id`, requisito/versão/hash, plano/hash, `task_id`, `run_id`, tentativa, persona, modelo/digest/quantização disponível, prompt/context/skills, base Git e commit/tree testado, suite/config/tool versions, timestamps, exit 0/1/2, artefato/hash e decisão de review/HITL.

Guardar o registro completo em artefatos locais redigidos, e apenas metadados/links no relatório compacto. Testes ocultos, rótulos humanos e segredos não entram no prompt do executor. Falha por budget/modelo/infra deve aparecer como tal, sem marcar a feature implementada.

## Rastreabilidade de aceite

- Discovery/requisito/plano: FAC-131, TAG-R01–08.
- Dados/backend: FAC-132, TAG-A01–10/13–15.
- UI/integração/qualidade: FAC-133, TAG-A01/04–17.
- Follow-up: FAC-134, TAG-A20.
- Confiabilidade/observabilidade/aceite final: FAC-137–139, TAG-A18–19 e todas as evidências obrigatórias.

Evidência executada nesta tentativa: suíte focused de API cobre nomes/duplicidade, atribuição, filtro, limpeza, IDs inválidos/atomicidade e limite dez; o E2E integrado cobre criação/edição, catálogo/filtro e associação no navegador. A integração passou em Python, TypeScript/build e Playwright no SHA `da379aa122fd601899e41cd9910c898823267fa3`; os testes focused passaram no SHA `6a4985be003d6bf9b69ac51450f672d0fccf6ae0`. Os artefatos com hashes estão em `.runtime/artifacts/run/`.

Atualização 2026-10-27: migrações passaram em PostgreSQL descartável vazio e populado. Upgrade preservou usuário/telefone legado; downgrade que truncaria `normalized_name` com casefold Unicode >32 foi recusado; após remover o fixture de risco, downgrade para 0003 e upgrade para head preservaram os dados. Artefato: `.runtime/artifacts/next-five/postgres-migration-proof.json`. Uma validação da API contra outro PostgreSQL descartável passou catálogo, nomes, acentos, duplicidade concorrente (201/409), vínculo de 10 etiquetas, filtro, omissão/limpeza, rollback sem alteração parcial para entradas inválidas, limite de nome, PK composta e duas FKs; detalhes em `.runtime/artifacts/next-five/postgres-tag-api-proof.json`. A primeira tentativa de inspecionar a chave composta consultou unique constraints; essa checagem foi corrigida e passou via primary key inspector em um banco descartável novo.

E2E browser→React→API→PostgreSQL também passou em DB descartável. O novo spec Playwright cobre viewport 375px, criação de etiquetas, associação, filtro+busca, remoção de vínculo, reload e foco de teclado; na mesma execução passaram regressões de cliente/telefone e estados/foco do botão (3/3). Readback SQL confirmou cliente ativo e associação persistida. ESLint do spec e build web passaram. Evidência: `.runtime/artifacts/next-five/tags-browser-postgres-e2e.json` e `.runtime/artifacts/next-five/tags-postgres-playwright.log`.

Ainda faltam: repetir e vincular as provas PostgreSQL à autoria do worker; revisão de atividade FAC-131–133 após decisão humana e conflito resolvido; segurança/performance conforme risco; validação visual/a11y completa além dos casos de teclado/mobile cobertos; restart/outbox nas jornadas de tags; confirmação do contrato de produto por pessoa autorizada. Não marcar a matriz inteira como aprovada com base nos gates parciais.
