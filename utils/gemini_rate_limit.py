"""
Gemini model fallback chain and availability checks.

No rate-limit pacing or long backoff here — callers decide retry / next model.
"""
from __future__ import annotations

import os
from typing import List


def gemini_model_fallback_chain() -> List[str]:
    raw = os.environ.get("GEMINI_MODEL_FALLBACKS", "").strip()
    if raw:
        return [m.strip() for m in raw.split(",") if m.strip()]
    # Free tier: quota is often per-model per day (e.g. ~20 RPD each). Multiple models = more analyses/day.
    # Order: prefer 2.5-flash, then 2.0-flash, then flash-lite (separate quota buckets).
    return [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.5-flash-lite",
    ]


def is_model_unavailable_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "not found" in msg and "model" in msg:
        return True
    if "invalid model" in msg:
        return True
    if "404" in msg and "model" in msg:
        return True
    return False


def is_rate_limit_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "429" in msg:
        return True
    if "resource exhausted" in msg:
        return True
    if "quota" in msg and ("exceed" in msg or "exceeded" in msg):
        return True
    if "too many requests" in msg:
        return True
    try:
        from google.api_core import exceptions as gexc

        _types = (gexc.ResourceExhausted,)
        _tm = getattr(gexc, "TooManyRequests", None)
        if _tm is not None:
            _types = _types + (_tm,)
        if isinstance(exc, _types):
            return True
    except Exception:
        pass
    return False
