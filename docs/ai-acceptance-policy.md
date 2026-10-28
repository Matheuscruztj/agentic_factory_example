# Aceite técnico por IA (vigente por solicitação do operador)

O aceite de implementação e de evidências automatizadas pode ser realizado por
um reviewer local de IA, sem assinatura humana. Esse aceite cobre somente os
critérios técnicos que podem ser verificados no checkout, nas suites, nos runs e
nos artefatos citados.

## Registro obrigatório

Cada decisão precisa conter atividade, decisão (`approve`, `reject` ou
`uncertain`), modelo/tag e digest, identidade distinta do executor, prompt e
hash, snapshot revisado, referências e hashes das evidências, gate results,
timestamp e rationale com citações. O revisor não pode editar arquivos nem
fabricar evidências; os hashes são recalculados antes da decisão. Um gate
ausente/falho, referência não encontrada, modelo igual ao executor, evidência
stale, dependência aberta ou confiança baixa resulta em `uncertain`/rejeição.

O aceite de atividade usa decisão por evidências (`pass`, `fail` ou
`uncertain`), confiança mínima 0,8 e citações verificáveis. A nota numérica do
Judge permanece para calibração de avaliações e não substitui essa decisão.

O modelo pode aceitar critérios técnicos se todas as evidências requeridas
estiverem presentes e os gates determinísticos passarem. Datasets provisórios
continuam identificados como provisórios; aceite por IA não os transforma em
gold humano nem autoriza promoção baseada em rótulos não independentes.

## Limites

Esse aceite substitui a assinatura humana de UAT para o momento, por instrução
explícita do operador. Ele não é apresentado como aceite humano. Aprovações
persistidas de escopo para execução, envio de Telegram, escrita GitHub, push,
PR, merge, deploy, mudança de secrets/policies e expansão de escopo mantêm os
HITLs separados previstos nas especificações.

O scorecard global só pode dizer `accepted_by_ai` quando os requisitos
obrigatórios estiverem concluídos, todos os runs/gates/artifacts estiverem
verificados e um receipt de IA válido estiver ligado ao hash exato do backlog
e do pacote de evidências. Enquanto isso, o scorecard permanece pendente.
