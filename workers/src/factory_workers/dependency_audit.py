"""One-shot dependency audit that records proposals without editing manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scripts.propose_dependency_upgrade import evaluate_remediation, propose


@dataclass(frozen=True)
class DependencyAuditWorker:
    artifact_root: Path

    def run_once(
        self,
        *,
        evidence_path: Path,
        before_manifest: Path,
        candidate_manifest: Path,
        output_path: Path,
    ) -> dict:
        root = self.artifact_root.resolve()
        output = output_path.resolve()
        if not output.is_relative_to(root):
            raise ValueError("DEPENDENCY_AUDIT_OUTPUT_OUTSIDE_ARTIFACT_ROOT")
        evidence_before = evidence_path.read_bytes()
        baseline_before = before_manifest.read_bytes()
        candidate_before = candidate_manifest.read_bytes()
        proposal = propose(evidence_path)
        remediation = evaluate_remediation(evidence_path, before_manifest, candidate_manifest)
        if (
            evidence_path.read_bytes() != evidence_before
            or before_manifest.read_bytes() != baseline_before
            or candidate_manifest.read_bytes() != candidate_before
        ):
            raise ValueError("DEPENDENCY_AUDIT_INPUT_MUTATED")
        report = {
            "schema": 1,
            "kind": "dependency-audit-run",
            "proposal": proposal,
            "remediation_evidence": remediation,
            "status": "pending_approval",
            "lockfiles_modified": False,
            "publication_authorized": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report
