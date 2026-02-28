import os
from itsdangerous import URLSafeTimedSerializer
from fastapi import Request

SESSION_COOKIE = "mp_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _get_signer() -> URLSafeTimedSerializer:
    key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    return URLSafeTimedSerializer(key)


def create_session_token() -> str:
    return _get_signer().dumps("ok")


def verify_session_token(token: str) -> bool:
    try:
        _get_signer().loads(token, max_age=SESSION_MAX_AGE)
        return True
    except Exception:
        return False


# Paths that don't require auth
_PUBLIC_PREFIXES = ("/login", "/static", "/demo")


def is_public(path: str) -> bool:
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)
