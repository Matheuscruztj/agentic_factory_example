#!/usr/bin/env python3
"""Build a scorecard that fails closed until independent local-AI acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.ai_acceptance import verify_receipt_hmac  # noqa: E402


def _inside(root: Path, path: Path, folder: Path) -> Path:
    resolved = path.resolve(strict=True)
    allowed = folder.resolve(strict=True)
    ancestors = [path, *path.parents]
    if (
        resolved == allowed
        or allowed not in resolved.parents
        or any(item.is_symlink() for item in ancestors if item != root.parent)
    ):
        raise ValueError("UAT_ARTIFACT_PATH_INVALID")
    return resolved


def _verify_approval(candidate: dict, backlog_sha: str, root: Path) -> bool:
    required = (
        "reviewer_id",
        "signed_at",
        "decision",
        "scope",
        "signature_file",
        "evidence_manifest",
        "evidence_manifest_sha256",
    )
    if not all(isinstance(candidate.get(key), str) and candidate[key].strip() for key in required):
        return False
    if candidate["decision"] != "approve" or candidate["scope"] != "all-required-activities":
        return False
    try:
        signed_at = datetime.fromisoformat(candidate["signed_at"].replace("Z", "+00:00"))
        if signed_at.tzinfo is None or signed_at > datetime.now(UTC):
            return False
        uat_dir = root / ".runtime/artifacts/uat"
        manifest_path = _inside(root, root / candidate["evidence_manifest"], uat_dir)
        signature_path = _inside(root, root / candidate["signature_file"], uat_dir)
        manifest_bytes = manifest_path.read_bytes()
        manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
        if manifest_sha != candidate["evidence_manifest_sha256"]:
            return False
        manifest = json.loads(manifest_bytes)
        if not isinstance(manifest, dict):
            return False
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return False
        run_id, task_id = manifest.get("run_id"), manifest.get("task_id")
        git_sha, tree_sha = manifest.get("git_sha"), manifest.get("tree_sha")
        if (
            not isinstance(run_id, str)
            or not run_id
            or not isinstance(task_id, str)
            or not task_id
            or not isinstance(git_sha, str)
            or len(git_sha) not in {40, 64}
            or not isinstance(tree_sha, str)
            or len(tree_sha) not in {40, 64}
        ):
            return False
        artifact_hashes = {}
        for item in artifacts:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                return False
            artifact_path = root / item["path"]
            resolved = _inside(root, artifact_path, root / ".runtime")
            actual_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if actual_hash != item.get("sha256"):
                return False
            artifact_hashes[item["path"]] = actual_hash
        gates = manifest.get("gates")
        if not isinstance(gates, list) or not gates:
            return False
        for gate in gates:
            if (
                not isinstance(gate, dict)
                or gate.get("status") != "pass"
                or gate.get("run_id") != run_id
                or gate.get("task_id") != task_id
                or gate.get("git_sha") != git_sha
                or gate.get("tree_sha") != tree_sha
                or artifact_hashes.get(gate.get("artifact")) != gate.get("artifact_sha256")
            ):
                return False
        independent_review = manifest.get("review")
        if (
            not isinstance(independent_review, dict)
            or independent_review.get("decision") != "approved"
            or independent_review.get("git_sha") != git_sha
            or not isinstance(independent_review.get("reviewer_id"), str)
            or independent_review["reviewer_id"] == candidate["reviewer_id"]
        ):
            return False
        if candidate.get("backlog_sha256") != backlog_sha:
            return False
        allowed_signers = uat_dir / "allowed_signers"
        if allowed_signers.is_symlink() or not allowed_signers.is_file():
            return False
        message = {
            "reviewer_id": candidate["reviewer_id"],
            "signed_at": candidate["signed_at"],
            "decision": candidate["decision"],
            "scope": candidate["scope"],
            "backlog_sha256": candidate["backlog_sha256"],
            "evidence_manifest_sha256": manifest_sha,
        }
        result = subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "verify",
                "-f",
                str(allowed_signers),
                "-I",
                candidate["reviewer_id"],
                "-n",
                "agentic-factory-uat",
                "-s",
                str(signature_path),
            ],
            input=json.dumps(message, sort_keys=True, separators=(",", ":")).encode(),
            capture_output=True,
            check=False,
            timeout=10,
        )
        return result.returncode == 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ):
        return False


def _verify_ai_acceptance(
    candidate: dict,
    backlog_sha: str,
    pending_required: list[str],
    root: Path,
    required_activity_ids: set[str] | None = None,
) -> bool:
    required = (
        "reviewer_type",
        "reviewer_model",
        "reviewer_digest",
        "executor_model",
        "reviewed_at",
        "decision",
        "verdict",
        "confidence",
        "scope",
        "prompt",
        "prompt_sha256",
        "response",
        "response_sha256",
        "evidence_manifest",
        "evidence_manifest_sha256",
        "backlog_sha256",
        "evidence_refs",
        "receipt_hmac",
    )
    if not all(key in candidate for key in required):
        return False
    if (
        candidate.get("reviewer_type") != "local_ollama"
        or candidate.get("decision") != "approve"
        or candidate.get("verdict") != "pass"
        or candidate.get("scope") != "all-required-activities"
        or candidate.get("reviewer_model") == candidate.get("executor_model")
        or candidate.get("backlog_sha256") != backlog_sha
        or pending_required
        or not isinstance(candidate.get("reviewer_digest"), str)
        or len(candidate["reviewer_digest"]) != 64
        or any(char not in "0123456789abcdef" for char in candidate["reviewer_digest"])
        or type(candidate.get("confidence")) not in (int, float)
        or candidate["confidence"] < 0.8
        or not isinstance(candidate.get("evidence_refs"), list)
        or not candidate["evidence_refs"]
    ):
        return False
    try:
        reviewed_at = datetime.fromisoformat(candidate["reviewed_at"].replace("Z", "+00:00"))
        if reviewed_at.tzinfo is None or reviewed_at > datetime.now(UTC):
            return False
        uat_dir = root / ".runtime/artifacts/uat"
        manifest_path = _inside(root, root / candidate["evidence_manifest"], uat_dir)
        prompt_path = _inside(root, root / candidate["prompt"], uat_dir)
        response_path = _inside(root, root / candidate["response"], uat_dir)
        manifest_bytes = manifest_path.read_bytes()
        prompt_bytes = prompt_path.read_bytes()
        response_bytes = response_path.read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != candidate["evidence_manifest_sha256"]:
            return False
        if hashlib.sha256(prompt_bytes).hexdigest() != candidate["prompt_sha256"]:
            return False
        if hashlib.sha256(response_bytes).hexdigest() != candidate["response_sha256"]:
            return False
        manifest = json.loads(manifest_bytes)
        if (
            not isinstance(manifest, dict)
            or manifest.get("scope") != candidate["scope"]
            or manifest.get("backlog_sha256") != backlog_sha
        ):
            return False
        key_path = uat_dir / "ai-acceptance.key"
        if key_path.is_symlink() or not key_path.is_file() or key_path.stat().st_mode & 0o077:
            return False
        key = key_path.read_bytes()
        if len(key) < 32:
            return False
        if not verify_receipt_hmac(candidate, key):
            return False
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return False
        artifact_hashes = {}
        for item in artifacts:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                return False
            artifact_path = _inside(root, root / item["path"], root / ".runtime")
            actual_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            if actual_hash != item.get("sha256"):
                return False
            artifact_hashes[item["path"]] = actual_hash
        activities = manifest.get("activities")
        if not isinstance(activities, list) or not activities:
            return False
        activity_ids = set()
        for activity in activities:
            if (
                not isinstance(activity, dict)
                or activity.get("status") != "done"
                or not isinstance(activity.get("id"), str)
            ):
                return False
            activity_ids.add(activity["id"])
            refs = activity.get("evidence_refs")
            if (
                not isinstance(refs, list)
                or not refs
                or any(ref not in artifact_hashes for ref in refs)
            ):
                return False
        expected_ids = set(manifest.get("required_activity_ids", []))
        if not expected_ids or activity_ids != expected_ids:
            return False
        if required_activity_ids is not None and activity_ids != required_activity_ids:
            return False
        gates = manifest.get("gates")
        if (
            not isinstance(gates, list)
            or not gates
            or any(
                not isinstance(gate, dict)
                or gate.get("status") != "pass"
                or gate.get("artifact") not in artifact_hashes
                for gate in gates
            )
        ):
            return False
        if set(candidate["evidence_refs"]) != set(artifact_hashes):
            return False
        response = json.loads(response_bytes)
        if (
            not isinstance(response, dict)
            or response.get("verdict") != "pass"
            or response.get("decision") != "approve"
            or response.get("confidence") != candidate["confidence"]
            or response.get("reviewer_model") != candidate["reviewer_model"]
        ):
            return False
        return True
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False


def build_report(backlog: Path, approval: Path | None, root: Path | None = None) -> dict:
    root = (root or Path.cwd()).resolve()
    raw = backlog.read_bytes()
    data = json.loads(raw)
    optional = {"optional_capability_expansion", "lite_llm_opt_in", "optional_llmg"}
    required_ids = {
        item["id"] for item in data["tasks"] if item.get("release_scope") not in optional
    }
    pending_required = [
        item["id"]
        for item in data["tasks"]
        if item["status"] != "done" and item.get("release_scope") not in optional
    ]
    ai_reviewer_record = None
    if approval and approval.is_file():
        try:
            candidate = json.loads(approval.read_text(encoding="utf-8"))
            if isinstance(candidate, dict) and _verify_ai_acceptance(
                candidate, hashlib.sha256(raw).hexdigest(), pending_required, root, required_ids
            ):
                ai_reviewer_record = candidate
        except (OSError, json.JSONDecodeError):
            ai_reviewer_record = None
    signed = ai_reviewer_record is not None
    return {
        "schema": 1,
        "status": "accepted_by_ai" if signed else "pending_ai_acceptance",
        "generated_at": datetime.now(UTC).isoformat(),
        "backlog_sha256": hashlib.sha256(raw).hexdigest(),
        "activities": {
            "total": len(data["tasks"]),
            "done": sum(item["status"] == "done" for item in data["tasks"]),
            "pending": [item["id"] for item in data["tasks"] if item["status"] != "done"],
            "pending_required": pending_required,
        },
        "ai_reviewer": ai_reviewer_record,
        "acceptance_claim": (
            "independent local AI reviewer accepted all required evidence"
            if signed
            else "no AI acceptance is claimed; required evidence or a valid AI receipt is missing"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--approval", type=Path, default=Path(".runtime/artifacts/uat/ai-approval.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path(".runtime/artifacts/uat/ai-scorecard.json")
    )
    args = parser.parse_args()
    result = build_report(Path("specs/implementation-backlog.json"), args.approval)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    rows = "\n".join(
        f"| {item['id']} | {item['status']} | {item['acceptance']} |"
        for item in json.loads(Path("specs/implementation-backlog.json").read_text())["tasks"]
    )
    approval_text = (
        "AI reviewer: "
        f"{result['ai_reviewer']['reviewer_model']} — {result['ai_reviewer']['decision']}"
        if result["ai_reviewer"]
        else "Nenhum reviewer de IA independente aprovou este relatório."
    )
    Path("docs/acceptance-report.md").write_text(
        "# Acceptance report (draft)\n\n"
        f"Status: **{result['status']}**. {result['acceptance_claim']}\n\n"
        f"Backlog SHA-256: `{result['backlog_sha256']}`. {approval_text}\n\n"
        "| Atividade | Estado | Critério registrado |\n|---|---|---|\n"
        f"{rows}\n\n"
        "Este scorecard usa o aceite técnico por IA autorizado pelo operador; ele não declara "
        "aceite humano nem autoriza efeitos externos com HITL próprio. `done` no backlog "
        "precisa estar ligado a evidências verificadas e ao receipt de IA.\n",
        encoding="utf-8",
    )
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
