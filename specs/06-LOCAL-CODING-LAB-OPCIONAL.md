# Extensão opcional — Local Coding Lab / Ollama Benchmark

Este laboratório é **um add-on de benchmark**, não outro produto nem parte do caminho crítico P00–P13. Serve para medir se `qwen3:4b`, `qwen2.5-coder:7b`, `qwen3:8b` ou outras quantizações são adequadas à RTX 4060 Ti 8 GB + 64 GB RAM, comparando inferência pura, coding agent em IDE e OpenBot/Task Engine. Os modelos são hipóteses; os resultados precisam ser medidos.

## Escopo de implementação (após P09–P11)

- `packages/local-coding-lab/` (Python): client Ollama tipado, benchmark de throughput/latência, runner de tarefas de código e normalizador de métricas.
- `evals/local-coding-lab/`: conjuntos equivalentes a bugs, CRUD, migration, refatoração e correção de vulnerabilidade com gabaritos e tests privados.
- `scripts/bench_local_models.py`: seleção por `model, quantization, context, concurrency`, warmup e N repetições; registrar median, p95, load duration, prompt and output tokens, GPU/VRAM.
- `packages/local-coding-lab/adapters/`: Ollama API, IDE/Continue ou Aider via interface de execução reproduzível (quando suportada), OpenBot/LangGraph executor adapter; ambientes separados para cada candidato.
- `evals/local-coding-lab/results/`: artefatos de runs ignorados no Git e relatórios agregados com hashes/model/version.
- Quality: Ruff/mypy/pytest, Playwright quando apropriado, scanners; `pass@1`, task_success_rate, first_pass, rework, accepted tasks/hour e gasto elétrico estimado por intervalo de medição.
- Segurança: workspace isolado, sem acesso a segredos, sem rede para executar código gerado, sem automaticamente baixar modelos enormes sem autorização.

**Critério de aceite:** mesmos fixtures e budgets para todos os candidatos; no mínimo 3 runs/tarefa/modelo para comparação exploratória; guardar estatísticas, falhas e incerteza. Não comparar apenas tokens/s. O LLM Judge deve ser externo ao executor quando possível, calibrado com labels humanos e subordinado a checks objetivos. Não implantar novos modelos para produção por mudança automática de prompt.

O laboratório pode compartilhar OpenTelemetry, Phoenix e scripts JSON 0/1/2 da Factory; Phoenix desligado não interrompe benchmark nem invalida resultados. Não acrescentar 20 serviços novos para executar uma avaliação simples.
