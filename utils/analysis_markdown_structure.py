"""
Post-process AI resume analysis markdown: turn dense paragraphs into structured lists.

Does not change the LLM prompt; runs on the final response string before UI/PDF.
"""
from __future__ import annotations

import re


def structure_analysis_markdown(text: str) -> str:
    if not text or not str(text).strip():
        return text
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")

    # Split into ## sections; keep preamble before first ##
    first_h2 = re.search(r"^## .+$", text, flags=re.MULTILINE)
    if not first_h2:
        return _structure_body(text)

    head = text[: first_h2.start()].rstrip()
    rest = text[first_h2.start() :]
    blocks: list[str] = []
    if head:
        blocks.append(_structure_body(head))

    for m in re.finditer(
        r"^(## [^\n]+)\n([\s\S]*?)(?=^## |\Z)",
        rest,
        flags=re.MULTILINE,
    ):
        title = m.group(1).strip()
        body = m.group(2).strip()
        blocks.append(title + "\n\n" + _structure_body(body, section_heading=title))

    out = "\n\n".join(b for b in blocks if b)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = out.strip()
    out = _inline_bold_to_html(out)
    return out


def _inline_bold_to_html(text: str) -> str:
    """Turn **label** into <strong> so report HTML shows emphasis (prompt unchanged)."""
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)


def _structure_body(body: str, section_heading: str = "") -> str:
    s = body.strip()
    if not s:
        return s

    # Repeated passes so multiple glued markers on one line get split
    for _ in range(12):
        prev = s

        # Inline "- **Label**:" bullets (Skills Analysis, etc.)
        s = re.sub(
            r"([^\n#])(\s+-\s+\*\*[^*]+\*\*\s*[:：]?)",
            r"\1\n\2",
            s,
        )

        # Sub-bullets "* **Category**:" (Technical / Soft / Domain)
        s = re.sub(
            r"([^\n])(\s*\*\s+\*\*[^*]+\*\*\s*[:：])",
            r"\1\n\2",
            s,
        )

        # Numbered items like "1. **Summary:**" mid-paragraph (Role Alignment style)
        s = re.sub(
            r"([^\n\d])(\s*\d+\.\s+\*\*[^*]+\*\*)",
            r"\1\n\2",
            s,
        )
        # Second numbered item glued after first: "...text. 2. **Next**"
        s = re.sub(
            r"([a-zA-Z0-9.)])(\s+\d+\.\s+\*\*[^*]+\*\*)",
            r"\1\n\2",
            s,
        )
        # Numbered without bold: "2. Skills Section:" (avoid version numbers like 3.14)
        s = re.sub(
            r"(?<![0-9.])([^\n\d])(\s*\d+\.\s+[A-Z][^:\n]{0,120}:)",
            r"\1\n\2",
            s,
        )

        # Standalone **Subsection:** headers (Concrete edits, etc.)
        s = re.sub(
            r"([^\n])(\s*\*\*(?:Concrete edits|Summary|Action items)[^*]*\*\*\s*[:：]?\s*)",
            r"\1\n\n\2",
            s,
            flags=re.IGNORECASE,
        )

        # **Add:** / **Example:** / **Prioritize:** style labels
        s = re.sub(
            r"([^\n])(\s+\*\*(?:Add|Remove|Prioritize|Example|Mention|Rewrite|De-emphasize|Include)[^*]{0,48}\*\*[:：])",
            r"\1\n\2",
            s,
            flags=re.IGNORECASE,
        )

        # Hollow / unicode bullets mid-line
        s = re.sub(r"([^\n])(\s*[•◦]\s+)", r"\1\n\2", s)

        # New sentence then "- " plain bullet (not **)
        s = re.sub(r"([.!?])\s+(-\s+(?!\*\*)[^\n]+)", r"\1\n\2", s)

        if s == prev:
            break

    # Indent continuation: line after "- **Current Skills**:" that starts with * gets blank line before block
    s = re.sub(r"(^-\s+\*\*[^\n]+\n)(?=\*)", r"\1\n", s, flags=re.MULTILINE)

    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()
