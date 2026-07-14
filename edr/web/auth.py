"""Token auth. Control routes (mutations) require the admin token; read routes are public."""

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from edr.config import get_settings

COOKIE = "edr_token"


def is_admin(request: Request) -> bool:
    token = request.cookies.get(COOKIE) or request.headers.get("x-admin-token")
    return bool(token) and token == get_settings().admin_token


def require_admin(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return True


__all__ = ["COOKIE", "is_admin", "require_admin", "Depends", "RedirectResponse"]
