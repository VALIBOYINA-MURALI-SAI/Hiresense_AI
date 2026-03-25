"""
In-app social proof for the OAuth login / landing column.
Uses feedback/feedback.db for trust + experience scores only.
Optional env / Secrets fallbacks when there is no feedback data yet.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import streamlit as st

from config.database import get_ai_analysis_stats


def _env_float(key: str) -> float | None:
    raw = os.environ.get(key) or os.environ.get(key.lower())
    if raw is None or not str(raw).strip():
        return None
    try:
        return float(str(raw).strip())
    except ValueError:
        return None


def _secrets_float(*keys: str) -> float | None:
    try:
        sec = st.secrets
        for k in keys:
            if k in sec:
                raw = sec[k]
                if raw is not None and str(raw).strip():
                    return float(str(raw).strip())
    except Exception:
        pass
    return None


def _spotlight_float(env_key: str, *secret_keys: str) -> float | None:
    v = _env_float(env_key)
    if v is not None:
        return v
    return _secrets_float(*secret_keys) if secret_keys else None


def _feedback_path() -> Path:
    return Path(__file__).resolve().parent.parent / "feedback" / "feedback.db"


def _load_feedback_aggregates() -> tuple[int, float | None, float | None]:
    """
    Returns (n_rows, trust_pct, experience_pct).
    trust_pct = % with overall rating >= 4.
    experience_pct = mean(rating, usability, satisfaction) scaled to 0–100.
    """
    path = _feedback_path()
    if not path.is_file():
        return 0, None, None
    try:
        conn = sqlite3.connect(str(path))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM feedback")
        n = int(cur.fetchone()[0] or 0)
        if n == 0:
            conn.close()
            return 0, None, None
        cur.execute(
            """
            SELECT AVG(rating), AVG(usability_score), AVG(feature_satisfaction),
                   SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END)
            FROM feedback
            """
        )
        row = cur.fetchone()
        conn.close()
        ar, au, af, high = row[0] or 0, row[1] or 0, row[2] or 0, int(row[3] or 0)
        trust_pct = round(100.0 * high / n, 1)
        triple = (ar + au + af) / 3.0
        experience_pct = round(min(100.0, max(0.0, (triple / 5.0) * 100.0)), 1)
        return n, trust_pct, experience_pct
    except Exception:
        return 0, None, None


def render_login_spotlight_block() -> None:
    """Two prominent score cards for the sign-in landing column."""
    fb_n, trust_data, exp_data = _load_feedback_aggregates()
    ai_stats = get_ai_analysis_stats()
    ai_n = int(ai_stats.get("total_analyses") or 0)
    ai_avg = float(ai_stats.get("average_score") or 0)

    env_trust = _spotlight_float(
        "HIRERESUME_LOGIN_SPOTLIGHT_TRUST_PCT",
        "hireresume_login_spotlight_trust_pct",
    )
    env_exp = _spotlight_float(
        "HIRERESUME_LOGIN_SPOTLIGHT_EXPERIENCE_PCT",
        "hireresume_login_spotlight_experience_pct",
    )

    trust_val = trust_data if fb_n > 0 else env_trust
    exp_val = exp_data if fb_n > 0 else env_exp

    if trust_val is not None:
        t_num = f"{trust_val:.0f}<span style='font-size:0.55em;font-weight:700;opacity:0.85'>%</span>"
        t_foot = "% of responses with 4–5★ overall."
        if fb_n:
            t_foot += f" <strong>{fb_n}</strong> response(s)."
        else:
            t_foot += " Configured highlight."
        t_dim = False
    else:
        t_num = "—"
        t_foot = (
            "No data yet — use Feedback after sign-in, or set "
            "<code>HIRERESUME_LOGIN_SPOTLIGHT_TRUST_PCT</code>."
        )
        t_dim = True

    if exp_val is not None:
        e_num = f"{exp_val:.0f}<span style='font-size:0.5em;font-weight:700;opacity:0.8'>/100</span>"
        e_foot = "Blend of rating, ease of use, and feature satisfaction."
        if fb_n:
            e_foot += f" <strong>{fb_n}</strong> response(s)."
        else:
            e_foot += " Configured highlight."
        e_dim = False
    else:
        e_num = "—"
        e_foot = (
            "No data yet — use Feedback after sign-in, or set "
            "<code>HIRERESUME_LOGIN_SPOTLIGHT_EXPERIENCE_PCT</code>."
        )
        e_dim = True

    def cell(dim: bool, kicker: str, num: str, foot: str) -> str:
        cls = "hire-ls-card" + (" hire-ls-card-dim" if dim else "")
        return f"""<div class="{cls}">
            <div class="hire-ls-kicker">{kicker}</div>
            <div class="hire-ls-num">{num}</div>
            <div class="hire-ls-foot">{foot}</div>
        </div>"""

    st.markdown(
        f"""
        <style>
        .hire-ls-wrap {{ margin-top: 0.35rem; }}
        .hire-ls-title {{
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--text);
            margin: 0 0 0.15rem 0;
            letter-spacing: -0.02em;
        }}
        .hire-ls-sub {{
            font-size: 0.78rem;
            color: var(--muted);
            margin: 0 0 0.85rem 0;
            line-height: 1.45;
        }}
        .hire-ls-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.85rem;
        }}
        @media (max-width: 640px) {{
            .hire-ls-grid {{ grid-template-columns: 1fr; }}
        }}
        .hire-ls-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 1rem 1.1rem 1.05rem;
            border-left: 4px solid #22c55e;
            box-shadow: 0 6px 28px rgba(0, 0, 0, 0.12);
        }}
        .hire-ls-card-dim {{
            border-left-color: rgba(148, 163, 184, 0.55);
        }}
        .hire-ls-kicker {{
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            color: var(--muted);
            font-weight: 700;
            margin-bottom: 0.35rem;
        }}
        .hire-ls-num {{
            font-size: clamp(1.85rem, 4.2vw, 2.45rem);
            font-weight: 800;
            color: var(--text);
            line-height: 1.05;
            letter-spacing: -0.03em;
        }}
        .hire-ls-foot {{
            font-size: 0.78rem;
            color: var(--muted);
            margin-top: 0.5rem;
            line-height: 1.4;
        }}
        </style>
        <div class="hire-ls-wrap">
            <p class="hire-ls-title">Community snapshot</p>
            <p class="hire-ls-sub">Trust and experience scores from this app’s <strong>Feedback</strong> page — large type for quick reading.</p>
            <div class="hire-ls-grid">
                {cell(t_dim, "Trust signal", t_num, t_foot)}
                {cell(e_dim, "Experience score", e_num, e_foot)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    bits = []
    if fb_n:
        bits.append(f"{fb_n} feedback response(s)")
    if ai_n:
        bits.append(
            f"{ai_n} AI analysis run(s)"
            + (f", mean resume score {ai_avg:.0f}/100" if ai_avg else "")
        )
    if bits:
        st.caption(" · ".join(bits))
    elif not trust_val and not exp_val:
        st.caption(
            "Optional env: `HIRERESUME_LOGIN_SPOTLIGHT_TRUST_PCT` and "
            "`HIRERESUME_LOGIN_SPOTLIGHT_EXPERIENCE_PCT` (see `.env.example`)."
        )
