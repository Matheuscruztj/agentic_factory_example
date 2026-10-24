from __future__ import annotations

from fastapi import Cookie, HTTPException, Request

from factory_api.auth.session import verify_session


def require_operator(request: Request, factory_session: str | None = Cookie(default=None)) -> dict:
    # Resolve settings at request time so app fixtures and local runtime overrides stay aligned.
    from factory_api.main import settings

    if not settings.auth_enabled:
        return {"sub": "operator", "csrf": "disabled"}
    data = verify_session(settings.secret_key, factory_session or "")
    if data is None:
        raise HTTPException(status_code=401, detail={"code": "AUTHENTICATION_REQUIRED"})
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get(
        "x-csrf-token"
    ) != data.get("csrf"):
        raise HTTPException(status_code=403, detail={"code": "CSRF_VALIDATION_FAILED"})
    return data
