# Provisionar a chave de assinatura UAT (fluxo humano legado)

Este procedimento está temporariamente desativado por solicitação do operador.
O aceite técnico atual usa reviewer local de IA e receipt verificado; veja
[política](ai-acceptance-policy.md). Decisões HITL para efeitos externos continuam
sem alteração. As instruções abaixo permanecem apenas para histórico e não
autorizam aceite humano no scorecard atual.

O relatório de aceite só considera uma aprovação quando `scripts/acceptance_report.py`
verifica a assinatura OpenSSH e todos os hashes do pacote. Não use uma chave de executor
ou uma chave temporária compartilhada como identidade do revisor.

## Provisionamento pelo responsável do projeto

1. O revisor independente gera uma chave Ed25519 dedicada, em dispositivo/conta sob seu
   controle: `ssh-keygen -t ed25519 -f uat-review -C "<identidade institucional>"`.
2. O responsável verifica a identidade por canal organizacional conhecido e recebe a
   chave pública por canal autenticado. A chave privada fica com o revisor.
3. Em `.runtime/artifacts/uat/allowed_signers`, o responsável registra exatamente:
   `<identidade verificada> namespaces="agentic-factory-uat" <conteúdo da chave pública>`.
   O arquivo e o diretório devem pertencer ao operador local e não ser symlinks.
4. O revisor assina o JSON canônico indicado no packet, com `ssh-keygen -Y sign -n
   agentic-factory-uat -f uat-review`. O registro de aprovação inclui a identidade,
   decisão, timestamp, escopo, hash do backlog e hash do manifest de evidências.
5. Rotação/revogação exige substituir a linha autorizada e invalidar aprovações
   assinadas pela chave anterior. Não versionar chaves privadas nem confiar em uma
   identidade apenas por estar no JSON de aprovação.

Este repositório não contém chave pública de revisor porque nenhuma identidade
independente foi fornecida/verificada. A ausência do arquivo `allowed_signers` mantém
corretamente o relatório em `pending_independent_human_review`.

## Manifest de evidências

`evidence_manifest` aponta para JSON sob `.runtime/artifacts/uat/`. O manifest deve
conter `run_id`, `task_id`, `git_sha`, `tree_sha`, lista não vazia de artefatos com
`path` e `sha256`, lista de gates PASS amarrados aos mesmos run/task/SHA/tree e uma
revisão aprovada por pessoa diferente do signatário UAT. Cada caminho deve permanecer
sob `.runtime`; o gerador reabre os arquivos e recalcula os hashes durante a verificação.
Use artefatos originados do executor/gates autoritativos, nunca arquivos de demonstração.
