"""Single-user password login with a signed cookie, plus CSRF protection via a custom header."""

from __future__ import annotations

import asyncio
import hmac

from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from .config import get_settings

COOKIE = "steep_session"
MAX_AGE = 60 * 60 * 24 * 365  # one year: this is a personal app on your own server
CSRF_HEADER = "x-steep"


def _signer() -> TimestampSigner:
    return TimestampSigner(get_settings().secret_key, salt="steep-session")


def check_password(candidate: str) -> bool:
    expected = get_settings().password or ""
    return bool(expected) and hmac.compare_digest(candidate.encode(), expected.encode())


def issue(response: Response, request: Request) -> None:
    token = _signer().sign(b"owner").decode()
    response.set_cookie(
        COOKIE, token, max_age=MAX_AGE, httponly=True, samesite="lax",
        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
        path="/",
    )


def clear(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


def is_authenticated(request: Request) -> bool:
    header = get_settings().trust_proxy_header
    if header and request.headers.get(header):
        return True
    token = request.cookies.get(COOKIE)
    if not token:
        return False
    try:
        _signer().unsign(token, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return True


async def require_user(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Sign in required")
    # Browsers can't send a custom header cross-site without a CORS preflight we never allow,
    # so requiring it on writes blocks cross-site request forgery.
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=403, detail="Missing X-Steep header")


async def slow_down() -> None:
    await asyncio.sleep(1.0)
