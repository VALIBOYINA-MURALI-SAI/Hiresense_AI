"""
Canonical skill labels + aliases for resume ↔ job keyword matching (Option C).

All canonical forms are lowercase single strings; matching expands to known aliases.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, FrozenSet, Iterable, List, Set

# alias (lowercase, stripped) -> canonical key
_SKILL_ALIASES: Dict[str, str] = {
    "js": "javascript",
    "ecmascript": "javascript",
    "py": "python",
    "python3": "python",
    "ts": "typescript",
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue.js",
    "vue": "vue.js",
    "nodejs": "node.js",
    "node": "node.js",
    "angularjs": "angular",
    "angular.js": "angular",
    "postgres": "postgresql",
    "tf": "tensorflow",
    "pytorch": "pytorch",
    "torch": "pytorch",
    "k8s": "kubernetes",
    "golang": "go",
    "gcp": "google cloud",
    "google cloud platform": "google cloud",
    "ms excel": "excel",
    "powerbi": "power bi",
    "kubenetes": "kubernetes",
    "mongo": "mongodb",
    "html5": "html",
    "css3": "css",
    "c sharp": "c#",
    "csharp": "c#",
    "cpp": "c++",
    "cplusplus": "c++",
    "c / c++": "c/c++",
    "c/c++": "c/c++",
    "machine-learning": "machine learning",
    "deep-learning": "deep learning",
    "data-science": "data science",
    "nlp": "natural language processing",
    "natural language": "natural language processing",
}

# Extra resume phrases for short canonical IDs
_CANON_EXTRA_PHRASES: Dict[str, FrozenSet[str]] = {
    "iam": frozenset(
        {"iam", "identity and access management", "identity and access"}
    ),
}

_SPECIAL_DISPLAY = {
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "python": "Python",
    "java": "Java",
    "node.js": "Node.js",
    "vue.js": "Vue.js",
    "react": "React",
    "angular": "Angular",
    "c++": "C++",
    "c#": "C#",
    "c/c++": "C/C++",
    "sql": "SQL",
    "html": "HTML",
    "css": "CSS",
    "aws": "AWS",
    "gcp": "GCP",
    "api": "APIs",
    "apis": "APIs",
    "ui/ux": "UI/UX",
    "natural language processing": "NLP",
    "iam": "IAM",
    "google cloud": "Google Cloud",
    "power bi": "Power BI",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "data science": "Data Science",
}


def _clean_raw(s: str) -> str:
    t = (s or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t.strip(".,;:|• \t\r\n")


def normalize_skill_term(raw: str) -> str:
    """Map surface form to canonical lowercase skill id."""
    s = _clean_raw(raw)
    if not s:
        return ""
    if s in _SKILL_ALIASES:
        return _SKILL_ALIASES[s]
    return s


@lru_cache(maxsize=512)
def expand_resume_search_phrases(canonical: str) -> FrozenSet[str]:
    """All lowercase substrings / tokens to search for in resume text."""
    c = normalize_skill_term(canonical)
    if not c:
        return frozenset()
    out: Set[str] = {c}
    for alias, can in _SKILL_ALIASES.items():
        if can == c:
            out.add(alias)
    out.update(_CANON_EXTRA_PHRASES.get(c, frozenset()))
    return frozenset(out)


def display_skill(canonical_lower: str) -> str:
    """Human-readable label for UI (from canonical key)."""
    if not canonical_lower:
        return ""
    if canonical_lower in _SPECIAL_DISPLAY:
        return _SPECIAL_DISPLAY[canonical_lower]
    return canonical_lower.replace("_", " ").title()


def text_contains_skill(resume_text_lower: str, phrase: str) -> bool:
    """Avoid false positives for very short tokens (e.g. Go, R, C)."""
    if not phrase or not resume_text_lower:
        return False
    pl = phrase.lower()
    if len(pl) <= 2:
        return re.search(rf"(?<!\w){re.escape(pl)}(?!\w)", resume_text_lower) is not None
    if pl in ("c++", "c#", "r"):
        return re.search(rf"(?<!\w){re.escape(pl)}(?!\w)", resume_text_lower) is not None
    return pl in resume_text_lower


def build_allowed_canonicals_for_job_role(job_requirements: dict) -> FrozenSet[str]:
    """
    Skill vocabulary from the selected JOB_ROLES entry (required + recommended technical).
    Corpus priors are intersected with this set so Excel export noise (random tech mentions
    in messy cells) does not inflate unrelated skills for a role.
    """
    out: Set[str] = set()
    for x in job_requirements.get("required_skills", []):
        n = normalize_skill_term(str(x))
        if n:
            out.add(n)
            out.update(expand_resume_search_phrases(n))
    rec = job_requirements.get("recommended_skills") or {}
    tech = rec.get("technical")
    if isinstance(tech, list):
        for blob in tech:
            text = str(blob).lower()
            for part in re.split(r"[/,&]| or | and ", text):
                p = normalize_skill_term(part.strip(" -\t"))
                if p and len(p) > 1:
                    out.add(p)
                    out.update(expand_resume_search_phrases(p))
    out.discard("")
    return frozenset(out)


def match_required_skills_against_resume(
    resume_text: str, required_skill_labels: Iterable[str]
) -> tuple[List[str], List[str], List[dict]]:
    """
    Returns (found_labels, missing_labels, details) using normalization + aliases.
    Labels in output preserve the wording from required_skill_labels where possible.
    """
    resume_lower = resume_text.lower()
    found: List[str] = []
    missing: List[str] = []
    details: List[dict] = []

    for label in required_skill_labels:
        canon = normalize_skill_term(str(label))
        phrases = expand_resume_search_phrases(canon) if canon else frozenset()
        hit = any(text_contains_skill(resume_lower, p) for p in phrases) if phrases else False
        details.append(
            {
                "requested": label,
                "canonical": canon,
                "matched": hit,
            }
        )
        if hit:
            found.append(label)
        else:
            missing.append(label)

    return found, missing, details
