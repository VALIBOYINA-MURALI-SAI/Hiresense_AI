"""
OAuth2 (authorization code) helpers for Google and GitHub sign-in.
Uses st.secrets for client credentials and redirect URI; exchange runs on the server.
"""
from __future__ import annotations

import secrets as secrets_mod
import urllib.parse
from typing import Any, Optional, Tuple

import requests

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


def new_oauth_state() -> str:
    return secrets_mod.token_urlsafe(32)


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