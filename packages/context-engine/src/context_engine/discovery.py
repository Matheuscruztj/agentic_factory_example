"""Evidence-grounded demand discovery without inventing repository facts."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import PurePosixPath


class EvidenceStatus(StrEnum):
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class Evidence:
    claim: str
    status: EvidenceStatus
    source: str | None = None
    sha: str | None = None


@dataclass(frozen=True, slots=True)
class Discovery:
    summary: str
    evidence: tuple[Evidence, ...]
    questions: tuple[str, ...]
    request_type: str = "unknown"
    impact: str = "unknown"

    def as_dict(self) -> dict:
        return {
            "summary": self.summary,
            "evidence": [{**asdict(item), "status": item.status.value} for item in self.evidence],
            "questions": list(self.questions),
            "request_type": self.request_type,
            "impact": self.impact,
        }


def discover_demand(
    text: str, *, repository_files: dict[str, str] | None = None, sha: str | None = None
) -> Discovery:
    """Match mentioned paths against an explicit SHA-scoped file inventory."""
    body = text.strip()
    if not body:
        return Discovery("", (Evidence("Demand text is empty", EvidenceStatus.UNKNOWN),), ())
    request_type = _classify_request(body)
    impact = _classify_impact(body)
    files = repository_files or {}
    pinned_sha = (
        sha
        if isinstance(sha, str) and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", sha)
        else None
    )
    mentions = sorted(
        {token.strip("`.,:;()[]{}") for token in body.split() if "/" in token and "." in token}
    )
    evidence: list[Evidence] = []
    for mention in mentions:
        path = PurePosixPath(mention)
        if path.is_absolute() or ".." in path.parts:
            evidence.append(
                Evidence(
                    f"Path mention {mention} is outside allowed repository scope",
                    EvidenceStatus.UNKNOWN,
                )
            )
        elif mention in files and pinned_sha:
            evidence.append(
                Evidence(
                    f"Path exists at pinned repository revision: {mention}",
                    EvidenceStatus.VERIFIED,
                    mention,
                    pinned_sha,
                )
            )
        elif mention in files:
            evidence.append(
                Evidence(
                    "Path exists in inventory, but no valid repository SHA was supplied: "
                    f"{mention}",
                    EvidenceStatus.UNKNOWN,
                    mention,
                )
            )
        else:
            evidence.append(
                Evidence(
                    f"Path not found in supplied inventory: {mention}",
                    EvidenceStatus.UNKNOWN,
                    mention,
                    pinned_sha,
                )
            )
    if not evidence:
        evidence.append(
            Evidence(
                "No repository claim was verified from a supplied inventory", EvidenceStatus.UNKNOWN
            )
        )
    lowered = body.casefold()
    ambiguous_terms = (
        "better", "fast", "secure", "correct", "melhor", "rápido", "rapido", "seguro", "certo"
    )
    question_list = []
    if request_type == "unknown":
        question_list.append("Should this request be a question, bug fix, feature, or change?")
    if any(word in lowered for word in ambiguous_terms):
        question_list.append("What observable outcome should define acceptance for this request?")
    if impact == "unknown" and request_type in {"feature", "change", "bug"}:
        question_list.append("Which users or data flows are affected?")
    evidence.extend(
        [
            Evidence(
                f"Request type inferred from wording: {request_type}",
                EvidenceStatus.INFERRED if request_type != "unknown" else EvidenceStatus.UNKNOWN,
            ),
            Evidence(
                f"Impact category inferred from wording: {impact}",
                EvidenceStatus.INFERRED if impact != "unknown" else EvidenceStatus.UNKNOWN,
            ),
        ]
    )
    return Discovery(body[:2000], tuple(evidence), tuple(question_list), request_type, impact)


def _classify_request(text: str) -> str:
    lowered = text.casefold()
    if re.search(r"\b(why|what|how|when|where|por que|o que|como|quando|onde)\b", lowered):
        return "question"
    if re.search(r"\b(fix|repair|bug|erro|falha|corrigir|corrija|consertar)\b", lowered):
        return "bug"
    if re.search(r"\b(add|create|implement|build|adicionar|criar|implementar|incluir)\b", lowered):
        return "feature"
    if re.search(r"\b(change|update|alter|modify|mudar|alterar|atualizar|editar)\b", lowered):
        return "change"
    return "unknown"


def _classify_impact(text: str) -> str:
    lowered = text.casefold()
    if re.search(
        r"\b(cpf|secret|token|password|senha|auth|autentica|security|segurança|pii)\b",
        lowered,
    ):
        return "security_or_sensitive_data"
    if re.search(r"\b(delete|remove|drop|apagar|excluir|remover|migration|migração)\b", lowered):
        return "data_or_schema"
    if re.search(r"\b(ui|ux|button|screen|interface|botão|tela)\b", lowered):
        return "user_interface"
    return "unknown"
