.PHONY: doctor doctor-factory doctor-agent preflight api-test web-test web-build local telegram-intake github-intake ai-up ai-status

doctor:
	uv run --frozen --all-packages --group api python scripts/doctor.py --profile registry

doctor-factory:
	uv run --frozen --all-packages --group api python scripts/doctor.py --profile factory

doctor-agent:
	uv run --frozen --all-packages --group api python scripts/doctor.py --profile agent

preflight:
	python scripts/validate_env.py --env .env --mode local --require core,postgres,redis

api-test:
	PYTHONPATH=apps/customer-registry/api/src pytest -q apps/customer-registry/api/tests

web-test:
	pnpm --dir apps/customer-registry/web test

web-build:
	pnpm --dir apps/customer-registry/web build

local:
	python scripts/local_boot.py

telegram-intake:
	uv run --frozen --all-packages --group api python scripts/telegram_intake_worker.py

telegram-outbox-once:
	uv run --frozen --all-packages --group api python scripts/telegram_outbox_worker.py --once

github-intake:
	uv run --frozen --all-packages --group api python scripts/github_intake_worker.py

ai-up:
	docker compose --env-file .env -f infra/compose/ai-services.yml up -d --build --wait

ai-status:
	docker compose --env-file .env -f infra/compose/ai-services.yml ps

.PHONY: quality quality-fast quality-full quality-up quality-down quality-security quality-dast telegram-outbox-once
QUALITY_PYTHON = uv run --frozen --all-packages --group api python

quality: quality-fast

quality-fast:
	$(QUALITY_PYTHON) scripts/quality_fast.py

quality-full:
	$(QUALITY_PYTHON) scripts/quality_full.py

quality-up:
	$(QUALITY_PYTHON) scripts/quality.py up
quality-down:
	$(QUALITY_PYTHON) scripts/quality.py down
quality-security:
	$(QUALITY_PYTHON) scripts/quality_security.py
quality-dast:
	$(QUALITY_PYTHON) scripts/quality_dast.py
