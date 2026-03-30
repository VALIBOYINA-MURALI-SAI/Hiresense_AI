"""
OAuth2 (authorization code) helpers for Google and GitHub sign-in.
Uses st.secrets for client credentials and redirect URI; exchange runs on the server.
"""
from __future__ import annotations

import os

import base64
import hashlib
import hmac
import json
import secrets as secrets_mod
import time
import urllib.parse
from typing import Any, Optional, Tuple

import requests

# Signed OAuth state survives Streamlit session loss after external redirect (e.g. Streamlit Cloud).
_STATE_TTL_SEC = 20 * 60
_STATE_VER = 1

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v2/userinfo"

GITHUB_AUTH = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"


def _secrets_dict() -> dict:
    try:
        import streamlit as st

        return dict(st.secrets)
    except Exception:
        return {}


def oauth_redirect_uri() -> Optional[str]:
    """
    Redirect URI sent to Google/GitHub must match exactly what is registered for that client.

    Resolution order (first non-empty wins):
    1. Environment: OAUTH_REDIRECT_URI, oauth_redirect_uri, HIRERESUME_OAUTH_REDIRECT_URI
       → use in local `.env` so **localhost** wins over Streamlit secrets that point at Cloud.
    2. Streamlit secrets: oauth_redirect_uri or OAUTH_REDIRECT_URI (typical on Streamlit Cloud).
    """
    for key in (
        "OAUTH_REDIRECT_URI",
        "oauth_redirect_uri",
        "HIRERESUME_OAUTH_REDIRECT_URI",
    ):
        v = os.environ.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()

    d = _secrets_dict()
    u = d.get("oauth_redirect_uri") or d.get("OAUTH_REDIRECT_URI")
    if u is None:
        return None
    s = str(u).strip()
    return s or None


def google_client_credentials() -> Tuple[Optional[str], Optional[str]]:
    d = _secrets_dict()
    cid = str(d.get("oauth_google_client_id") or d.get("OAUTH_GOOGLE_CLIENT_ID") or "").strip() or None
    sec = str(d.get("oauth_google_client_secret") or d.get("OAUTH_GOOGLE_CLIENT_SECRET") or "").strip() or None
    return cid, sec


def github_client_credentials() -> Tuple[Optional[str], Optional[str]]:
    d = _secrets_dict()
    cid = str(d.get("oauth_github_client_id") or d.get("OAUTH_GITHUB_CLIENT_ID") or "").strip() or None
    sec = str(d.get("oauth_github_client_secret") or d.get("OAUTH_GITHUB_CLIENT_SECRET") or "").strip() or None
    return cid, sec


def google_oauth_configured() -> bool:
    cid, sec = google_client_credentials()
    return bool(cid and sec)


def github_oauth_configured() -> bool:
    cid, sec = github_client_credentials()
    return bool(cid and sec)


def any_oauth_configured() -> bool:
    return google_oauth_configured() or github_oauth_configured()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def oauth_state_signing_key() -> Optional[bytes]:
    """Stable server-side key for HMAC state (never sent to browser except inside signed blob)."""
    d = _secrets_dict()
    explicit = d.get("oauth_state_secret") or d.get("OAUTH_STATE_SECRET")
    if explicit is not None and str(explicit).strip():
        return hashlib.sha256(str(explicit).strip().encode("utf-8")).digest()
    parts: list[str] = []
    _, gs = google_client_credentials()
    _, hs = github_client_credentials()
    if gs:
        parts.append(str(gs))
    if hs:
        parts.append(str(hs))
    if not parts:
        return None
    return hashlib.sha256("||".join(parts).encode("utf-8")).digest()


def new_oauth_state(provider: str) -> str:
    """
    CSRF state for authorize URL.
    When client secrets (or oauth_state_secret) exist, returns a signed token so the callback
    does not depend on st.session_state after Google/GitHub redirect (fixes \"session expired\").
    """
    key = oauth_state_signing_key()
    p = str(provider).strip().lower()
    if p not in ("google", "github"):
        p = "google"
    if not key:
        return secrets_mod.token_urlsafe(32)
    nonce = secrets_mod.token_urlsafe(16)
    payload = {"v": _STATE_VER, "p": p, "n": nonce, "t": int(time.time())}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    p_b64 = _b64url_encode(raw)
    sig = hmac.new(key, p_b64.encode("ascii"), hashlib.sha256).digest()
    s_b64 = _b64url_encode(sig)
    return f"v{_STATE_VER}.{p_b64}.{s_b64}"


def parse_signed_oauth_state(state_param: str) -> Optional[str]:
    """
    If state is a valid signed token, return provider ('google' | 'github').
    Otherwise return None (caller may fall back to session-stored random state).
    """
    key = oauth_state_signing_key()
    if not key or not state_param or not str(state_param).startswith(f"v{_STATE_VER}."):
        return None
    parts = str(state_param).split(".", 2)
    if len(parts) != 3:
        return None
    _, p_b64, s_b64 = parts
    try:
        sig = _b64url_decode(s_b64)
        expect = hmac.new(key, p_b64.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expect):
            return None
        payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
        if int(payload.get("v", 0)) != _STATE_VER:
            return None
        t0 = int(payload.get("t", 0))
        if int(time.time()) - t0 > _STATE_TTL_SEC:
            return None
        p = str(payload.get("p", "")).lower()
        if p not in ("google", "github"):
            return None
        return p
    except Exception:
        return None


def build_google_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH}?{urllib.parse.urlencode(params)}"


def build_github_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user user:email",
        "state": state,
    }
    return f"{GITHUB_AUTH}?{urllib.parse.urlencode(params)}"


def exchange_google_code(
    code: str, client_id: str, client_secret: str, redirect_uri: str
) -> dict[str, Any]:
    r = requests.post(
        GOOGLE_TOKEN,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def fetch_google_profile(access_token: str) -> dict[str, Any]:
    r = requests.get(
        GOOGLE_USERINFO,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def exchange_github_code(
    code: str, client_id: str, client_secret: str, redirect_uri: str
) -> dict[str, Any]:
    r = requests.post(
        GITHUB_TOKEN,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        headers={"Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(data.get("error_description") or data.get("error"))
    return data


def fetch_github_user(access_token: str) -> dict[str, Any]:
    r = requests.get(
        f"{GITHUB_API}/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def fetch_github_primary_email(access_token: str) -> Optional[str]:
    r = requests.get(
        f"{GITHUB_API}/user/emails",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    r.raise_for_status()
    emails = r.json()
    for e in emails:
        if e.get("primary") and e.get("verified"):
            return e.get("email")
    for e in emails:
        if e.get("verified"):
            return e.get("email")
    return None


def normalize_google_user(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": "google",
        "id": raw.get("id") or raw.get("sub"),
        "email": raw.get("email"),
        "name": raw.get("name") or raw.get("email"),
        "picture": raw.get("picture"),
    }


def normalize_github_user(raw: dict[str, Any], email: Optional[str]) -> dict[str, Any]:
    return {
        "provider": "github",
        "id": str(raw.get("id")),
        "email": email or raw.get("email"),
        "name": raw.get("name") or raw.get("login") or email,
        "picture": raw.get("avatar_url"),
    }


# ---------------------------------------------------------------------------
# Persistent session tokens (cookie-based, HMAC-signed, 5-hour default TTL)
# ---------------------------------------------------------------------------

_SESSION_TOKEN_VER = 1


def create_session_token(user: dict[str, Any], *, ttl_hours: float = 5) -> Optional[str]:
    """Return a signed, URL-safe token encoding *user* with an expiry, or None if no signing key."""
    key = oauth_state_signing_key()
    if not key:
        return None
    payload = {
        "v": _SESSION_TOKEN_VER,
        "u": {k: user.get(k) for k in ("provider", "id", "email", "name", "picture")},
        "exp": int(time.time() + ttl_hours * 3600),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    p_b64 = _b64url_encode(raw)
    sig = hmac.new(key, p_b64.encode("ascii"), hashlib.sha256).digest()
    return f"s{_SESSION_TOKEN_VER}.{p_b64}.{_b64url_encode(sig)}"


def create_guest_session_token(*, ttl_hours: float = 5) -> Optional[str]:
    """Signed token for guest (no OAuth user) sessions."""
    key = oauth_state_signing_key()
    if not key:
        return None
    payload = {
        "v": _SESSION_TOKEN_VER,
        "guest": True,
        "exp": int(time.time() + ttl_hours * 3600),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    p_b64 = _b64url_encode(raw)
    sig = hmac.new(key, p_b64.encode("ascii"), hashlib.sha256).digest()
    return f"s{_SESSION_TOKEN_VER}.{p_b64}.{_b64url_encode(sig)}"


def validate_session_token(token: str) -> Optional[dict[str, Any]]:
    """
    Validate a session token. Returns the payload dict (with key ``u`` for user
    or ``guest`` for guest sessions), or None if invalid/expired.
    """
    key = oauth_state_signing_key()
    if not key or not token or not str(token).startswith(f"s{_SESSION_TOKEN_VER}."):
        return None
    parts = str(token).split(".", 2)
    if len(parts) != 3:
        return None
    _, p_b64, s_b64 = parts
    try:
        sig = _b64url_decode(s_b64)
        expect = hmac.new(key, p_b64.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expect):
            return None
        payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
        if int(payload.get("v", 0)) != _SESSION_TOKEN_VER:
            return None
        if int(time.time()) > int(payload.get("exp", 0)):
            return None
        return payload
    except Exception:
        return None