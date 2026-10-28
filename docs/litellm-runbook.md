# Runbook local do LiteLLM

O LiteLLM é opt-in. O caminho direto usa `OllamaAdapter` e `OLLAMA_BASE_URL`; o gateway usa `LiteLLMGatewayAdapter` e o alias configurado em `infra/litellm/config.example.yaml`. A seleção é explícita no chamador. Não há fallback automático entre rotas nem para serviços externos.

## Pré-verificação

Na raiz do repositório, confirme a sintaxe e os dois perfis Compose sem iniciar containers:

```bash
uv run python scripts/validate_llm_gateway.py --mode syntactic
uv run python scripts/validate_llm_gateway.py --mode dry-run
```

O perfil `litellm` exige `LITELLM_ENABLED=true` e `LITELLM_MASTER_KEY` válida no `.env` local. Não imprima nem copie essa chave para logs. `LITELLM_BASE_URL` usa `http://127.0.0.1:4000` no host; dentro da rede Compose, o serviço atende em `http://litellm:4000`.

## Iniciar e parar

```bash
docker compose -f infra/compose/ai-services.yml -f infra/compose/litellm.yml --profile litellm up -d litellm
docker compose -f infra/compose/ai-services.yml -f infra/compose/litellm.yml ps litellm
uv run python scripts/validate_llm_gateway.py --mode live
docker compose -f infra/compose/ai-services.yml -f infra/compose/litellm.yml stop litellm
```

Para remover também o container e a rede do projeto:

```bash
docker compose -f infra/compose/ai-services.yml -f infra/compose/litellm.yml --profile litellm down
```

O comando `down` não usa `-v`; ele preserva os volumes de modelos e dados.

## Alternar rota

- **Direta:** instancie `OllamaAdapter(OLLAMA_BASE_URL, semaphore=...)` e use a tag local de `OLLAMA_MODEL_CODING` ou `OLLAMA_MODEL_CHAT`.
- **Proxy:** após subir e validar o perfil, instancie `LiteLLMGatewayAdapter` com `LITELLM_BASE_URL`, a chave obtida localmente e o alias configurado (`coding`, `chat` ou `judge`).
- Registre a rota, modelo resolvido e digest em cada execução. Não reutilize alias do proxy como identidade do modelo.
- Para voltar a direct, selecione `OllamaAdapter` explicitamente e pare LiteLLM. Não altere prompts nem releases ativos ao trocar a rota.

## Diagnóstico

| Sintoma | Verificação e ação |
|---|---|
| `HTTP_401` / `AUTH` | Confirme `LITELLM_ENABLED=true` e a chave local com formato válido; confira se o serviço recebeu o mesmo valor. Nunca inclua o valor em saída de terminal ou chamado de suporte. |
| `MODEL_MISSING` | Compare alias em `infra/litellm/config.example.yaml` com `/v1/models` e as tags retornadas por `OLLAMA_BASE_URL/api/tags`; instale o modelo por processo operacional autorizado. |
| OOM / erro CUDA | Pare execuções concorrentes, mantenha `OLLAMA_NUM_PARALLEL=1`, reduza contexto/orçamento de saída e confirme VRAM com `scripts/hardware_probe.py`. Não aumente a concorrência como recuperação. |
| Latência alta | Capture p50/p95 em pares direct/proxy com o mesmo fixture, modelo e orçamento usando `scripts/compare_gateway.py`; confirme carga e tempos de fila. Amostras pequenas não determinam vencedor. |
| Timeout ou gateway offline | Confira `docker compose ... ps litellm` e logs sanitizados. A rota proxy deve falhar de forma visível; escolha direct explicitamente para continuar. |
| Configuração quebrada após upgrade | Pare LiteLLM, restaure o digest/configuração anteriormente fixados e repita validação sintática, dry-run e smoke local antes de reabrir o perfil. |

## Prova de independência do modo direct

Com LiteLLM parado, execute o smoke local do adapter Ollama e confirme uma resposta não vazia. O fluxo direto não consulta a porta 4000. Este modo não promove modelo, prompt ou resultado de benchmark.
