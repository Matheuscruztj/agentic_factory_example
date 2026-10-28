#!/usr/bin/env python3
"""Issue local-AI acceptance receipts bound to verified task evidence."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages/eval-engine/src"))
from eval_engine.judge import (  # noqa: E402
    JudgeError,
    OllamaJudge,
    build_acceptance_prompt,
)


def canonical_json(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def get_or_create_receipt_key(root: Path) -> bytes:
    path = root / ".runtime/artifacts/uat/ai-acceptance.key"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError("AI_ACCEPTANCE_KEY_SYMLINK")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "wb") as stream:
            stream.write(secrets.token_bytes(32))
    if path.stat().st_mode & 0o077:
        raise ValueError("AI_ACCEPTANCE_KEY_PERMISSIONS")
    key = path.read_bytes()
    if len(key) < 32:
        raise ValueError("AI_ACCEPTANCE_KEY_INVALID")
    return key


def seal_receipt(receipt: dict, key: bytes) -> dict:
    if not isinstance(receipt, dict) or "receipt_hmac" in receipt or len(key) < 32:
        raise ValueError("AI_ACCEPTANCE_RECEIPT_INVALID")
    return {
        **receipt,
        "receipt_hmac": hmac.new(key, canonical_json(receipt), hashlib.sha256).hexdigest(),
    }


def verify_receipt_hmac(receipt: dict, key: bytes) -> bool:
    signature = receipt.get("receipt_hmac")
    if not isinstance(signature, str) or len(signature) != 64 or len(key) < 32:
        return False
    unsigned = {name: value for name, value in receipt.items() if name != "receipt_hmac"}
    expected = hmac.new(key, canonical_json(unsigned), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def _safe_runtime_artifact(root: Path, relative: str) -> tuple[Path, bytes]:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("AI_EVIDENCE_PATH_INVALID")
    candidate = root / relative
    if (
        any(part.casefold() in {"private", "secrets", "credentials"} for part in candidate.parts)
        or candidate.name.casefold().startswith(".env")
        or candidate.suffix.casefold() in {".key", ".pem", ".p12", ".pfx", ".env"}
    ):
        raise ValueError("AI_EVIDENCE_SECRET_PATH_FORBIDDEN")
    resolved = candidate.resolve(strict=True)
    runtime = (root / ".runtime").resolve(strict=True)
    if not resolved.is_relative_to(runtime) or candidate.is_symlink() or not resolved.is_file():
        raise ValueError("AI_EVIDENCE_PATH_INVALID")
    if any(part.is_symlink() for part in candidate.parents if part != root.parent):
        raise ValueError("AI_EVIDENCE_PATH_INVALID")
    content = resolved.read_bytes()
    if len(content) > 1_000_000:
        raise ValueError("AI_EVIDENCE_TOO_LARGE")
    return resolved, content


def _model_digest(base_url: str, model: str) -> str:
    response = httpx.get(base_url.rstrip("/") + "/api/tags", timeout=10, trust_env=False)
    response.raise_for_status()
    payload = response.json()
    models = payload.get("models", []) if isinstance(payload, dict) else []
    matches = [item for item in models if isinstance(item, dict) and item.get("name") == model]
    if len(matches) != 1 or not isinstance(matches[0].get("digest"), str):
        raise ValueError("AI_REVIEW_MODEL_DIGEST_UNAVAILABLE")
    digest = matches[0]["digest"]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("AI_REVIEW_MODEL_DIGEST_INVALID")
    return digest


def review_activity(
    *,
    activity_id: str,
    manifest_path: Path,
    root: Path = ROOT,
    judge_model: str,
    executor_model: str,
    base_url: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    """Review one implemented activity against physical artifacts and passed gates."""
    if not re.fullmatch(r"(?:FAC-\d{3}|LLMG-T\d{2})", activity_id):
        raise ValueError("AI_ACTIVITY_ID_INVALID")
    root = root.resolve(strict=True)
    backlog_path = root / "specs/implementation-backlog.json"
    raw_backlog = backlog_path.read_bytes()
    backlog_sha = hashlib.sha256(raw_backlog).hexdigest()
    backlog = json.loads(raw_backlog)
    tasks = [task for task in backlog.get("tasks", []) if task.get("id") == activity_id]
    if len(tasks) != 1:
        raise ValueError("AI_ACTIVITY_NOT_FOUND")
    task = tasks[0]
    if task.get("status") not in {"in_progress", "done"}:
        raise ValueError("AI_ACTIVITY_NOT_STARTED")
    dependencies = task.get("depends_on", [])
    task_by_id = {
        item.get("id"): item
        for item in backlog.get("tasks", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if not isinstance(dependencies, list) or any(
        not isinstance(dependency, str)
        or dependency not in task_by_id
        or task_by_id[dependency].get("status") != "done"
        for dependency in dependencies
    ):
        raise ValueError("AI_ACTIVITY_DEPENDENCIES_OPEN")
    if task.get("remaining_work"):
        raise ValueError("AI_ACTIVITY_HAS_REMAINING_WORK")
    if not isinstance(task.get("acceptance"), str) or not task["acceptance"].strip():
        raise ValueError("AI_ACTIVITY_ACCEPTANCE_MISSING")
    definition = {
        key: task.get(key) for key in ("id", "title", "acceptance", "paths", "depends_on", "risk")
    }
    definition_hash = hashlib.sha256(canonical_json(definition)).hexdigest()

    manifest_file = manifest_path if manifest_path.is_absolute() else root / manifest_path
    manifest_resolved = manifest_file.resolve(strict=True)
    runtime = (root / ".runtime").resolve(strict=True)
    if not manifest_resolved.is_relative_to(runtime) or manifest_file.is_symlink():
        raise ValueError("AI_EVIDENCE_MANIFEST_PATH_INVALID")
    manifest_raw = manifest_resolved.read_bytes()
    manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
    manifest = json.loads(manifest_raw)
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != 1
        or manifest.get("scope") != "activity"
        or manifest.get("activity_id") != activity_id
        or manifest.get("backlog_sha256") != backlog_sha
        or not isinstance(manifest.get("implementation_summary"), str)
        or not manifest["implementation_summary"].strip()
    ):
        raise ValueError("AI_EVIDENCE_MANIFEST_INVALID")
    artifacts = manifest.get("artifacts")
    gates = manifest.get("gates")
    if not isinstance(artifacts, list) or not artifacts or not isinstance(gates, list) or not gates:
        raise ValueError("AI_EVIDENCE_AND_GATES_REQUIRED")
    evidence: dict[str, str] = {}
    artifact_hashes = {}
    for item in artifacts:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("AI_EVIDENCE_ARTIFACT_INVALID")
        artifact_path, content = _safe_runtime_artifact(root, item["path"])
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != item.get("sha256"):
            raise ValueError("AI_EVIDENCE_ARTIFACT_HASH_MISMATCH")
        artifact_hashes[item["path"]] = actual_hash
        evidence[item["path"]] = (
            f"sha256={actual_hash}\n" + content.decode("utf-8", errors="replace")[:12_000]
        )
    for gate in gates:
        if (
            not isinstance(gate, dict)
            or gate.get("activity_id") != activity_id
            or gate.get("status") != "pass"
            or gate.get("artifact") not in artifact_hashes
            or gate.get("artifact_sha256") != artifact_hashes[gate["artifact"]]
        ):
            raise ValueError("AI_ACCEPTANCE_GATE_INVALID")
    gate_evidence = {
        f"gate:{index}": json.dumps(gate, ensure_ascii=False, sort_keys=True)
        for index, gate in enumerate(gates, start=1)
    }
    evidence.update(gate_evidence)
    answer = json.dumps(
        {
            "activity": definition,
            "implementation_summary": manifest["implementation_summary"],
            "required_checks": [gate["name"] for gate in gates],
            "claim": "The component meets its recorded acceptance criteria.",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    rubric = {
        "decision_order": [
            "Any failed/missing gate or hash mismatch means fail or uncertain.",
            "Approve only when every criterion is directly supported by cited evidence.",
            "Do not treat a related downstream integration as proof of this component.",
            "Reject claims unsupported by the cited files or test output.",
        ],
        "minimum_confidence_for_approval": 0.8,
    }
    prompt = build_acceptance_prompt(
        executor_model=executor_model, answer=answer, evidence=evidence, rubric=rubric
    )
    judge = OllamaJudge(base_url=base_url, model=judge_model)
    verdict = judge.accept(
        executor_model=executor_model, answer=answer, evidence=evidence, rubric=rubric
    )
    if verdict.prompt_sha256 != hashlib.sha256(prompt.encode()).hexdigest():
        raise ValueError("AI_REVIEW_PROMPT_HASH_MISMATCH")
    reviewer_digest = _model_digest(base_url, judge_model)
    review_identity = f"{activity_id}:{manifest_sha}:{verdict.response_sha256}"
    review_id = hashlib.sha256(review_identity.encode()).hexdigest()[:20]
    review_dir = root / ".runtime/artifacts/uat/activities" / activity_id
    review_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    prompt_path = review_dir / f"{review_id}.prompt.json"
    response_path = review_dir / f"{review_id}.response.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    response_path.write_text(verdict.raw_response, encoding="utf-8")
    receipt = {
        "schema": 1,
        "review_id": review_id,
        "activity_id": activity_id,
        "activity_definition_sha256": definition_hash,
        "backlog_sha256": backlog_sha,
        "evidence_manifest": manifest_resolved.relative_to(root).as_posix(),
        "evidence_manifest_sha256": manifest_sha,
        "reviewer_type": "local_ollama",
        "review_protocol": "binary_activity_acceptance_v1",
        "reviewer_model": judge_model,
        "reviewer_digest": reviewer_digest,
        "executor_model": executor_model,
        "reviewed_at": datetime.now(UTC).isoformat(),
        "decision": (
            "approve"
            if verdict.verdict == "pass"
            and verdict.confidence >= 0.8
            and not verdict.human_review_required
            else "reject"
            if verdict.verdict == "fail"
            else "uncertain"
        ),
        "verdict": verdict.verdict,
        "score": None,
        "confidence": verdict.confidence,
        "rationale": verdict.rationale,
        "evidence_refs": list(verdict.evidence_refs),
        "gates": gates,
        "artifacts": artifact_hashes,
        "prompt": prompt_path.relative_to(root).as_posix(),
        "prompt_sha256": verdict.prompt_sha256,
        "response": response_path.relative_to(root).as_posix(),
        "response_sha256": verdict.response_sha256,
        "source_tree_sha256": manifest.get("source_tree_sha256"),
    }
    sealed = seal_receipt(receipt, get_or_create_receipt_key(root))
    receipt_path = review_dir / f"{review_id}.receipt.json"
    receipt_path.write_text(json.dumps(sealed, ensure_ascii=False, indent=2) + "\n")
    receipt_path.chmod(0o600)
    return sealed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--activity", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--judge-model")
    parser.add_argument("--executor-model")
    parser.add_argument("--ollama-url")
    args = parser.parse_args()
    from scripts.validate_env import read_env

    config = read_env(ROOT / ".env") if (ROOT / ".env").is_file() else {}
    judge_model = (
        args.judge_model
        or config.get("EVAL_JUDGE_MODEL")
        or config.get("OLLAMA_MODEL_JUDGE", "qwen3:4b")
    )
    executor_model = args.executor_model or config.get("OLLAMA_MODEL_CODING", "qwen2.5-coder:7b")
    base_url = args.ollama_url or config.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    try:
        receipt = review_activity(
            activity_id=args.activity,
            manifest_path=args.manifest,
            judge_model=judge_model,
            executor_model=executor_model,
            base_url=base_url,
        )
    except (OSError, ValueError, httpx.HTTPError, JudgeError) as exc:
        code = str(exc) or type(exc).__name__
        print(json.dumps({"status": "error", "code": code}, separators=(",", ":")))
        return 2
    print(
        json.dumps(
            {
                "activity_id": receipt["activity_id"],
                "decision": receipt["decision"],
                "verdict": receipt["verdict"],
                "reviewer_model": receipt["reviewer_model"],
                "confidence": receipt["confidence"],
                "receipt": receipt["review_id"],
            },
            separators=(",", ":"),
        )
    )
    return 0 if receipt["decision"] == "approve" else 1 if receipt["decision"] == "reject" else 2


if __name__ == "__main__":
    raise SystemExit(main())
