#!/usr/bin/env python3
"""Freeze the assisted seven-node tag plan against the reviewed v2 contract."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from task_engine.models import Task  # noqa: E402

from scripts.run_next_five import BASE, approve_plan, bundle, context, request, save  # noqa: E402

DEMAND = "5719882c-1e1d-49b9-a0d4-1f965762489e"
TASKS = json.loads(open(".runtime/artifacts/fac-131-134/fac131-delegated-dag.json").read())[
    "task_plan"
]
CORE = [
    "apps/customer-registry/api/src/customer_registry/models/user.py",
    "apps/customer-registry/api/src/customer_registry/models/__init__.py",
    "apps/customer-registry/api/alembic/versions/0002_add_optional_user_phone.py",
    "apps/customer-registry/api/alembic/versions/0003_add_shared_tags.py",
    "apps/customer-registry/api/alembic/versions/0004_expand_tag_normalization.py",
]
API = [
    "apps/customer-registry/api/src/customer_registry/main.py",
    "apps/customer-registry/api/src/customer_registry/repositories/users.py",
    "apps/customer-registry/api/src/customer_registry/database.py",
]
WEB = [
    "apps/customer-registry/web/src/App.tsx",
    "apps/customer-registry/web/src/api.ts",
    "apps/customer-registry/web/src/styles.css",
]
INTEGRATED = CORE + API + WEB + ["apps/customer-registry/web/e2e/users.spec.ts"]


def read_files(paths):
    return {path: open(path, encoding="utf-8").read() for path in paths}


with context() as (_, sessions, client):
    mapping = {}
    key_to_id = {item["key"]: item["task_id"] for item in TASKS}
    dependency_keys = {
        "TAG-DB": [],
        "TAG-BE": ["TAG-DB"],
        "TAG-FE": [],
        "TAG-INTEGRATION": ["TAG-BE", "TAG-FE"],
        "TAG-QA": ["TAG-INTEGRATION"],
        "TAG-DOCS": ["TAG-DB", "TAG-BE", "TAG-FE"],
        "TAG-REVIEW": ["TAG-QA", "TAG-DOCS"],
    }
    for item in TASKS:
        key = item["key"]
        tid = item["task_id"]
        with sessions() as session:
            task = session.get(Task, tid)
            # Existing DB/BE/FE patches are tied to their current SHA and are preserved.
            if key in {"TAG-DB", "TAG-BE", "TAG-FE"}:
                spec = dict(task.execution_spec)
                scopes = list(task.path_scopes)
                if key == "TAG-BE":
                    spec["sandbox_pids_limit"] = 256
                    spec["context_paths"] = CORE + API
                    files = read_files(CORE + API)
                    spec.update(bundle("next-five-tag-be-v3", files))
                    scopes = CORE + API
                if key == "TAG-FE":
                    spec["sandbox_pids_limit"] = 256
            elif key == "TAG-INTEGRATION":
                scopes = INTEGRATED
                files = read_files(INTEGRATED)
                spec = {
                    "base_git_sha": BASE,
                    "profile": "registry-fullstack",
                    "fixture_path": "apps/customer-registry/api/tests",
                    "context_paths": [
                        "apps/customer-registry/api/src/customer_registry/models/user.py"
                    ],
                    "max_attempts": 2,
                    "sandbox_pids_limit": 256,
                    **bundle("next-five-tag-integration-v3", files),
                }
            elif key == "TAG-QA":
                scopes = [
                    "apps/customer-registry/api/tests/test_users.py",
                    "apps/customer-registry/web/e2e/users.spec.ts",
                ]
                spec = {
                    "base_git_sha": BASE,
                    "profile": "registry-fullstack",
                    "fixture_path": "apps/customer-registry/api/tests",
                    "context_paths": [
                        "apps/customer-registry/api/src/customer_registry/models/user.py"
                    ],
                    "max_attempts": 2,
                    "sandbox_pids_limit": 256,
                    **bundle("next-five-tag-qa-v3", read_files(scopes)),
                }
            elif key == "TAG-DOCS":
                scopes = ["docs/registry-domain.md", "specs/demands/feature-tags-e2e/acceptance.md"]
                spec = {
                    "base_git_sha": BASE,
                    "profile": "registry-backend",
                    "fixture_path": "apps/customer-registry/api/tests",
                    "context_paths": [
                        "apps/customer-registry/api/src/customer_registry/models/user.py"
                    ],
                    "max_attempts": 2,
                    "sandbox_pids_limit": 256,
                    **bundle("next-five-tag-docs-v3", read_files(scopes)),
                }
            else:
                scopes = ["docs/feature-tags-review.md"]
                spec = {
                    "base_git_sha": BASE,
                    "profile": "registry-backend",
                    "fixture_path": "apps/customer-registry/api/tests",
                    "context_paths": [
                        "apps/customer-registry/api/src/customer_registry/models/user.py"
                    ],
                    "max_attempts": 1,
                    "sandbox_pids_limit": 256,
                    **bundle(
                        "next-five-tag-review-v3",
                        {
                            "docs/feature-tags-review.md": (
                                "# Revisão da entrega de etiquetas\n\n"
                                "Checklist de revisão independente. A aprovação efetiva exige "
                                "inspeção do diff integrado e leitura dos receipts dos gates "
                                "no SHA final.\n"
                            )
                        },
                    ),
                }
            dep_ids = [key_to_id[value] for value in dependency_keys[key]]
            if key not in {"TAG-DB", "TAG-BE", "TAG-FE"}:
                payload = {
                    "expected_version": task.state_version,
                    "title": task.title,
                    "owner_role": task.owner_role,
                    "priority": 100
                    if key == "TAG-DB"
                    else 95
                    if key == "TAG-FE"
                    else 85
                    if key == "TAG-BE"
                    else task.priority,
                    "path_scopes": scopes,
                    "acceptance": task.acceptance,
                    "risk": task.risk,
                    "dependencies": dep_ids,
                    "execution_spec": spec,
                }
            else:
                payload = {
                    "expected_version": task.state_version,
                    "title": task.title,
                    "owner_role": task.owner_role,
                    "priority": 100 if key == "TAG-DB" else 95 if key == "TAG-FE" else 85,
                    "path_scopes": scopes,
                    "acceptance": task.acceptance,
                    "dependencies": dep_ids,
                    "execution_spec": spec,
                    "risk": task.risk,
                }
            old = dict(task.execution_spec or {})
            # Update API nodes; scope and hash changes require a fresh demand-plan grant.
        if key not in {"TAG-DB", "TAG-BE", "TAG-FE"} or old != spec or scopes != task.path_scopes:
            result = request(client, "PUT", f"/tasks/{tid}/plan", payload)
            mapping[key] = {
                "task_id": tid,
                "plan_revision": result["state_version"],
                "paths": scopes,
                "spec": spec,
                "dependencies": payload["dependencies"],
            }
        else:
            mapping[key] = {
                "task_id": tid,
                "plan_revision": task.state_version,
                "paths": scopes,
                "spec": spec,
                "dependencies": payload["dependencies"],
            }
    grant = approve_plan(client, DEMAND)
    record = {
        "status": "plan_approved",
        "provenance": "Codex-assisted delegated execution plan; no human signature claimed",
        "human_approval_claimed": False,
        "baseline_sha": BASE,
        "revision_id": "994f041d-736b-4d8c-a08d-0de8ea2391e2",
        "task_plan_hash_bound": True,
        "approval_id": grant["id"],
        "nodes": mapping,
    }
    save("tags-plan-final.json", record)
    print(
        json.dumps({"status": record["status"], "nodes": len(mapping), "approval_id": grant["id"]})
    )
