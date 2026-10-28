# Feature inédita de aceite — etiquetas de clientes

**Estado: contrato de produto definido pelo operador; discovery/agendamento pela Factory e autoria agêntica ainda não comprovados.** Este dossiê define o ensaio da fábrica. Em 2026-10-26 o operador aprovou múltiplas etiquetas por cliente, catálogo compartilhado, desvinculação sem apagar catálogo, trim+casefold com acentos preservados, nomes de 1–32 caracteres, máximo de 10 etiquetas por cliente, filtro de uma etiqueta combinado por AND com busca textual, omitido preserva/[] limpa, sem rename/delete neste incremento e operador único local. Atividades de controle: FAC-131–134; dependências do runtime em [P16](../../fases/p16.md).

Chamadas autenticadas reais Factory→OpenBot foram repetidas em 2026-10-26 contra uma cópia limpa do baseline. A resposta Qwen3 foi retida por formato privado; Qwen2.5 respondeu sem citar paths, repetiu partes do prompt e foi rejeitada como discovery. O Planner respondeu BLOQUEADO enquanto o requisito estava `proposed`. Essas respostas não foram promovidas a requisito. Posteriormente, EARS e DAG foram registrados sob delegação IA explícita, sem alegar autoria dessas personas; ver `contract-review.md`. O inventário de baseline é `.runtime/artifacts/fac-131-134/fac131-baseline-inventory.json`; o pacote de revisão atual está em `contract-review.md`. O checkout atual já contém implementação de etiquetas e migração; portanto, ele não é um baseline sem solução e não pode provar que TAG-DB/TAG-BE/TAG-FE foram geradas pela Factory. Os testes UI/API/PostgreSQL existentes validam comportamento de componente, não autoria nem jornada integrada.

## Demanda inicial

> Quero organizar clientes por etiquetas e filtrar a lista por etiqueta.

No baseline Git `00d1a782ece691ad510fb4ef318590eea3540fff`, `customer-registry` tem usuários e telefone, sem implementação de etiquetas. Esse baseline já foi inventariado; o checkout atual tem tags e deve ser preservado fora do ensaio de autoria. Cada repetição do ensaio parte de uma cópia limpa desse baseline.

Objetivo da validação: o fluxo recebe somente o pedido, investiga o repositório, esclarece produto, gera contrato/plano e produz uma mudança inédita em banco, backend e frontend, com qualidade, revisão e evidências. Não adicionar etiquetas manualmente antes do ensaio e depois atribuir a autoria aos agentes.

## Discovery que o agente deverá realizar

Investigar modelos/migrations, schemas/rotas/repositórios, contrato do cliente React, formulário/listagem/busca, padrões de validação/erro, testes, índices e estratégia de execução local. Registrar arquivos e commit efetivamente lidos, fatos, hipóteses, limites e impacto. Não declarar path existente só porque foi sugerido neste documento.

Perguntas de produto que podem mudar contrato/escopo:

1. Um cliente pode ter várias etiquetas ou apenas uma categoria?
2. Etiquetas são catálogo compartilhado? Quem cria, renomeia ou exclui? Basta criar e desvincular neste primeiro incremento?
3. Diferenças de maiúscula/espaços/acentos representam a mesma etiqueta? Qual tamanho e limite por cliente?
4. O filtro escolhe uma ou várias etiquetas? Se várias, combinação AND ou OR? Como combina com busca textual e clientes inativos?
5. Desvincular remove só a associação ou apaga a etiqueta globalmente? O que acontece com clientes antigos?
6. A demo permanece single-operator local, com as permissões já existentes, ou foi solicitado novo controle de acesso?

O agente deve condensar perguntas quando houver convenções existentes suficientes. Só pedir decisão sobre ambiguidades materiais. Guardar pergunta/resposta no mesmo card/run; mensagens de esclarecimento não são novas demandas.

## Proposta de contrato para refinamento

**Proposta histórica anterior aos defaults aprovados:** várias etiquetas por cliente, catálogo compartilhado, nome preservado para exibição e unicidade por trim/casefold; sem apagar acentos automaticamente. Nomes de 1–32 caracteres e limite de 10 etiquetas por cliente foram posteriormente aprovados nos defaults; conferir a decisão/revisão concreta em `contract-review.md`.

Incremento sugerido: criar/listar etiquetas, atribuir/desvincular no formulário de cliente, exibir na listagem e filtrar por uma etiqueta combinada à busca existente. Clientes antigos começam sem etiquetas. Desvincular não exclui o catálogo; renomear/excluir catálogo, filtros múltiplos, cor de etiqueta e novos papéis de acesso ficam fora deste incremento **se o operador concordar**.

Desenho candidato, somente após discovery e decisão:

| Camada | Contrato candidato |
|---|---|
| Dados | `tags` com UUID/nome/nome normalizado e constraints; associação usuário-etiqueta com unicidade e FKs. |
| API catálogo | GET/POST `/api/v1/tags`, validação tipada e conflito 409 para nome normalizado duplicado. |
| API usuários | `tag_ids` em criação/edição e representação de etiquetas na leitura; omitir preserva, `[]` limpa, ID desconhecido é erro explícito. |
| Filtro | GET `/api/v1/users?tag_id=<uuid>&search=...`; preservar semântica active/include_inactive existente. |
| Frontend | Criar/selecionar/remover etiquetas com teclado, exibir chips/texto e filtro com limpar; estados assíncronos visíveis. |
| Compatibilidade | Payloads antigos sem etiquetas continuam válidos; migration preserva cadastros e telefone. |

Caso discovery encontre alternativa mais simples compatível com o projeto, o Planner deve apresentá-la e congelar o contrato escolhido antes de front/back começarem. Este desenho não substitui a investigação do agente nem autoriza expansão de escopo.

## Requisitos EARS candidatos

O texto abaixo é o **draft histórico**, com IDs/conteúdo que precisam de conciliação com a revisão concreta aprovada por IA delegada. Não tratá-lo como revisão canônica nem solicitar outra decisão idêntica:

- TAG-R01: Quando o operador criar uma etiqueta com nome válido, o sistema deverá persistir e disponibilizar a etiqueta para seleção após recarregar a página.
- TAG-R02: Se o nome violar a regra aprovada ou duplicar um nome normalizado, o sistema deverá rejeitar a operação sem criar registro parcial.
- TAG-R03: Quando o operador criar/editar um cliente com etiquetas válidas, o sistema deverá salvar exatamente as associações selecionadas, sem duplicatas.
- TAG-R04: Quando o operador remover uma associação e salvar, o sistema deverá desvincular a etiqueta somente daquele cliente; sua semântica global deverá seguir o contrato aprovado.
- TAG-R05: Quando um filtro de etiqueta estiver ativo, a lista deverá mostrar somente clientes que atendam à etiqueta e aos demais filtros aplicáveis.
- TAG-R06: Enquanto a operação estiver pendente ou falhar, a UI deverá informar o estado e permitir recuperação sem fingir que os dados foram salvos.
- TAG-R07: Quando a migração for aplicada sobre base populada, clientes existentes deverão permanecer consultáveis/editáveis e sem associações inventadas.
- TAG-R08: Se houver resposta/edição concorrente ou replay da mesma operação no workflow, o histórico deverá manter uma demanda e execuções/decisões idempotentes conforme o contrato do Task Engine.

Limites e regras específicos devem ser substituídos pelos aprovados na revisão final; não carimbar esta proposta como requisito congelado sem decisão.

## DAG de trabalho gerada/validada no ensaio

Os IDs TAG abaixo são **tasks de domínio que a fábrica criará no banco**, enquanto FAC-131–134 são atividades do backlog do projeto para viabilizar e validar o ensaio. Não confundir os dois níveis.

| Child task proposta | Persona | Dependências | Entrega / paths a autorizar |
|---|---|---|---|
| TAG-DISC | Analyst | Intake | Evidências e perguntas sobre o cadastro, snapshot da investigação. |
| TAG-REQ | Analyst/Planner | TAG-DISC + respostas | Requisito/contrato/EARS/cenários e decisão humana versionada. |
| TAG-PLAN | Planner | TAG-REQ | DAG, paths, riscos, orçamento e plano final aprovado. |
| TAG-DB | Backend/Database | TAG-PLAN | Models e migration Registry; testes de dados/compatibilidade. |
| TAG-BE | Backend | TAG-DB | API/repository/validações e testes de contrato/integração. |
| TAG-FE | Frontend | TAG-PLAN | UI e cliente usando contrato congelado; pode evoluir em paralelo a TAG-DB/BE. |
| TAG-DOC | Docs/Analyst | TAG-BE + TAG-FE | Contrato final, exemplos sintéticos e runbook da feature no escopo permitido. |
| TAG-INTEGRATE | Platform | TAG-BE + TAG-FE + TAG-DOC | Branch isolada com commits, resolução de conflitos e reteste no SHA integrado. |
| TAG-QA | QA | TAG-INTEGRATE | Unit/contract/PG/E2E/acessibilidade/regressão/security e artefatos verificados. |
| TAG-REVIEW | Reviewer | TAG-QA | Findings e decisão no SHA final, sem editar patch. |
| TAG-DELIVERY | Operator/flow | TAG-REVIEW + decisões pertinentes | Pacote local, resultado no canal e eventual publicação explicitamente autorizada. |

Não usar o mesmo worktree para TAG-FE/TAG-BE. A aprovação deve incluir testes e arquivos novos necessários, evitando que o executor precise ampliar paths por conta própria. Mudança de contrato após início invalida plano/approvals pertinentes e gera reconciliação; não ajustar frontend silenciosamente a um backend divergente.

## Roteiro do ensaio real

1. Verificar runtime/workers/modelo/preflight, baseline sem etiquetas e banco sintético populado. Registrar SHA/digests/config; preservar testes ocultos fora do contexto e das permissões do agente.
2. Enviar a demanda por frontend, Telegram ou GitHub Issue. Para comparação entre canais, repetir em baselines independentes; não reutilizar um produto já alterado.
3. Acompanhar discovery, responder perguntas e aprovar requisito e plano final. Persistir transcrição, revisões e hashes; não criar manualmente as tasks técnicas para contornar Planner ausente.
4. Deixar o workflow gerar/executar TAG-DB/BE/FE/DOC com Ollama local. Guardar tool calls permitidas, orçamento, patches e commits por task.
5. Integrar branches e executar a [matriz de aceite](acceptance.md) no código integrado com API/PostgreSQL/UI reais. A rodada final não pode usar mocks de API para provar comportamento da feature.
6. Injetar pelo menos uma falha funcional e um conflito controlado. Observar veto, diagnóstico e retrabalho dentro do limite; infraestrutura não vira patch de código automático.
7. Reviewer revisa evidência do commit entregue; humano decide onde o escopo exige. Resultado retorna ao canal inicial sem afirmar merge/deploy automático.
8. Depois de concluída, pedir `@qa` um teste de remoção de etiqueta inexistente ou outro cenário aprovado que ainda falte. O fluxo deve criar somente follow-up QA, preservando a demanda/requisito originais.

## Condição de sucesso

O cadastro antigo e a funcionalidade nova funcionam juntos; o transcript demonstra autoria agêntica; estado, aprovações, patch, gates e review pertencem aos mesmos IDs/versões/commits; nenhum gate é satisfeito por resultado antigo ou testes enfraquecidos. A assinatura independente só ocorre depois dessas provas.

Estado consolidado em 2026-10-27: baseline, defaults, decisão EARS delegada e DAG proposto existem; autoria grounded Analyst/Planner e geração/integração/follow-up Factory ainda não foram aceitos. Passos restantes e critérios: [roteiro FAC-131–134](../../10-FECHAMENTO-DAS-12-PENDENCIAS.md).
