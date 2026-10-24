.PHONY: doctor preflight api-test web-test web-build local

doctor:
	python scripts/doctor.py

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
