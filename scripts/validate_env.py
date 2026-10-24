#!/usr/bin/env python3
"""Safe, read-only integration preflight (Python 3.11+; stdlib by default).

Exit 0: all required checks passed. Exit 1: invalid configuration/credentials.
Exit 2: infrastructure / network / operational error. Stdout: exactly one JSON line.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

SERVICES = (
    "github",
    "telegram",
    "jira",
    "ollama",
    "sonar",
    "postgres",
    "redis",
    "core",
    "openbot",
    "phoenix",
)
PROBE_ERROR = {"CONFIG": 1, "AUTH": 1, "NETWORK": 2, "SERVICE": 2}


class ConfigError(Exception):
    pass


class ProbeError(Exception):
    def __init__(self, category: str, code: str):
        super().__init__(code)
        self.category, self.code = category, code


def read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ConfigError("ENV_FILE_MISSING")
    result: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise ConfigError(f"ENV_SYNTAX_LINE_{number}")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ConfigError(f"ENV_KEY_LINE_{number}")
        if key in result:
            raise ConfigError(f"ENV_DUPLICATE_{key}")
        value = value.strip()
        if value.startswith(('"', "'")):
            q = value[0]
            if len(value) < 2 or value[-1] != q:
                raise ConfigError(f"ENV_QUOTE_LINE_{number}")
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        result[key] = value
    return result


def is_enabled(cfg: dict[str, str], service: str, required: set[str]) -> bool:
    if service in required:
        return True
    if service == "core":
        return bool(cfg.get("FACTORY_ENV"))
    v = cfg.get(f"{service.upper()}_ENABLED", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    if service == "github":
        return bool(cfg.get("GITHUB_TOKEN") or cfg.get("GITHUB_APP_ID"))
    if service == "ollama":
        return bool(cfg.get("OLLAMA_BASE_URL"))
    if service == "sonar":
        return bool(cfg.get("SONAR_TOKEN"))
    if service == "telegram":
        return bool(cfg.get("TELEGRAM_BOT_TOKEN"))
    if service == "jira":
        return bool(cfg.get("JIRA_API_TOKEN"))
    if service == "postgres":
        return bool(cfg.get("DATABASE_URL"))
    if service == "redis":
        return bool(cfg.get("REDIS_URL"))
    if service == "openbot":
        return bool(cfg.get("OPENBOT_API_KEY"))
    if service == "phoenix":
        return False
    return False


def require(cfg: dict[str, str], *keys: str) -> None:
    for key in keys:
        if not cfg.get(key, "").strip():
            raise ProbeError("CONFIG", f"MISSING_{key}")


def safe_url(raw: str, *, tls_required: bool = False, local_allowed: bool = True) -> str:
    p = urlparse(raw)
    if (
        p.scheme not in ("http", "https")
        or not p.hostname
        or p.username
        or p.password
        or p.query
        or p.fragment
    ):
        raise ProbeError("CONFIG", "INVALID_URL")
    if tls_required and p.scheme != "https":
        raise ProbeError("CONFIG", "TLS_REQUIRED")
    if p.scheme == "http" and not local_allowed:
        raise ProbeError("CONFIG", "HTTP_NOT_ALLOWED")
    return raw.rstrip("/")


def http_json(url: str, headers: dict[str, str], timeout: float) -> dict:
    try:
        req = Request(url, headers={**headers, "User-Agent": "agentic-factory-preflight/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            content = resp.read(1024 * 1024)
            value = json.loads(content)
            if not isinstance(value, dict):
                raise ProbeError("SERVICE", "UNEXPECTED_RESPONSE")
            return value
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise ProbeError("AUTH", f"HTTP_{exc.code}") from None
        if exc.code == 404:
            raise ProbeError("CONFIG", "HTTP_404") from None
        if exc.code == 429:
            raise ProbeError("SERVICE", "RATE_LIMITED") from None
        raise ProbeError("SERVICE", f"HTTP_{exc.code}") from None
    except (URLError, TimeoutError, ConnectionError):
        raise ProbeError("NETWORK", "UNREACHABLE") from None
    except (ValueError, UnicodeDecodeError):
        raise ProbeError("SERVICE", "INVALID_RESPONSE") from None


def github_app_jwt(cfg: dict[str, str]) -> str:
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError:
        raise ProbeError("SERVICE", "MISSING_CRYPTOGRAPHY_PACKAGE") from None
    key_path = Path(cfg["GITHUB_APP_PRIVATE_KEY_PATH"])
    if not key_path.is_file():
        raise ProbeError("CONFIG", "GITHUB_PEM_MISSING")
    try:
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        now = int(time.time())

        def encode(obj: dict) -> bytes:
            payload = json.dumps(obj, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(payload).rstrip(b"=")

        signing = b".".join(
            (
                encode({"alg": "RS256", "typ": "JWT"}),
                encode({"iat": now - 60, "exp": now + 540, "iss": cfg["GITHUB_APP_ID"]}),
            )
        )
        sig = key.sign(signing, padding.PKCS1v15(), hashes.SHA256())
        return signing.decode() + "." + base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    except (OSError, ValueError, TypeError, AttributeError):
        raise ProbeError("CONFIG", "GITHUB_PEM_INVALID") from None


def check_github(cfg: dict[str, str], live: bool, timeout: float) -> str:
    require(cfg, "GITHUB_OWNER", "GITHUB_REPO")
    owner, repo = cfg["GITHUB_OWNER"], cfg["GITHUB_REPO"]
    if not re.fullmatch(r"[\w.-]+", owner) or not re.fullmatch(r"[\w.-]+", repo):
        raise ProbeError("CONFIG", "INVALID_GITHUB_REPOSITORY")
    mode = cfg.get("GITHUB_AUTH_MODE", "pat").lower()
    api = safe_url(cfg.get("GITHUB_API_URL", "https://api.github.com"), tls_required=True)
    if mode == "pat":
        require(cfg, "GITHUB_TOKEN")
        if not live:
            return "CONFIG_VALIDATED_NOT_AUTHENTICATED"
        http_json(
            f"{api}/repos/{quote(owner)}/{quote(repo)}",
            {
                "Authorization": f"Bearer {cfg['GITHUB_TOKEN']}",
                "Accept": "application/vnd.github+json",
            },
            timeout,
        )
    elif mode == "app":
        require(cfg, "GITHUB_APP_ID", "GITHUB_INSTALLATION_ID", "GITHUB_APP_PRIVATE_KEY_PATH")
        if not Path(cfg["GITHUB_APP_PRIVATE_KEY_PATH"]).is_file():
            raise ProbeError("CONFIG", "GITHUB_PEM_MISSING")
        if not live:
            return "CONFIG_VALIDATED_NOT_AUTHENTICATED"
        jwt = github_app_jwt(cfg)
        http_json(
            f"{api}/app",
            {"Authorization": f"Bearer {jwt}", "Accept": "application/vnd.github+json"},
            timeout,
        )
        # This endpoint validates installation identity. It does NOT prove write permissions.
        http_json(
            f"{api}/app/installations/{quote(cfg['GITHUB_INSTALLATION_ID'])}",
            {"Authorization": f"Bearer {jwt}", "Accept": "application/vnd.github+json"},
            timeout,
        )
    else:
        raise ProbeError("CONFIG", "UNSUPPORTED_GITHUB_AUTH_MODE")
    return "READ_AUTH_VALIDATED_PERMISSIONS_NOT_PROVEN"


def check_telegram(cfg: dict[str, str], live: bool, timeout: float) -> str:
    require(cfg, "TELEGRAM_BOT_TOKEN")
    token = cfg["TELEGRAM_BOT_TOKEN"]
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
        raise ProbeError("CONFIG", "TELEGRAM_TOKEN_FORMAT")
    if not live:
        return "CONFIG_VALIDATED_NOT_AUTHENTICATED"
    body = http_json(f"https://api.telegram.org/bot{token}/getMe", {}, timeout)
    if body.get("ok") is not True:
        raise ProbeError("AUTH", "TELEGRAM_NOT_OK")
    # Optional chat ID: verifies bot can access the chat, no messages sent.
    if cfg.get("TELEGRAM_CHAT_ID"):
        chat = quote(cfg["TELEGRAM_CHAT_ID"], safe="-@")
        chat_result = http_json(
            f"https://api.telegram.org/bot{token}/getChat?chat_id={chat}", {}, timeout
        )
        if chat_result.get("ok") is not True:
            raise ProbeError("AUTH", "TELEGRAM_CHAT_INACCESSIBLE")
    return "BOT_AUTH_VALIDATED_NO_MESSAGE_SENT"


def check_jira(cfg: dict[str, str], live: bool, timeout: float) -> str:
    require(cfg, "JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
    host = safe_url(cfg["JIRA_BASE_URL"], tls_required=True)
    if not live:
        return "CONFIG_VALIDATED_NOT_AUTHENTICATED"
    basic = base64.b64encode(f"{cfg['JIRA_EMAIL']}:{cfg['JIRA_API_TOKEN']}".encode()).decode()
    http_json(
        f"{host}/rest/api/3/myself",
        {"Authorization": f"Basic {basic}", "Accept": "application/json"},
        timeout,
    )
    if cfg.get("JIRA_PROJECT_KEY"):
        http_json(
            f"{host}/rest/api/3/project/{quote(cfg['JIRA_PROJECT_KEY'])}",
            {"Authorization": f"Basic {basic}", "Accept": "application/json"},
            timeout,
        )
    return "JIRA_READ_AUTH_VALIDATED_NO_WRITE_TEST"


def check_ollama(cfg: dict[str, str], live: bool, timeout: float) -> str:
    require(cfg, "OLLAMA_BASE_URL")
    host = safe_url(cfg["OLLAMA_BASE_URL"])
    if not live:
        return "CONFIG_VALIDATED_NOT_CONNECTED"
    body = http_json(f"{host}/api/tags", {}, timeout)
    if "models" not in body or not isinstance(body["models"], list):
        raise ProbeError("SERVICE", "OLLAMA_TAGS_INVALID")
    available = {x.get("name") for x in body["models"] if isinstance(x, dict)}
    for key in ("OLLAMA_MODEL_CHAT", "OLLAMA_MODEL_CODING", "OLLAMA_MODEL_JUDGE"):
        if cfg.get(key) and cfg[key] not in available:
            raise ProbeError("CONFIG", f"MODEL_NOT_FOUND_{key}")
    return "OLLAMA_REACHABLE_MODELS_FOUND_NO_INFERENCE_RUN"


def check_sonar(cfg: dict[str, str], live: bool, timeout: float) -> str:
    require(cfg, "SONAR_HOST_URL", "SONAR_TOKEN")
    host = safe_url(cfg["SONAR_HOST_URL"])
    if not live:
        return "CONFIG_VALIDATED_NOT_AUTHENTICATED"
    body = http_json(
        f"{host}/api/authentication/validate",
        {"Authorization": f"Bearer {cfg['SONAR_TOKEN']}"},
        timeout,
    )
    if body.get("valid") is not True:
        raise ProbeError("AUTH", "SONAR_TOKEN_INVALID")
    return "SONAR_AUTH_VALIDATED_ANALYSIS_PERMISSIONS_NOT_PROVEN"


def check_postgres(cfg: dict[str, str], live: bool, timeout: float) -> str:
    require(cfg, "DATABASE_URL")
    url = cfg["DATABASE_URL"]
    p = urlparse(url)
    if (
        p.scheme not in ("postgresql", "postgresql+psycopg", "postgres")
        or not p.hostname
        or not p.path.strip("/")
    ):
        raise ProbeError("CONFIG", "DATABASE_URL_INVALID")
    if "REPLACE_" in url or "CHANGE_ME" in url:
        raise ProbeError("CONFIG", "DATABASE_PLACEHOLDER_NOT_REPLACED")
    if not live:
        return "CONFIG_VALIDATED_NOT_CONNECTED"
    try:
        import psycopg
    except ImportError:
        raise ProbeError("SERVICE", "MISSING_PSYCOPG_PACKAGE") from None
    # psycopg accepts postgresql://, not the SQLAlchemy +driver URL.
    dsn = url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        with psycopg.connect(dsn, connect_timeout=max(1, int(timeout))) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                if cur.fetchone() != (1,):
                    raise ProbeError("SERVICE", "POSTGRES_QUERY_FAILED")
    except psycopg.OperationalError as exc:
        message = str(exc).lower()
        if any(
            x in message
            for x in (
                "password authentication failed",
                "no pg_hba.conf entry",
                "role ",
                "database does not exist",
            )
        ):
            raise ProbeError("AUTH", "POSTGRES_AUTH_OR_ACCESS_DENIED") from None
        raise ProbeError("NETWORK", "POSTGRES_UNREACHABLE") from None
    return "POSTGRES_READ_QUERY_VALIDATED_NO_MUTATION"


def check_redis(cfg: dict[str, str], live: bool, timeout: float) -> str:
    require(cfg, "REDIS_URL")
    url = cfg["REDIS_URL"]
    p = urlparse(url)
    if p.scheme not in ("redis", "rediss") or not p.hostname:
        raise ProbeError("CONFIG", "REDIS_URL_INVALID")
    if not live:
        return "CONFIG_VALIDATED_NOT_CONNECTED"
    try:
        import redis
    except ImportError:
        raise ProbeError("SERVICE", "MISSING_REDIS_PACKAGE") from None
    try:
        client = redis.Redis.from_url(url, socket_connect_timeout=timeout, socket_timeout=timeout)
        try:
            if not client.ping():
                raise ProbeError("SERVICE", "REDIS_PING_FAILED")
        finally:
            client.close()
    except redis.exceptions.AuthenticationError:
        raise ProbeError("AUTH", "REDIS_AUTH_FAILED") from None
    except redis.exceptions.ConnectionError:
        raise ProbeError("NETWORK", "REDIS_UNREACHABLE") from None
    except redis.exceptions.TimeoutError:
        raise ProbeError("NETWORK", "REDIS_TIMEOUT") from None
    return "REDIS_PING_VALIDATED_NO_MUTATION"


def check_core(cfg: dict[str, str], live: bool, timeout: float) -> str:
    require(cfg, "FACTORY_ENV", "APP_SECRET_KEY")
    if cfg["FACTORY_ENV"] != "local":
        raise ProbeError("CONFIG", "LOCAL_ONLY_EXPECTED")
    if len(cfg["APP_SECRET_KEY"]) < 32 or any(
        x in cfg["APP_SECRET_KEY"].upper() for x in ("REPLACE", "CHANGE_ME")
    ):
        raise ProbeError("CONFIG", "APP_SECRET_KEY_WEAK_OR_PLACEHOLDER")
    if cfg.get("LOCAL_AUTH_ENABLED", "true").lower() in ("true", "1", "yes"):
        require(cfg, "OPERATOR_PASSWORD_HASH")
        if len(cfg["OPERATOR_PASSWORD_HASH"]) < 20:
            raise ProbeError("CONFIG", "OPERATOR_PASSWORD_HASH_INVALID")
    for name in ("LLM_MAX_CONCURRENT_REQUESTS", "WORKER_MAX_CONCURRENT_TASKS"):
        if name in cfg:
            if not cfg[name].isdigit() or int(cfg[name]) < 1:
                raise ProbeError("CONFIG", f"INVALID_{name}")
    for flag in ("ALLOW_AGENT_MERGE", "ALLOW_AGENT_DEPLOY"):
        if cfg.get(flag, "false").lower() in ("true", "yes", "1"):
            raise ProbeError("CONFIG", f"FORBIDDEN_{flag}_IN_LOCAL_MVP")
    return "LOCAL_CORE_CONFIG_VALIDATED"


def http_status(url: str, headers: dict[str, str], timeout: float) -> int:
    try:
        request = Request(url, headers={**headers, "User-Agent": "agentic-factory-preflight/2.0"})
        with urlopen(request, timeout=timeout) as response:
            response.read(4096)
            return response.status
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise ProbeError("AUTH", f"HTTP_{exc.code}") from None
        if exc.code == 404:
            raise ProbeError("CONFIG", "HTTP_404") from None
        raise ProbeError("SERVICE", f"HTTP_{exc.code}") from None
    except (URLError, TimeoutError, ConnectionError):
        raise ProbeError("NETWORK", "UNREACHABLE") from None


def check_openbot(cfg: dict[str, str], live: bool, timeout: float) -> str:
    require(cfg, "OPENBOT_BASE_URL", "OPENBOT_API_KEY")
    url = safe_url(cfg["OPENBOT_BASE_URL"])
    path = cfg.get("OPENBOT_HEALTH_PATH", "/api/v1/health")
    auth_probe_path = cfg.get("OPENBOT_AUTH_PROBE_PATH", "").strip()
    for value in (path, auth_probe_path):
        if value and (
            not value.startswith("/") or value.startswith("//") or "?" in value or "#" in value
        ):
            raise ProbeError("CONFIG", "OPENBOT_PATH_INVALID")
    if not live:
        return "CONFIG_VALIDATED_NOT_AUTHENTICATED"
    http_status(url + path, {}, timeout)
    if auth_probe_path:
        http_status(url + auth_probe_path, {"X-API-Key": cfg["OPENBOT_API_KEY"]}, timeout)
        return "HEALTH_AND_AUTH_ENDPOINT_VALIDATED"
    return "HEALTH_REACHABLE_AUTH_NOT_VERIFIED_ADD_AUTH_PROBE_PATH"


def check_phoenix(cfg: dict[str, str], live: bool, timeout: float) -> str:
    require(cfg, "PHOENIX_BASE_URL")
    url = safe_url(cfg["PHOENIX_BASE_URL"])
    if not live:
        return "CONFIG_VALIDATED_NOT_CONNECTED"
    http_status(url + "/", {}, timeout)
    return "PHOENIX_UI_REACHABLE_OTEL_EXPORT_NOT_VERIFIED"


CHECKS = {
    "github": check_github,
    "telegram": check_telegram,
    "jira": check_jira,
    "ollama": check_ollama,
    "sonar": check_sonar,
    "postgres": check_postgres,
    "redis": check_redis,
    "core": check_core,
    "openbot": check_openbot,
    "phoenix": check_phoenix,
}


def run(path: Path, mode: str, required: set[str], timeout: float) -> tuple[int, dict]:
    start = time.monotonic()
    try:
        cfg = read_env(path)
    except (OSError, ConfigError, UnicodeError) as exc:
        invalid = isinstance(exc, ConfigError) and str(exc) != "ENV_FILE_MISSING"
        code = 1 if invalid else 2
        reason = str(exc) if isinstance(exc, ConfigError) else "ENV_UNREADABLE"
        return code, {
            "schema": 1,
            "check": "env-preflight",
            "status": "fail" if invalid else "error",
            "ok": 0,
            "reason": reason,
        }
    checks = []
    outcome = 0
    for name in SERVICES:
        if not is_enabled(cfg, name, required):
            checks.append({"service": name, "status": "skipped"})
            continue
        begin = time.monotonic()
        try:
            detail = CHECKS[name](cfg, mode == "live", timeout)
            checks.append(
                {
                    "service": name,
                    "status": "pass",
                    "detail": detail,
                    "duration_ms": int((time.monotonic() - begin) * 1000),
                }
            )
        except ProbeError as exc:
            checks.append(
                {
                    "service": name,
                    "status": "fail" if exc.category in ("AUTH", "CONFIG") else "error",
                    "category": exc.category,
                    "reason": exc.code,
                }
            )
            outcome = max(outcome, PROBE_ERROR[exc.category])
        except Exception:
            checks.append(
                {
                    "service": name,
                    "status": "error",
                    "category": "SERVICE",
                    "reason": "UNEXPECTED_ERROR",
                }
            )
            outcome = 2
    result = {
        "schema": 1,
        "check": "env-preflight",
        "mode": mode,
        "status": {0: "pass", 1: "fail", 2: "error"}[outcome],
        "ok": int(outcome == 0),
        "metrics": {
            "passed": sum(x["status"] == "pass" for x in checks),
            "failed": sum(x["status"] == "fail" for x in checks),
            "errors": sum(x["status"] == "error" for x in checks),
            "skipped": sum(x["status"] == "skipped" for x in checks),
            "duration_ms": int((time.monotonic() - start) * 1000),
        },
        "checks": checks,
    }
    return outcome, result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate .env and optionally test provider credentials without writes"
    )
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--mode", choices=["local", "live"], default="local")
    parser.add_argument(
        "--require",
        default="",
        help="Comma-separated required integrations (github, ollama, core, openbot, etc.)",
    )
    parser.add_argument("--timeout", type=float, default=8)
    parser.add_argument("--output", choices=["json"], default="json")
    args = parser.parse_args()
    required = {x.strip().lower() for x in args.require.split(",") if x.strip()}
    if not required.issubset(SERVICES) or not 0 < args.timeout <= 120:
        print(
            json.dumps(
                {
                    "schema": 1,
                    "check": "env-preflight",
                    "status": "error",
                    "ok": 0,
                    "reason": "INVALID_ARGUMENTS",
                },
                separators=(",", ":"),
            )
        )
        return 2
    code, result = run(args.env, args.mode, required, args.timeout)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
