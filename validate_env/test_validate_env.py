"""Offline tests for scripts/validate_env.py; no real credentials or network needed."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "validate_env.py"
spec = importlib.util.spec_from_file_location("validate_env", MODULE)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / ".env"

    def test_no_network_local(self):
        self.path.write_text(
            "GITHUB_OWNER=owner\nGITHUB_REPO=repo\nGITHUB_TOKEN=dummy_not_real\nGITHUB_AUTH_MODE=pat\n"
        )
        with patch.object(preflight, "http_json", side_effect=AssertionError("network called")):
            code, output = preflight.run(self.path, "local", {"github"}, 1)
        self.assertEqual(code, 0)
        self.assertEqual(output["metrics"]["passed"], 1)
        self.assertNotIn("dummy_not_real", str(output))

    def test_missing_required_secret_is_fail_one(self):
        self.path.write_text("GITHUB_OWNER=o\nGITHUB_REPO=r\n")
        code, output = preflight.run(self.path, "local", {"github"}, 1)
        self.assertEqual(code, 1)
        self.assertEqual(output["checks"][0]["reason"], "MISSING_GITHUB_TOKEN")

    def test_missing_env_file_is_error_two(self):
        code, output = preflight.run(self.path, "local", {"github"}, 1)
        self.assertEqual(code, 2)
        self.assertEqual(output["reason"], "ENV_FILE_MISSING")

    def test_duplicate_key_is_error_two(self):
        self.path.write_text("GITHUB_TOKEN=x\nGITHUB_TOKEN=y\n")
        code, output = preflight.run(self.path, "local", set(), 1)
        self.assertEqual(code, 1)
        self.assertIn("ENV_DUPLICATE_", output["reason"])

    def test_invalid_telegram_token(self):
        self.path.write_text("TELEGRAM_ENABLED=true\nTELEGRAM_BOT_TOKEN=invalid-token\n")
        code, output = preflight.run(self.path, "local", set(), 1)
        self.assertEqual(code, 1)
        self.assertEqual(output["checks"][1]["reason"], "TELEGRAM_TOKEN_FORMAT")

    def test_optional_integration_skipped(self):
        self.path.write_text("GITHUB_ENABLED=false\nTELEGRAM_ENABLED=false\n")
        code, output = preflight.run(self.path, "live", set(), 1)
        self.assertEqual(code, 0)
        self.assertEqual(output["metrics"]["skipped"], 7)

    def test_live_ollama_with_model_found(self):
        self.path.write_text(
            "OLLAMA_BASE_URL=http://localhost:11434\nOLLAMA_MODEL_CODING=example:7b\n"
        )
        with patch.object(
            preflight, "http_json", return_value={"models": [{"name": "example:7b"}]}
        ):
            code, output = preflight.run(self.path, "live", {"ollama"}, 1)
        self.assertEqual(code, 0)
        self.assertEqual(output["checks"][3]["status"], "pass")

    def test_network_error_returns_two(self):
        self.path.write_text("OLLAMA_BASE_URL=http://localhost:11434\n")
        with patch.object(
            preflight, "http_json", side_effect=preflight.ProbeError("NETWORK", "UNREACHABLE")
        ):
            code, output = preflight.run(self.path, "live", {"ollama"}, 1)
        self.assertEqual(code, 2)
        self.assertEqual(output["checks"][3]["category"], "NETWORK")

    def test_auth_fail_returns_one_and_no_secret(self):
        self.path.write_text("TELEGRAM_BOT_TOKEN=123456:my_private_test_token\n")
        with patch.object(
            preflight, "http_json", side_effect=preflight.ProbeError("AUTH", "HTTP_401")
        ):
            code, output = preflight.run(self.path, "live", {"telegram"}, 1)
        self.assertEqual(code, 1)
        self.assertNotIn("my_private_test_token", str(output))

    def test_disabled_explicit_can_be_required(self):
        self.path.write_text(
            "GITHUB_ENABLED=false\nGITHUB_OWNER=foo\nGITHUB_REPO=bar\nGITHUB_TOKEN=dummy\n"
        )
        code, output = preflight.run(self.path, "local", {"github"}, 1)
        self.assertEqual(code, 0)
        self.assertEqual(output["checks"][0]["status"], "pass")

    def test_postgres_invalid_url_fails(self):
        self.path.write_text("DATABASE_URL=not-a-db-url\n")
        code, output = preflight.run(self.path, "local", {"postgres"}, 1)
        self.assertEqual(code, 1)
        self.assertEqual(output["checks"][5]["reason"], "DATABASE_URL_INVALID")

    def test_redis_url_local_pass(self):
        self.path.write_text("REDIS_URL=redis://localhost:6379/0\n")
        with patch.object(preflight, "http_json", side_effect=AssertionError("network called")):
            code, output = preflight.run(self.path, "local", {"redis"}, 1)
        self.assertEqual(code, 0)
        self.assertEqual(output["checks"][6]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
