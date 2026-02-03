from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import RedirectResponse


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def _session_secret() -> bytes:
    sec = os.getenv("COMPANION_SESSION_SECRET") or os.getenv("COMPANION_EXEC_SECRET") or ""
    return sec.encode("utf-8")


def _sign(payload: bytes) -> str:
    return _b64(hmac.new(_session_secret(), payload, hashlib.sha256).digest())


def _encode_session(data: Dict[str, Any]) -> str:
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = _sign(raw)
    return _b64(raw) + "." + sig


def _decode_session(token: str) -> Optional[Dict[str, Any]]:
    try:
        raw_b64, sig = token.split(".", 1)
        raw = _b64d(raw_b64)
        if not hmac.compare_digest(sig, _sign(raw)):
            return None
        data = json.loads(raw.decode("utf-8"))
        if data.get("exp") and time.time() > float(data["exp"]):
            return None
        return data
    except Exception:
        return None


def _auth_mode() -> str:
    return (os.getenv("COMPANION_AUTH_MODE") or "none").strip().lower()


def is_auth_enabled() -> bool:
    return _auth_mode() in ("password", "oauth")


def get_user(request: Request) -> Optional[Dict[str, Any]]:
    if not is_auth_enabled():
        return {"user": "local"}
    tok = request.cookies.get("companion_session")
    if not tok:
        return None
    data = _decode_session(tok)
    return data


def require_login(request: Request):
    if not is_auth_enabled():
        return None
    user = get_user(request)
    if user:
        return None
    return RedirectResponse(url="/login", status_code=303)


def set_password_session(resp, user: str = "local", ttl_s: int = 3600):
    data = {"user": user, "mode": "password", "exp": time.time() + ttl_s}
    resp.set_cookie("companion_session", _encode_session(data), httponly=True, samesite="lax")


def set_oauth_session(resp, user: str, email: str, ttl_s: int = 3600):
    data = {"user": user, "email": email, "mode": "oauth", "exp": time.time() + ttl_s}
    resp.set_cookie("companion_session", _encode_session(data), httponly=True, samesite="lax")


def clear_session(resp):
    resp.delete_cookie("companion_session")


def oauth_login_url(redirect_uri: str) -> str:
    auth_url = os.getenv("COMPANION_OAUTH_AUTH_URL", "")
    client_id = os.getenv("COMPANION_OAUTH_CLIENT_ID", "")
    scopes = os.getenv("COMPANION_OAUTH_SCOPES", "openid email profile")
    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
    }
    return auth_url + "?" + urllib.parse.urlencode(params), state


def encode_state(state: str, ttl_s: int = 600) -> str:
    data = {"state": state, "exp": time.time() + ttl_s}
    return _encode_session(data)


def decode_state(token: str) -> Optional[str]:
    data = _decode_session(token)
    if not data:
        return None
    return data.get("state")


def oauth_exchange_code(code: str, redirect_uri: str) -> Dict[str, Any]:
    token_url = os.getenv("COMPANION_OAUTH_TOKEN_URL", "")
    client_id = os.getenv("COMPANION_OAUTH_CLIENT_ID", "")
    client_secret = os.getenv("COMPANION_OAUTH_CLIENT_SECRET", "")
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(token_url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode("utf-8")
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


def oauth_userinfo(access_token: str) -> Dict[str, Any]:
    userinfo_url = os.getenv("COMPANION_OAUTH_USERINFO_URL", "")
    req = urllib.request.Request(userinfo_url, headers={"Authorization": f"Bearer {access_token}"}, method="GET")
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode("utf-8")
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


def oauth_email_allowed(email: str) -> bool:
    allow_emails = os.getenv("COMPANION_OAUTH_ALLOWED_EMAILS", "").strip()
    allow_domains = os.getenv("COMPANION_OAUTH_ALLOWED_DOMAINS", "").strip()
    if not allow_emails and not allow_domains:
        return True
    email_l = email.lower()
    if allow_emails:
        allowed = [e.strip().lower() for e in allow_emails.split(",") if e.strip()]
        if email_l in allowed:
            return True
    if allow_domains:
        domains = [d.strip().lower() for d in allow_domains.split(",") if d.strip()]
        for d in domains:
            if email_l.endswith("@" + d):
                return True
    return False
