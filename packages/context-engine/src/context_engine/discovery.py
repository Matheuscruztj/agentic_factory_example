"""Evidence-grounded demand discovery without inventing repository facts."""

from __future__ import annotations

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

    def as_dict(self) -> dict:
        return {
            "summary": self.summary,
            "evidence": [{**asdict(item), "status": item.status.value} for item in self.evidence],
            "questions": list(self.questions),
        }


def discover_demand(
    text: str, *, repository_files: dict[str, str] | None = None, sha: str | None = None
) -> Discovery:
    """Match mentioned paths against an explicit SHA-scoped file inventory."""
    body = text.strip()
    if not body:
        return Discovery("", (Evidence("Demand text is empty", EvidenceStatus.UNKNOWN),), ())
    files = repository_files or {}
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
        elif mention in files:
            evidence.append(
                Evidence(f"Path exists: {mention}", EvidenceStatus.VERIFIED, mention, sha)
            )
        else:
            evidence.append(
                Evidence(
                    f"Path not found in supplied inventory: {mention}",
                    EvidenceStatus.UNKNOWN,
                    mention,
                    sha,
                )
            )
    if not evidence:
        evidence.append(
            Evidence(
                "No repository claim was verified from a supplied inventory", EvidenceStatus.UNKNOWN
            )
        )
    questions = ()
    if any(word in body.lower() for word in ("better", "fast", "secure", "correct")):
        questions = ("What observable outcome should define acceptance for this request?",)
    return Discovery(body[:2000], tuple(evidence), questions)
