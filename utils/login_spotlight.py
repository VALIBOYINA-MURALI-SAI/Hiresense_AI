"""
In-app social proof for the OAuth login / landing column: no external form required.
Uses feedback/feedback.db and main SQLite stats (resume + AI analyses).
Optional env fallbacks when counts are zero — set explicitly; never invented by code.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import streamlit as st

from config.database import get_ai_analysis_stats, get_database_connection


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


def _standard_analysis_count_avg_ats() -> tuple[int, float | None]:
    conn = get_database_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='resume_analysis'"
        )
        if not cur.fetchone():
            return 0, None
        cur.execute("SELECT COUNT(*), AVG(ats_score) FROM resume_analysis")
        row = cur.fetchone()
        cnt = int(row[0] or 0)
        avg = row[1]
        if cnt == 0:
            return 0, None
        return cnt, round(float(avg), 1)
    except Exception:
        return 0, None
    finally:
        conn.close()


def render_login_spotlight_block() -> None:
    """Metrics card for the sign-in landing column (Streamlit)."""
    fb_n, trust_data, exp_data = _load_feedback_aggregates()
    std_n, avg_ats = _standard_analysis_count_avg_ats()
    ai_stats = get_ai_analysis_stats()
    ai_n = int(ai_stats.get("total_analyses") or 0)
    ai_avg = float(ai_stats.get("average_score") or 0)

    # Optional display overrides when you have no rows yet (you set these explicitly).
    env_trust = _spotlight_float(
        "HIRERESUME_LOGIN_SPOTLIGHT_TRUST_PCT",
        "hireresume_login_spotlight_trust_pct",
    )
    env_exp = _spotlight_float(
        "HIRERESUME_LOGIN_SPOTLIGHT_EXPERIENCE_PCT",
        "hireresume_login_spotlight_experience_pct",
    )
    env_ats = _spotlight_float(
        "HIRERESUME_LOGIN_SPOTLIGHT_AVG_ATS",
        "hireresume_login_spotlight_avg_ats",
    )

    trust_val = trust_data if fb_n > 0 else env_trust
    exp_val = exp_data if fb_n > 0 else env_exp
    ats_val = avg_ats if std_n > 0 else env_ats

    st.markdown("**Community snapshot**")
    st.caption(
        "Pulled from this app’s **Feedback** page and **saved resume analyses** on this server."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        if trust_val is not None:
            st.metric(
                label="Trust signal",
                value=f"{trust_val:.0f}%",
                help="Share of in-app feedback with overall rating 4★ or 5★. "
                "Or set HIRERESUME_LOGIN_SPOTLIGHT_TRUST_PCT when you have no responses yet.",
            )
        else:
            st.metric(label="Trust signal", value="—", help="Submit feedback in-app to populate.")
    with c2:
        if exp_val is not None:
            st.metric(
                label="Experience score",
                value=f"{exp_val:.0f}/100",
                help="From average of rating, usability, and satisfaction (1–5 each), scaled to 100. "
                "Or HIRERESUME_LOGIN_SPOTLIGHT_EXPERIENCE_PCT.",
            )
        else:
            st.metric(label="Experience score", value="—", help="Submit feedback in-app to populate.")
    with c3:
        if ats_val is not None:
            st.metric(
                label="Avg. ATS (standard)",
                value=f"{ats_val:.0f}",
                help="Mean ATS score across saved standard analyses on this server. "
                "Or HIRERESUME_LOGIN_SPOTLIGHT_AVG_ATS.",
            )
        else:
            st.metric(
                label="Avg. ATS (standard)",
                value="—",
                help="Run the standard analyzer and save, or set HIRERESUME_LOGIN_SPOTLIGHT_AVG_ATS.",
            )

    bits = []
    if fb_n:
        bits.append(f"**{fb_n}** feedback response(s)")
    if std_n:
        bits.append(f"**{std_n}** standard analysis record(s)")
    if ai_n:
        bits.append(
            f"**{ai_n}** AI analysis run(s){f', mean resume score **{ai_avg:.0f}**/100' if ai_avg else ''}"
        )
    if bits:
        st.caption(" · ".join(bits))
    else:
        st.caption(
            "No feedback or analyses stored yet. Use **Feedback** after sign-in, or set optional "
            "`HIRERESUME_LOGIN_SPOTLIGHT_*` env vars for static highlights (see `.env.example`)."
        )
