# Pesquisa aplicada: fábricas agênticas, evals e rubricas

Pesquisa em fontes primárias consultadas em 2026-10-24. Complementa a [auditoria do projeto](auditoria-projeto-2026-10-24.md). Esta etapa produz definições, cenários e backlog; não implementa harness, executa benchmark, altera prompts ativos ou aprova rótulos humanos.

## 1. O que as fontes acrescentam

| Fonte primária e data | Contribuição relevante | Aplicação proposta neste projeto |
|---|---|---|
| S01 — Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/research/demystifying-evals-for-ai-agents), 09/01/2026 | Distingue tarefa, tentativa, trajetória, resultado no ambiente e grader; separa suites de capacidade e regressão. | Contrato de eval com tipos de evidência distintos, repetição e promoção de casos entre suites. |
| S02 — Anthropic, [Effective harnesses for long-running agents](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents), 26/11/2025 | Continuidade entre sessões depende de estado e artefatos de progresso; contexto resumido não resolve todo o problema. | Medir qualidade do handoff e reorientação após reset, além do restart de processo já planejado. |
| S03 — Anthropic, [Harness design for long-running application development](https://www.anthropic.com/research/harness-design-long-running-apps), 24/03/2026 | Relata separação planner/generator/evaluator, contratos por incremento e inspeção de aplicação em uso. Também mostra que custo e qualidade variam com o harness. | Rubricas de entrega e desenho visual compatíveis com o Registry; comparar arquiteturas sob orçamento equivalente. Não presumir que mais personas sempre ajudam. |
| S04 — Anthropic, [Quantifying infrastructure noise in agentic coding evals](https://www.anthropic.com/research/infrastructure-noise), 05/02/2026 | CPU/RAM, limites e sua forma de aplicação interferem no resultado. | Controlar recursos e registrar OOM/timeouts; separar capacidade sob orçamento de falha do laboratório. |
| S05 — Anthropic, [Writing effective tools for agents — with agents](https://www.anthropic.com/research/writing-tools-for-agents), 11/09/2025 | Ferramentas precisam de contratos compreensíveis para o agente e retornos úteis; nomes, descrições e payloads merecem avaliação. | Ensaios de ergonomia do ToolGateway com LLM real, sem exigir uma sequência única de chamadas quando houver alternativas válidas. |
| S06 — Anthropic, [Define success criteria and build evaluations](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests), documentação consultada | Recomenda critérios específicos e multidimensionais, escolhendo a forma de correção adequada ao comportamento. | Cada critério terá evidência, aplicabilidade, tipo de grader e regra de interpretação. |
| S07 — Anthropic, [Define outcomes](https://platform.claude.com/docs/en/managed-agents/define-outcomes), documentação consultada | Apresenta rubricas com critérios avaliáveis individualmente. | Usar a ideia no runner local. Nenhuma adoção do serviço Managed Agents ou dependência de API paga é proposta. |
| S08 — Zheng et al., [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685), 2023 | Estuda vieses de posição, verbosidade e autoavaliação, além de limitações do julgamento por LLM. | Metatestes A/B com ordem trocada, anonimização e variações de estilo sem mudança factual. Resultados de modelos do artigo não certificam os modelos locais. |
| S09 — Yao et al., [τ-bench](https://arxiv.org/abs/2406.12045), 17/06/2024 | Avalia interação usuário-agente com ferramentas e compara estado final do banco; introduz uma medida de consistência entre tentativas. | Conversas com respostas de usuário controladas e oráculo de estado final, incluindo casos em que sucesso é não modificar nada. |
| S10 — OpenAI, [Separating signal from noise in coding evaluations](https://openai.com/index/separating-signal-from-noise-coding-evaluations/), 08/07/2026 | Audita problemas de especificação e testes em SWE-Bench Pro: rigor excessivo, cobertura insuficiente e contradições podem distorcer resultados. | Auditar nossos próprios graders com implementações corretas alternativas e defeitos semeados; não importar um leaderboard como certificado de qualidade. |
| S11 — StrongDM, [Software Factories and the Agentic Moment](https://factory.strongdm.ai/), 06/02/2026 | Relato do próprio fornecedor sobre cenários externos ao código e simuladores comportamentais de integrações. | Manter oráculos fora da permissão do executor e criar simuladores pequenos de GitHub/Telegram. O relato não é validação independente; sua proposta de remover revisão humana não altera os HITLs deste projeto. |
| S12 — Anthropic, [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/research/building-c-compiler), 05/02/2026 | Estudo de caso enfatiza verificação e feedback; conflitos em um gargalo compartilhado podem limitar paralelismo. | Avaliar decomposição útil, trabalho duplicado e custo de coordenação. Não reproduzir escala, gasto, permissões ou infraestrutura do experimento. |
| S13 — Liu et al., [G-Eval](https://aclanthology.org/2023.emnlp-main.153/), EMNLP 2023 | Investiga avaliação estruturada de texto e alinhamento com julgamentos humanos. | Exigir parecer curto fundamentado, além da nota; não transferir resultados de sumarização para correção de software. |
| S14 — Kim et al., [Prometheus](https://arxiv.org/abs/2310.08491), 2023 | Explora avaliação com rubricas específicas, descrições de notas e referências. | Escrever âncoras por critério e exemplos de fronteira. Não exige instalar esse modelo ou fazer fine-tuning. |

As definições de escala, prioridades e casos nos arquivos deste projeto são **propostas próprias**, inspiradas nessas fontes e nas falhas observadas no código. Não são recomendações universais dos autores nem ganhos já medidos.

## 2. Lacunas locais confirmadas

A rubrica ativa [judge-v1.json](../evals/rubrics/judge-v1.json) usa escala 1–5 e lista `correctness`, `evidence_coverage` e `policy_adherence`, mas não define o significado de cada nota por critério. `JudgeVerdict` recebe uma nota global; não preserva resultados por critério/aplicabilidade. Os manifests referenciam rubricas como `analyst-v1` e `planner-v1`, sem arquivos correspondentes na pasta de rubricas inspecionada; Reviewer tem outra definição parcial inline em policy.

`EvalObservation` e o scorecard atual não distinguem bem tentativas, defeito do grader, falha de infraestrutura e aprovação de produto. A calibração considera `pass` a classe positiva; portanto seu `recall` atual mede recuperação de aprovações, não detecção de defeitos. O `confidence` fornecido pelo Judge é autorrelato e não probabilidade empiricamente calibrada.

O plano anterior já cobre origem por run/SHA, contexto, gates, revisão, labels, restart, publicação e uma feature inédita. O acréscimo desta pesquisa é tornar **o próprio processo de avaliação testável**, acrescentar comportamentos negativos/proporcionais e medir quais partes da arquitetura ajudam sob a GPU e o orçamento locais.

## 3. Incremento sem duplicar o backlog

| Tema novo | O que já existia | Diferença de aceite acrescentada |
|---|---|---|
| Rubricas por persona | FAC-075/129 e LLMG-T13 | Âncoras observáveis, N/A/sem evidência, revisão das rubricas e adjudicação; FAC-140. |
| Qualidade do avaliador | FAC-105/117 validam contratos/gates | Provar que o grader aceita alternativas corretas e rejeita soluções incompletas; FAC-141. |
| Robustez do Judge | FAC-077/129 e LLMG-T14/15 | Posição, estilo, autoria declarada, referência fabricada e injeção no texto avaliado; FAC-142. |
| Confiabilidade estatística | LLMG-T10/12 repetem benchmarks | Distinguir sucesso ocasional de sucesso consistente e publicar denominadores/intervalos; FAC-143. |
| Ruído de infraestrutura | FAC-137/LLMG-T08 tratam falhas/warm-cold | Ensaio controlado da política de recursos e validade de comparação; FAC-144. |
| Continuidade cognitiva | FAC-119/137 tratam restart durável | Novo contexto deve reconstruir estado sem perder regra/decisão ou duplicar trabalho; FAC-145. |
| Valor da arquitetura | FAC-114/118 integram papéis | Ablation mede baseline simples versus papéis extras sem retirar políticas; FAC-146. |
| Ergonomia das tools | FAC-051/124 implementam gateway | Medir seleção, parâmetros, recuperação e utilidade dos outputs para LLM; FAC-147. |
| Manutenção das suites | FAC-076/129 congelam datasets | Incidente → candidato revisado → capacidade → regressão, com separação por família; FAC-148. |
| Interação proporcional | FAC-112/120/125 permitem esclarecer | Avaliar quando agir, perguntar, responder ou concluir sem patch; FAC-149. |
| Novas demandas fullstack | FAC-131–134 usam etiquetas | Importação com prévia, exportação segura e paginação compatível, como famílias de capability; FAC-150. |
| Invariância de intenção | FAC-130 prova três entradas | Variantes semânticas/canais diferentes devem manter obrigações e permissões; FAC-151. |
| Simulação comportamental | Contratos fake de conectores | Simuladores persistentes de múltiplas etapas, com relógio/eventos controlados e limites explícitos; FAC-152. |

As três famílias novas de produto são **demandas de avaliação de capacidade**. Não expandem silenciosamente o MVP contratado: uma família pode continuar difícil/sem sucesso e ainda fornecer diagnóstico válido. Comportamentos já promovidos a regressão mantêm o nível de qualidade aprovado.

## 4. Artefatos entregues nesta etapa

- [Especificação aplicada de evals e rubricas](../specs/09-EVALS-RUBRICAS-E-HARNESS.md).
- [Fase P20 / FAC-140–152](../specs/fases/p20.md), com dependências e aceites futuros.
- [Oito rubricas em draft](../evals/design/rubrics-v2-draft.json), com critérios ancorados por papel.
- [Catálogo de cenários em draft](../evals/design/scenarios-v2-draft.json), com preparação, resultado observável e controle negativo.
- [Guia dos drafts](../evals/design/README.md), incluindo calibração e métricas propostas.

Nenhum draft entra no manifest ativo, prompt, release ou calibração corrente. Os gabaritos humanos existentes permanecem intactos; os novos casos ainda precisam de implementação de fixture, revisão humana e prova de que seu próprio grader é válido.

## 5. Ordem recomendada

Começar por FAC-140/141/148: descrever critérios, auditar oráculos e estruturar suites. Isso pode avançar antes do runtime real e evita gastar GPU julgando critérios defeituosos. Com o runtime disponível, executar um subconjunto pequeno de FAC-149/150/152; depois medir repetição, handoff, ferramentas, variantes e ablation. Calibrar FAC-142 antes de usar nota do Judge para decisões comparativas.

Usar modo local, uma inferência pesada por vez, número pequeno de casos de desenvolvimento e limites explícitos. Ampliar repetições quando necessário para uma decisão, sem transformar cada chat em benchmark completo. Diferença de score sem incerteza, controles e denominadores é hipótese, não melhora comprovada.
