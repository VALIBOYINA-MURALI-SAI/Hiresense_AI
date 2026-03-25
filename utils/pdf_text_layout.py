"""
Layout-aware PDF text extraction for resumes.

Plain extract_text() often follows PDF content stream order, which breaks for
multi-column and floating headers. This module orders words by visual position.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional

import pdfplumber


def _words_to_lines(
    words: List[Dict[str, Any]], y_tolerance: float = 4.0
) -> List[str]:
    """Group word dicts (pdfplumber) into lines, left-to-right within each line."""
    if not words:
        return []
    # Stable visual order: scan top-to-bottom, then left-to-right
    sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    line_anchor_top: Optional[float] = None

    for w in sorted_words:
        top = float(w["top"])
        if line_anchor_top is None or abs(top - line_anchor_top) <= y_tolerance:
            current.append(w)
            if line_anchor_top is None:
                line_anchor_top = top
            else:
                line_anchor_top = (line_anchor_top + top) / 2.0
        else:
            current.sort(key=lambda x: x["x0"])
            lines.append(" ".join(t["text"] for t in current))
            current = [w]
            line_anchor_top = top

    if current:
        current.sort(key=lambda x: x["x0"])
        lines.append(" ".join(t["text"] for t in current))

    return lines


def _page_text_reading_order(
    page: pdfplumber.page.Page,
    two_column: bool = False,
    y_tolerance: float = 4.0,
) -> str:
    words = page.extract_words(
        x_tolerance=3,
        y_tolerance=3,
        keep_blank_chars=False,
    )
    if not words:
        t = page.extract_text()
        return (t or "").strip()

    width = float(page.width or 0)

    if two_column and width > 0:
        mid = width / 2.0
        left = [
            w
            for w in words
            if (float(w["x0"]) + float(w["x1"])) / 2.0 < mid
        ]
        right = [
            w
            for w in words
            if (float(w["x0"]) + float(w["x1"])) / 2.0 >= mid
        ]
        left_lines = _words_to_lines(left, y_tolerance=y_tolerance)
        right_lines = _words_to_lines(right, y_tolerance=y_tolerance)
        return "\n".join(left_lines + [""] + right_lines).strip()

    return "\n".join(_words_to_lines(words, y_tolerance=y_tolerance)).strip()


def extract_resume_text_layout_pdfplumber(
    pdf_path: str,
    *,
    two_column: bool = False,
    y_tolerance: float = 4.0,
) -> Tuple[str, Dict[str, Any]]:
    """
    Extract full document text with reading-order layout per page.

    Returns:
        (full_text, metadata) where metadata includes page count and flags.
    """
    meta: Dict[str, Any] = {
        "method": "pdfplumber_layout",
        "two_column": two_column,
        "pages": 0,
    }
    chunks: List[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        meta["pages"] = len(pdf.pages)
        for page in pdf.pages:
            chunk = _page_text_reading_order(
                page, two_column=two_column, y_tolerance=y_tolerance
            )
            if chunk:
                chunks.append(chunk)

    return "\n\n".join(chunks).strip(), meta


def _line_span_ratio_mid(
    words: List[Dict[str, Any]], page_mid_x: float, line_y_quantum: float = 4.0
) -> Tuple[float, int]:
    """
    Fraction of text lines whose bounding box crosses page_mid_x (full-width flow).
    True two-column resumes usually have a low span ratio; single-column + right-aligned
    dates still produce many spanning lines.
    """
    by_y: Dict[float, List[Dict[str, Any]]] = defaultdict(list)
    for w in words:
        key = round(float(w["top"]) / line_y_quantum) * line_y_quantum
        by_y[key].append(w)

    span_mid = 0
    total_lines = 0
    for group in by_y.values():
        if not group:
            continue
        x0s = [float(w["x0"]) for w in group]
        x1s = [float(w["x1"]) for w in group]
        mn, mx = min(x0s), max(x1s)
        total_lines += 1
        if mn < page_mid_x < mx:
            span_mid += 1

    if total_lines == 0:
        return 1.0, 0
    return span_mid / total_lines, total_lines


def detect_likely_two_column_page(page: pdfplumber.page.Page) -> bool:
    """
    Detect visual two-column layouts without misclassifying single-column resumes that
    happen to place many words in the right half (e.g. right-aligned dates).

    Uses (1) fraction of lines that cross the horizontal midline and (2) rough
    left/right balance of word centers.
    """
    words = page.extract_words(
        x_tolerance=3,
        y_tolerance=3,
        keep_blank_chars=False,
    )
    if len(words) < 12:
        return False
    width = float(page.width or 0)
    if width <= 0:
        return False
    mid = width / 2.0

    span_ratio, line_count = _line_span_ratio_mid(words, mid)
    if line_count < 6:
        return False
    # Single-column body text: most lines span the full content width across mid.
    # (~0.35 leaves margin below typical single-column continuations that are ~0.36.)
    if span_ratio > 0.34:
        return False

    centers = [(float(w["x0"]) + float(w["x1"])) / 2.0 for w in words]
    right_share = sum(1 for c in centers if c >= mid) / len(centers)
    if not (0.22 <= right_share <= 0.78):
        return False

    return True


def extract_resume_text_adaptive_columns(pdf_path: str) -> Tuple[str, Dict[str, Any]]:
    """
    Per page: use two-column ordering only when heuristic fires; else single column.
    """
    meta: Dict[str, Any] = {
        "method": "pdfplumber_layout_adaptive",
        "pages": 0,
        "two_column_pages": [],
    }
    chunks: List[str] = []
    two_column_pages: List[int] = []

    with pdfplumber.open(pdf_path) as pdf:
        meta["pages"] = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            use_2 = detect_likely_two_column_page(page)
            if use_2:
                two_column_pages.append(i + 1)
            chunk = _page_text_reading_order(
                page, two_column=use_2, y_tolerance=4.0
            )
            if chunk:
                chunks.append(chunk)

    meta["two_column_pages"] = two_column_pages
    return "\n\n".join(chunks).strip(), meta
