"""
Regression tests for layout-aware PDF extraction (Option B).

Looks for sample PDFs at repo root or under tests/fixtures/resumes/.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import pdfplumber

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_pdf_layout_module():
    path = REPO_ROOT / "utils" / "pdf_text_layout.py"
    spec = importlib.util.spec_from_file_location("pdf_text_layout", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


pdf_text_layout = _load_pdf_layout_module()


def _fixture(name: str) -> Path | None:
    for base in (
        REPO_ROOT / "tests" / "fixtures" / "resumes",
        REPO_ROOT,
    ):
        p = base / name
        if p.is_file():
            return p
    return None


class TestPdfTextLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resume_single = _fixture("Resume.pdf")
        cls.resume_twocol = _fixture("VALIBOYINA-MURALI-SAI-Resume.pdf")

    @unittest.skipUnless(_fixture("Resume.pdf"), "Resume.pdf not in repo root or tests/fixtures/resumes")
    def test_single_column_style_not_flagged_two_col(self):
        assert self.resume_single is not None
        with pdfplumber.open(self.resume_single) as pdf:
            for page in pdf.pages:
                self.assertFalse(
                    pdf_text_layout.detect_likely_two_column_page(page),
                    "Single-column resume should not use two-column reading order",
                )

    @unittest.skipUnless(
        _fixture("VALIBOYINA-MURALI-SAI-Resume.pdf"),
        "VALIBOYINA-MURALI-SAI-Resume.pdf not in repo root or tests/fixtures/resumes",
    )
    def test_two_column_style_detected(self):
        assert self.resume_twocol is not None
        with pdfplumber.open(self.resume_twocol) as pdf:
            self.assertTrue(
                pdf_text_layout.detect_likely_two_column_page(pdf.pages[0]),
                "Two-column resume first page should be detected",
            )

    @unittest.skipUnless(_fixture("Resume.pdf"), "Resume.pdf missing")
    def test_single_column_preserves_header_line(self):
        text, meta = pdf_text_layout.extract_resume_text_adaptive_columns(
            str(self.resume_single)
        )
        self.assertEqual(meta.get("two_column_pages"), [])
        self.assertIn("2026", text)
        self.assertIn("specializing in", text)
        self.assertIn("Artificial Intelligence", text)

    @unittest.skipUnless(
        _fixture("VALIBOYINA-MURALI-SAI-Resume.pdf"),
        "VALIBOYINA PDF missing",
    )
    def test_two_column_avoids_education_experience_same_line(self):
        text, meta = pdf_text_layout.extract_resume_text_adaptive_columns(
            str(self.resume_twocol)
        )
        self.assertEqual(meta.get("two_column_pages"), [1])
        self.assertNotIn("Education Experience", text)


if __name__ == "__main__":
    unittest.main()
