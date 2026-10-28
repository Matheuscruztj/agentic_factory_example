from observability import gpu


def test_gpu_metrics_missing_or_broken_tool_are_non_blocking(monkeypatch):
    monkeypatch.setattr(gpu.shutil, "which", lambda _name: None)
    assert gpu.probe()["status"] == "unavailable"

    monkeypatch.setattr(gpu.shutil, "which", lambda _name: "/fake/nvidia-smi")

    def broken(*args, **kwargs):
        raise gpu.subprocess.TimeoutExpired("nvidia-smi", 3)

    monkeypatch.setattr(gpu.subprocess, "run", broken)
    assert gpu.probe() == {
        "status": "unavailable",
        "source": "nvidia-smi",
        "reason": "TimeoutExpired",
    }


def test_gpu_metrics_parse_fake_device(monkeypatch):
    class Result:
        returncode = 0
        stdout = "RTX Test, 8192, 4096, 25, 72.5\n"

    monkeypatch.setattr(gpu.shutil, "which", lambda _name: "/fake/nvidia-smi")
    monkeypatch.setattr(gpu.subprocess, "run", lambda *args, **kwargs: Result())
    result = gpu.probe()
    assert result["status"] == "available"
    assert result["devices"][0]["memory_used_mib"] == 4096
    assert result["devices"][0]["power_watts"] == 72.5
