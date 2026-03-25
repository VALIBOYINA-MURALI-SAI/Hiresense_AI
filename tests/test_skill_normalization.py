"""Tests for skill normalization and alias matching (Option C)."""

import importlib.util
import unittest
from pathlib import Path


def _load_skill_norm():
    path = Path(__file__).resolve().parents[1] / "utils" / "skill_normalization.py"
    spec = importlib.util.spec_from_file_location("skill_normalization", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


sn = _load_skill_norm()


class TestSkillNormalization(unittest.TestCase):
    def test_normalize_aliases(self):
        self.assertEqual(sn.normalize_skill_term("JS"), "javascript")
        self.assertEqual(sn.normalize_skill_term("React.js"), "react")
        self.assertEqual(sn.normalize_skill_term("NodeJS"), "node.js")

    def test_match_uses_aliases(self):
        found, missing, _ = sn.match_required_skills_against_resume(
            "Senior dev: js, react, and node for apis",
            ["JavaScript", "React", "Node.js"],
        )
        self.assertEqual(len(missing), 0)
        self.assertEqual(len(found), 3)

    def test_iam_expansion(self):
        phrases = sn.expand_resume_search_phrases("iam")
        self.assertIn("identity and access management", phrases)

    def test_allowed_vocab_for_frontend(self):
        fake_job = {
            "required_skills": ["HTML", "JavaScript", "React"],
            "recommended_skills": {
                "technical": ["TypeScript", "Git"],
            },
        }
        allowed = sn.build_allowed_canonicals_for_job_role(fake_job)
        self.assertIn("javascript", allowed)
        self.assertIn("react", allowed)
        self.assertNotIn("python", allowed)


if __name__ == "__main__":
    unittest.main()
