from quality_gates.schema import result_status, validate_result


def test_quality_result_contract_distinguishes_pass_code_and_infra():
    assert result_status(0) == "pass"
    assert result_status(1) == "fail"
    assert result_status(2) == "error"
    good = {
        "schema": 1, "check": "unit", "status": "pass", "ok": 1, "exit_code": 0,
        "metrics": {}, "artifact": None, "errors": [],
    }
    assert validate_result(good) == []
    bad = {**good, "status": "pass", "exit_code": 2}
    assert "PASS_EXIT_CODE_MISMATCH" in validate_result(bad)
