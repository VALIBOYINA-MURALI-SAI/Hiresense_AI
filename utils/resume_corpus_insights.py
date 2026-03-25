"""
Aggregate skill terms from local resume exports (SQLite + Excel) to widen
lexicons used by analyzers without hard-coding every synonym.

Sources (merged):
  - resume_analysis.db: skills_tracking.skill, resume_analysis.skills (JSON array)
  - resume_data.db: resume_skills.skill_name
  - Excel: **resume_data_export.xlsx** (case-insensitive) if present, else newest **resume_data_export*.xlsx**

Override root with env RESUME_CORPUS_ROOT (defaults to parent of this package).
"""

from __future__ import annotations

import ast
import json
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Counter as CounterType, Dict, FrozenSet, Iterable, List, Optional, Set

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Multi-word phrases to detect in text / allow as single lexicon entries
_EXTRA_BIGRAMS = frozenset(
    {
        "machine learning",
        "deep learning",
        "data science",
        "computer vision",
        "natural language",
        "power bi",
        "ms excel",
        "node.js",
        "next.js",
        "vue.js",
        "html/css",
    }
)

# Case-insensitive boundary scan for known tech tokens in messy export text
_SEED_PATTERN = re.compile(
    r"\b(?:"
    r"c\+\+|c#|\.net|node\.js|next\.js|vue\.js|angular\.js|three\.js|"
    r"javascript|typescript|python|java|kotlin|swift|dart|ruby|go|rust|php|"
    r"sql|mysql|postgresql|mongodb|redis|graphql|rest|api|aws|gcp|azure|"
    r"docker|kubernetes|jenkins|git|github|gitlab|terraform|ansible|"
    r"react|angular|vue|django|flask|fastapi|spring|express|pandas|numpy|"
    r"tensorflow|pytorch|keras|scikit|opencv|nlp|iam|etl|excel|tableau|"
    r"html|css|sass|tailwind|bootstrap|linux|unix|bash|powershell|"
    r"cybersecurity|blockchain|figma|jira|selenium|android|ios"
    r")\b",
    re.IGNORECASE,
)

_JUNK_PREFIXES = (
    "aggregate:",
    "key skills:",
    "aspiring to",
    "showcasing the",
    "delivered comprehensive",
    "i am a dedicated",
    "i am a ",
    "world problem",
    "parul university",
    "skil",
)

# Drop noisy fragments from messy Excel exports (full phrases, not skill tokens)
_JUNK_SUBSTRINGS = (
    " university",
    " aspiring",
    " showcasing",
    " delivered",
    " comprehensive",
    " teamwork skills",
    " strategic alignment",
    " acquired expertise",
    " real-world",
    " real world",
    " internship in",
    " where i can",
    " solve real",
    " best practices",
    "capabilities",
    " gujarati",
    "hindi and",
)

_SOFT_SKILL_STOPWORDS = frozenset(
    {
        "leader",
        "adaptable",
        "collaborator",
        "communicator",
        "innovative",
        "motivated",
    }
)

# Exclude from role priors (corpus noise, not checklist skills)
_ROLE_PRIOR_STOPWORDS = frozenset(
    {
        "analytical",
        "brute force",
        "vulnerabilities",
        "communication",
        "teamwork",
        "problem solving",
        "problem-solving",
    }
)


def _corpus_root() -> Path:
    raw = os.environ.get("RESUME_CORPUS_ROOT", "").strip()
    return Path(raw).resolve() if raw else _PROJECT_ROOT


def _preferred_export_xlsx_path(root: Path) -> Optional[Path]:
    """
    Prefer canonical resume_data_export.xlsx (case-insensitive) when present;
    otherwise use the newest resume_data_export*.xlsx by modification time.
    """
    candidates = list(root.glob("resume_data_export*.xlsx"))
    if not candidates:
        return None
    for p in candidates:
        if p.name.lower() == "resume_data_export.xlsx":
            return p
    return max(candidates, key=lambda q: q.stat().st_mtime)


def _export_cache_token(root: Path) -> tuple:
    p = _preferred_export_xlsx_path(root)
    if p is None:
        return ("", None)
    return (str(p.resolve()), p.stat().st_mtime)


def _safe_connect(path: Path) -> Optional[sqlite3.Connection]:
    if not path.is_file():
        return None
    try:
        return sqlite3.connect(str(path))
    except sqlite3.Error:
        return None


def _add_counter(target: CounterType[str], items: Iterable[str]) -> None:
    for raw in items:
        if not raw or not isinstance(raw, str):
            continue
        s = raw.strip().lower()
        if 1 < len(s) <= 48:
            target[s] += 1


def _from_skills_tracking(conn: sqlite3.Connection) -> CounterType[str]:
    c: CounterType[str] = Counter()
    try:
        cur = conn.cursor()
        cur.execute("SELECT skill FROM skills_tracking WHERE skill IS NOT NULL")
        _add_counter(c, (row[0] for row in cur.fetchall()))
    except sqlite3.Error:
        pass
    return c


def _from_resume_analysis_skills_column(conn: sqlite3.Connection) -> CounterType[str]:
    c: CounterType[str] = Counter()
    try:
        cur = conn.cursor()
        cur.execute("SELECT skills FROM resume_analysis WHERE skills IS NOT NULL")
        for (blob,) in cur.fetchall():
            if not blob:
                continue
            try:
                arr = json.loads(blob)
                if isinstance(arr, list):
                    _add_counter(c, (str(x) for x in arr))
            except (json.JSONDecodeError, TypeError):
                continue
    except sqlite3.Error:
        pass
    return c


def _from_resume_skills_table(conn: sqlite3.Connection) -> CounterType[str]:
    c: CounterType[str] = Counter()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='resume_skills'"
        )
        if not cur.fetchone():
            return c
        cur.execute("SELECT skill_name FROM resume_skills WHERE skill_name IS NOT NULL")
        _add_counter(c, (row[0] for row in cur.fetchall()))
    except sqlite3.Error:
        pass
    return c


def _clean_excel_fragment(s: str) -> Optional[str]:
    s = s.strip()
    if len(s) < 2 or len(s) > 40:
        return None
    low = s.lower()
    if any(low.startswith(p) for p in _JUNK_PREFIXES):
        return None
    if low.count(" ") > 5:
        return None
    if sum(ch.isalpha() for ch in s) < 2:
        return None
    return low


def _from_excel_export(root: Path) -> CounterType[str]:
    c: CounterType[str] = Counter()
    path = _preferred_export_xlsx_path(root)
    if path is None:
        return c
    try:
        import pandas as pd
    except ImportError:
        return c

    try:
        df = pd.read_excel(path, sheet_name=0)
    except Exception:
        return c

    if "skills" not in df.columns:
        return c

    blob = " ".join(str(x) for x in df["skills"].dropna().tolist())
    for m in _SEED_PATTERN.finditer(blob):
        c[m.group(0).strip().lower()] += 1

    for cell in df["skills"].dropna():
        text = str(cell).strip()
        if not text or text == "nan":
            continue
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = ast.literal_eval(text)
                if isinstance(parsed, list):
                    _add_counter(c, (str(x) for x in parsed))
                    continue
            except (ValueError, SyntaxError):
                pass
        for part in text.split(","):
            frag = _clean_excel_fragment(part)
            if frag:
                c[frag] += 1

    return c


def collect_skill_term_counts(root: Optional[Path] = None) -> CounterType[str]:
    root = root or _corpus_root()
    total: CounterType[str] = Counter()

    ra = _safe_connect(root / "resume_analysis.db")
    if ra:
        total.update(_from_skills_tracking(ra))
        total.update(_from_resume_analysis_skills_column(ra))
        ra.close()

    rd = _safe_connect(root / "resume_data.db")
    if rd:
        total.update(_from_resume_skills_table(rd))
        rd.close()

    total.update(_from_excel_export(root))
    return total


def _is_plausible_skill_term(k: str) -> bool:
    if len(k) > 36 or len(k) < 2:
        return False
    if k.count(" ") > 3:
        return False
    if any(b in k for b in _JUNK_SUBSTRINGS):
        return False
    if ":" in k:
        return False
    if k.endswith("."):
        return False
    if k in _SOFT_SKILL_STOPWORDS:
        return False
    return True


def build_corpus_skill_lexicon(
    *,
    root: Optional[Path] = None,
    min_count: int = 1,
    max_terms: int = 400,
) -> FrozenSet[str]:
    """
    Return normalized lowercase skill strings suitable for substring/token matching.
    """
    counts = collect_skill_term_counts(root)
    filtered = Counter()
    for k, v in counts.items():
        if v < min_count or not _is_plausible_skill_term(k):
            continue
        # Excel noise: multi-word phrases need at least 2 occurrences unless from regex seeds
        if k.count(" ") >= 2 and v < 2:
            continue
        filtered[k] = v
    terms = [k for k, _ in filtered.most_common(max_terms)]
    base = set(terms)
    base.update(_EXTRA_BIGRAMS)
    return frozenset(base)


_cached_lexicon: Optional[FrozenSet[str]] = None
_cached_sig: Optional[tuple] = None


def get_corpus_skill_lexicon(
    *,
    root: Optional[Path] = None,
    force_reload: bool = False,
) -> FrozenSet[str]:
    """
    Cached lexicon keyed by mtimes of DB/XLSX sources so edits refresh automatically.
    """
    global _cached_lexicon, _cached_sig
    root = root or _corpus_root()
    ra = root / "resume_analysis.db"
    rd = root / "resume_data.db"
    sig = (
        (str(ra), ra.stat().st_mtime if ra.is_file() else None),
        (str(rd), rd.stat().st_mtime if rd.is_file() else None),
        _export_cache_token(root),
    )
    if not force_reload and _cached_lexicon is not None and _cached_sig == sig:
        return _cached_lexicon
    _cached_lexicon = build_corpus_skill_lexicon(root=root)
    _cached_sig = sig
    return _cached_lexicon


def merge_skill_lexicon(
    base: Set[str],
    *,
    root: Optional[Path] = None,
) -> Set[str]:
    """Union of base (lowercase strings) and corpus-derived terms."""
    out = {s.lower() for s in base}
    out.update(get_corpus_skill_lexicon(root=root))
    return out


def extract_skill_tokens_from_excel_cell(cell) -> List[str]:
    """Pull skill-like tokens from one Excel `skills` cell (regex + comma split)."""
    out: List[str] = []
    if cell is None:
        return out
    if isinstance(cell, float) and cell != cell:
        return out
    text = str(cell).strip()
    if not text or text.lower() == "nan":
        return out
    for m in _SEED_PATTERN.finditer(text):
        out.append(m.group(0).strip().lower())
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                for x in parsed:
                    xs = str(x).strip().lower()
                    if xs and xs != "nan":
                        out.append(xs)
                return _dedupe_preserve_order(out)
        except (ValueError, SyntaxError):
            pass
    for part in text.split(","):
        frag = _clean_excel_fragment(part)
        if frag:
            out.append(frag)
    return _dedupe_preserve_order(out)


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    res: List[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


def _normalize_role_name(raw: str) -> str:
    s = re.sub(r"\s+", " ", str(raw or "").strip().lower())
    if not s or s == "nan":
        return ""
    s = (
        s.replace("front-end", "frontend")
        .replace("back-end", "backend")
        .replace("full-stack", "full stack")
    )
    s = s.replace("front end", "frontend").replace("back end", "backend")
    return s


def build_role_skill_priors_map(root: Optional[Path] = None) -> Dict[str, CounterType[str]]:
    """target_role (normalized) -> Counter of canonical skill terms from export rows."""
    from utils.skill_normalization import normalize_skill_term

    root = root or _corpus_root()
    xlsx = _preferred_export_xlsx_path(root)
    if xlsx is None:
        return {}
    try:
        import pandas as pd
    except ImportError:
        return {}
    try:
        df = pd.read_excel(xlsx, sheet_name=0)
    except Exception:
        return {}
    if "target_role" not in df.columns or "skills" not in df.columns:
        return {}
    priors: Dict[str, CounterType[str]] = {}
    for _, row in df.iterrows():
        role = _normalize_role_name(row.get("target_role", ""))
        if not role:
            continue
        toks = extract_skill_tokens_from_excel_cell(row.get("skills"))
        if role not in priors:
            priors[role] = Counter()
        for t in toks:
            c = normalize_skill_term(t)
            if not c or not _is_plausible_skill_term(c):
                continue
            priors[role][c] += 1
    return priors


def _pick_role_counter(
    priors: Dict[str, CounterType[str]], role: str
) -> tuple[Optional[CounterType[str]], Optional[str]]:
    """
    Use exact normalized role keys only. Fuzzy substring matching mixed skill buckets
    (e.g. *developer* matching the wrong role) and produced unrelated priors.
    """
    r = _normalize_role_name(role)
    if not r or not priors:
        return None, None
    if r in priors:
        return priors[r], r
    return None, None


_cached_role_priors: Optional[Dict[str, CounterType[str]]] = None
_cached_role_sig: Optional[tuple] = None


def get_role_skill_priors_map(
    *,
    root: Optional[Path] = None,
    force_reload: bool = False,
) -> Dict[str, CounterType[str]]:
    global _cached_role_priors, _cached_role_sig
    root = root or _corpus_root()
    sig = (_export_cache_token(root),)
    if not force_reload and _cached_role_priors is not None and _cached_role_sig == sig:
        return _cached_role_priors
    _cached_role_priors = build_role_skill_priors_map(root)
    _cached_role_sig = sig
    return _cached_role_priors


def get_role_prior_skill_labels(
    role_name: str,
    *,
    top_n: int = 12,
    min_observations: int = 2,
    allowed_canonicals: Optional[Set[str]] = None,
    root: Optional[Path] = None,
) -> tuple[List[str], dict]:
    """
    Top skill labels from the Excel export for this target_role (exact role key match).

    - min_observations: ignore skills that appear only once for that role (noisy cells).
    - allowed_canonicals: if set, only skills in this vocabulary (from JOB_ROLES) are kept.
    """
    from utils.skill_normalization import display_skill, normalize_skill_term

    priors = get_role_skill_priors_map(root=root)
    ctr, matched_key = _pick_role_counter(priors, role_name or "")
    meta: dict = {
        "matched_corpus_role": matched_key,
        "distinct_skills": len(ctr) if ctr else 0,
        "prior_min_observations": min_observations,
        "prior_vocab_filtered": allowed_canonicals is not None,
    }
    if not ctr:
        return [], meta
    labels: List[str] = []
    seen: Set[str] = set()
    for canon, obs_count in ctr.most_common(top_n * 8):
        if obs_count < min_observations:
            continue
        cn = normalize_skill_term(canon)
        if not cn or cn in seen or cn in _ROLE_PRIOR_STOPWORDS:
            continue
        if allowed_canonicals is not None and cn not in allowed_canonicals:
            continue
        seen.add(cn)
        labels.append(display_skill(cn))
        if len(labels) >= top_n:
            break
    return labels, meta


def get_export_score_summary(root: Optional[Path] = None) -> Optional[dict]:
    """
    Simple stats from the newest resume_data_export*.xlsx (if present):
    row count, mean ATS / keyword / format when columns exist.
    """
    root = root or _corpus_root()
    path = _preferred_export_xlsx_path(root)
    if path is None:
        return None
    try:
        import pandas as pd
    except ImportError:
        return None
    try:
        df = pd.read_excel(path, sheet_name=0)
    except Exception:
        return None
    out: dict = {"export_file": path.name, "rows": len(df)}
    for col in ("ats_score", "keyword_match_score", "format_score", "section_score"):
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(s):
                out[f"{col}_mean"] = round(float(s.mean()), 2)
                out[f"{col}_median"] = round(float(s.median()), 2)
    return out
