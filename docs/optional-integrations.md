# Integrações opcionais

GitHub Projects v2 e Jira Cloud são espelhos/intake opt-in. Deixe
`GITHUB_PROJECTS_ENABLED=false` e `JIRA_ENABLED=false` para o modo local offline;
nessa configuração nenhum token ou destino externo é necessário. Os contratos
fakes estão em `tests/contracts/`.

O webhook GitHub só é registrado quando `GITHUB_WEBHOOK_SECRET` está definido.
Ele valida HMAC-SHA256, limita o payload a 1 MB, aceita apenas Issues e cria a
Demand como não executável; não inicia discovery nem execução. Túnel não faz
parte do caminho padrão. API/UI de administração e Ollama não são publicados.

Credenciais reais permanecem em `.env`, nunca em `specs`, logs ou artefatos.
Tokens/destinos live não foram usados nos smoke tests locais.
