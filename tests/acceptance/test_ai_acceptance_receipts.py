from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ai_acceptance import get_or_create_receipt_key, seal_receipt, verify_receipt_hmac


def test_receipt_key_and_private_configuration_never_become_model_evidence(tmp_path):
    from scripts.ai_acceptance import _safe_runtime_artifact

    get_or_create_receipt_key(tmp_path)
    for name in (".runtime/artifacts/uat/ai-acceptance.key", ".runtime/private/stack.env"):
        with pytest.raises(ValueError, match="SECRET_PATH_FORBIDDEN"):
            _safe_runtime_artifact(tmp_path, name)


def test_ai_receipt_is_locally_sealed_and_tampering_is_detected(tmp_path: Path) -> None:
    key = get_or_create_receipt_key(tmp_path)
    receipt = seal_receipt({"decision": "approve", "verdict": "pass"}, key)

    assert verify_receipt_hmac(receipt, key)
    assert not verify_receipt_hmac({**receipt, "decision": "reject"}, key)
    assert (tmp_path / ".runtime/artifacts/uat/ai-acceptance.key").stat().st_mode & 0o077 == 0
