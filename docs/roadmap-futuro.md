# Roadmap futuro: CI/deploy (desativado)

Este documento é planejamento. Nenhum workflow CI, segredo GitHub, VPS ou deploy
remoto é necessário para operar e validar a stack local atual.

## Sequência opcional

1. Após aceite humano da P13, desenhar CI de lint/testes em runner descartável.
2. Definir gestão e rotação de secrets antes de qualquer workflow que use credenciais.
3. Separar build de artefatos de qualquer ação de publicação.
4. Exigir aprovação humana hash-bound para deploy e rollback.
5. Avaliar hosting remoto somente com decisão explícita de operação e threat model.

## Gates antes de ativar

- Confirmar owner, ambientes, retenção, restauração e limites de custo.
- Usar credenciais de privilégio mínimo e ambientes protegidos.
- Manter integrações GitHub/Jira/webhook opt-in; offline continua suportado.
- Revisar scripts e permissões; deploy não deve entrar no caminho crítico local.
- Validar rollback em ambiente descartável e obter aceite humano independente.

Estado atual: **roadmap apenas; CI e deploy continuam desabilitados**.
