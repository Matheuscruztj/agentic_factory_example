import asyncio
import hashlib
from types import SimpleNamespace

import pytest
from agent_runtime.ollama_adapter import OllamaError
from agent_runtime.review import (
    ReviewFinding,
    ReviewReport,
    conduct_independent_review,
    review_diff_with_local_model,
    validate_review_report,
)


def test_review_report_requires_independent_reviewer_and_cited_findings():
    report = ReviewReport(
        reviewer="reviewer",
        rubric_version="v1",
        base_sha="a" * 40,
        reviewed_sha="b" * 40,
        findings=(
            ReviewFinding("high", "src/app.py", 12, "REQ-1", "unsafe path join", "validate path"),
        ),
        evidence_refs=("diff:sha256:abc", "gate:pytest:artifact-1"),
    )
    assert report.decision == "request_changes"
    assert (
        validate_review_report(
            report,
            executor_id="implementer",
            required_evidence=("diff:sha256:abc", "gate:pytest:artifact-1"),
        )
        == []
    )
    assert "REVIEWER_MUST_BE_INDEPENDENT" in validate_review_report(
        report, executor_id="reviewer", required_evidence=("diff:sha256:abc",)
    )


def test_review_conductor_binds_review_to_diff_requirements_and_gate_artifacts():
    request_seen = []
    report = ReviewReport(
        reviewer="reviewer",
        rubric_version="reviewer-v1",
        base_sha="a" * 40,
        reviewed_sha="b" * 40,
        findings=(),
        evidence_refs=("diff:abc", "spec:REQ-1", "gate:pytest-1"),
    )
    result = conduct_independent_review(
        reviewer_id="reviewer",
        executor_id="backend",
        base_sha="a" * 40,
        reviewed_sha="b" * 40,
        diff_ref="diff:abc",
        requirement_refs=("spec:REQ-1",),
        gate_refs=("gate:pytest-1",),
        evaluate=lambda request: request_seen.append(request) or report,
    )
    assert result["decision"] == "approve"
    assert request_seen[0]["mode"] == "read_only_findings"


def test_local_model_review_is_read_only_and_records_model_and_prompt_provenance():
    class FakeAdapter:
        def __init__(self):
            self.request = None
            self.fail_schema = False
            self.formats = []

        async def chat(self, model, messages, *, format_schema, think, output_tokens):
            self.request = (model, messages, format_schema, think, output_tokens)
            self.formats.append(format_schema)
            if self.fail_schema and isinstance(format_schema, dict):
                raise OllamaError("OUTPUT_SCHEMA_INVALID")
            return SimpleNamespace(
                model=model,
                model_digest="sha256:model-digest",
                content=(
                    '{"findings":[{"severity":"high","path":"src/a.py","line":4,'
                    '"requirement":"REQ-1","evidence":"unvalidated input",'
                    '"recommendation":"validate input"}]}'
                ),
            )

    adapter = FakeAdapter()
    prompt = "Review only supplied evidence."
    refs = ("diff:sha256:abc", "requirement:rev-1", "gate:unit-run-1")
    report = asyncio.run(
        review_diff_with_local_model(
            adapter=adapter,
            model_tag="qwen3:4b",
            reviewer_id="reviewer",
            executor_id="implementer",
            rubric_version="reviewer-v1",
            prompt=prompt,
            base_sha="a" * 40,
            reviewed_sha="b" * 40,
            diff_text="diff --git a/src/a.py b/src/a.py\n+unsafe = input()",
            requirement_text="REQ-1 validates input",
            gate_summary="unit passed",
            evidence_refs=refs,
        )
    )
    assert report["decision"] == "request_changes"
    assert report["model_digest"] == "sha256:model-digest"
    assert report["prompt_hash"] == hashlib.sha256(prompt.encode()).hexdigest()
    assert report["evidence_refs"] == list(refs)
    assert adapter.request[0] == "qwen3:4b" and adapter.request[4] == 1800
    assert adapter.request[3] is False
    assert adapter.request[2]["additionalProperties"] is False
    adapter.fail_schema = True
    fallback = asyncio.run(
        review_diff_with_local_model(
            adapter=adapter,
            model_tag="qwen3:4b",
            reviewer_id="reviewer",
            executor_id="implementer",
            rubric_version="reviewer-v1",
            prompt=prompt,
            base_sha="a" * 40,
            reviewed_sha="b" * 40,
            diff_text="diff --git a/src/a.py b/src/a.py\n+unsafe = input()",
            requirement_text="REQ-1 validates input",
            gate_summary="unit passed",
            evidence_refs=refs,
        )
    )
    assert fallback["decision"] == "request_changes"
    assert adapter.formats[-1] == "json"


def test_local_model_review_rejects_executor_as_reviewer():
    with pytest.raises(PermissionError, match="REVIEWER_MUST_BE_INDEPENDENT"):
        asyncio.run(
            review_diff_with_local_model(
                adapter=object(),
                model_tag="local",
                reviewer_id="same",
                executor_id="same",
                rubric_version="reviewer-v1",
                prompt="read only",
                base_sha="a" * 40,
                reviewed_sha="b" * 40,
                diff_text="diff",
                requirement_text="requirement",
                gate_summary="pass",
                evidence_refs=("diff:1", "req:1", "gate:1"),
            )
        )
