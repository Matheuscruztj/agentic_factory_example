import json

from quality_gates.aggregate import aggregate_results


def artifact(path, check, status="pass", exit_code=0, steps=None):
    path.write_text(json.dumps({
        "schema": 1,
        "check": check,
        "status": status,
        "ok": int(status == "pass"),
        "exit_code": exit_code,
        "metrics": {},
        "artifact": None,
        "errors": [],
        "steps": steps or [],
    }))


def test_missing_required_gate_cannot_be_overridden(tmp_path):
    python = tmp_path / "python.json"
    artifact(python, "quality-python")

    result = aggregate_results([python], required=("quality-python", "quality-frontend"))

    assert result["status"] == "error"
    assert result["missing"] == ["quality-frontend"]


def test_failed_deterministic_gate_remains_failed(tmp_path):
    python = tmp_path / "python.json"
    frontend = tmp_path / "frontend.json"
    artifact(python, "quality-python")
    artifact(frontend, "quality-frontend", "fail", 1)

    result = aggregate_results([python, frontend], required=("quality-python", "quality-frontend"))

    assert result["status"] == "fail"
    assert result["first_failure"]["check"] == "quality-frontend"


def test_unjustified_skipped_step_is_not_a_pass(tmp_path):
    python = tmp_path / "python.json"
    artifact(python, "quality-python", steps=[{"name": "mypy", "status": "skipped"}])

    result = aggregate_results([python], required=("quality-python",))

    assert result["status"] == "error"
