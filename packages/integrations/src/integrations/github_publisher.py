"""Fail-closed GitHub publication adapter requiring separate human approvals."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


class GitHubWriteTransport(Protocol):
    def branch_sha(self, repository: str, branch: str) -> str | None: ...

    def find_pull_request(self, repository: str, branch: str, commit_sha: str) -> str | None: ...

    def push_branch(self, repository: str, branch: str, commit_sha: str) -> str: ...

    def create_pull_request(
        self, repository: str, branch: str, title: str, body: str
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class PublicationApproval:
    action: str
    repository: str
    subject_sha: str
    decision: str
    approver: str


def _approved(
    approval: PublicationApproval | None, *, action: str, repository: str, sha: str
) -> bool:
    return bool(
        approval
        and approval.action == action
        and approval.repository == repository
        and approval.subject_sha == sha
        and approval.decision == "approved"
        and approval.approver == "operator"
    )


def publish_pull_request(
    transport: GitHubWriteTransport,
    *,
    repository: str,
    allowed_repository: str,
    branch: str,
    commit_sha: str,
    title: str,
    evidence_body: str,
    push_approval: PublicationApproval | None,
    pr_approval: PublicationApproval | None,
    redact: Callable[[str], str],
) -> dict[str, str]:
    """Push and open a PR only after distinct approvals bound to repository and SHA."""
    if repository != allowed_repository or not repository or "/" not in repository:
        raise PermissionError("REPOSITORY_NOT_ALLOWED")
    if not branch.startswith("agent/") or branch.startswith("agent/../"):
        raise ValueError("INVALID_PUBLICATION_BRANCH")
    if len(commit_sha) != 40 or any(c not in "0123456789abcdef" for c in commit_sha):
        raise ValueError("INVALID_COMMIT_SHA")
    if not _approved(push_approval, action="push", repository=repository, sha=commit_sha):
        raise PermissionError("PUSH_APPROVAL_REQUIRED")
    if not _approved(pr_approval, action="create_pr", repository=repository, sha=commit_sha):
        raise PermissionError("PULL_REQUEST_APPROVAL_REQUIRED")
    safe_body = redact(evidence_body)
    if not safe_body or len(safe_body) > 20_000:
        raise ValueError("INVALID_REDACTED_EVIDENCE")
    # Reconcile remote state first: a retry after a crash must not repeat a completed push/PR.
    remote_sha = transport.branch_sha(repository, branch)
    if remote_sha != commit_sha:
        remote_sha = transport.push_branch(repository, branch, commit_sha)
    if remote_sha != commit_sha:
        raise RuntimeError("REMOTE_COMMIT_MISMATCH")
    existing_pr = transport.find_pull_request(repository, branch, commit_sha)
    if existing_pr:
        return {"commit_sha": remote_sha, "pull_request_url": existing_pr}
    url = transport.create_pull_request(repository, branch, title[:240], safe_body)
    return {"commit_sha": remote_sha, "pull_request_url": url}
