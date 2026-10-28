FROM python:3.14-slim@sha256:35caba83af2fe6da9a5d922f9b0156f21d1246a48278c58a08bd253303ba42e8
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy UV_NO_PROGRESS=1 UV_PYTHON_DOWNLOADS=never
WORKDIR /workspace
RUN pip install --no-cache-dir uv==0.12.19
COPY . .
RUN uv sync --frozen --all-packages --no-default-groups --group api
ENV PATH="/workspace/.venv/bin:$PATH" \
    PYTHONPATH="/workspace:/workspace/apps/factory-api/src:/workspace/apps/customer-registry/api/src:/workspace/packages/shared-contracts/src:/workspace/packages/task-engine/src:/workspace/packages/context-engine/src:/workspace/packages/integrations/src:/workspace/packages/agent-runtime/src:/workspace/packages/eval-engine/src:/workspace/packages/observability/src"
USER 1000:1000
CMD ["python", "scripts/quality_target.py", "factory"]
