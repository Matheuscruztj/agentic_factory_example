# Build from the locally verified quality image; execute only by its resulting image ID.
ARG BASE_IMAGE=agentic-factory-quality:local
FROM ${BASE_IMAGE}
USER root
RUN cp -a /workspace/.venv /opt/runner-venv \
    && uv pip install --python /opt/runner-venv/bin/python pytest==9.0.3
COPY node /usr/local/bin/node
COPY node_modules /opt/frontend/node_modules
COPY browsers /opt/browsers
COPY frontend-gate /opt/runner/frontend-gate
RUN node /opt/frontend/node_modules/playwright-core/cli.js install-deps chromium \
    && chmod 0755 /opt/runner/frontend-gate \
    && chmod -R a+rX /opt/browsers
ENV PATH="/opt/runner-venv/bin:/usr/local/bin:/usr/bin:/bin" \
    PLAYWRIGHT_BROWSERS_PATH=/opt/browsers \
    PYTHONDONTWRITEBYTECODE=1 UV_OFFLINE=true
USER 1000:1000
