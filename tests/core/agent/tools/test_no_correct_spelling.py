"""SAFE-07: CI guard — ensure the correctly-spelled 'InfoCategory' never appears
under app/core/agent/ (where it would cause silent zero-row returns against the
live DB column 'InfoCategory '). The tests directory is excluded.
"""
from __future__ import annotations
import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCAN_ROOT = _REPO_ROOT / "app" / "core" / "agent"
_PATTERN = re.compile(r"\bInfoCategory\b")


def _scan_for_correct_spelling() -> list[tuple[str, int, str]]:
    """Return list of (path, line_number, line_text) matches under app/core/agent/."""
    hits: list[tuple[str, int, str]] = []
    for py in _SCAN_ROOT.rglob("*.py"):
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), start=1):
            if _PATTERN.search(line):
                hits.append((str(py.relative_to(_REPO_ROOT)), i, line))
    spec_dir = _SCAN_ROOT / "tools" / "spec"
    if spec_dir.exists():
        for txt in spec_dir.glob("*.txt"):
            for i, line in enumerate(txt.read_text(encoding="utf-8").splitlines(), start=1):
                if _PATTERN.search(line):
                    hits.append((str(txt.relative_to(_REPO_ROOT)), i, line))
    return hits


class InfoCategoryGuardTest(unittest.TestCase):
    def test_production_tree_has_no_correct_spelling(self):
        hits = _scan_for_correct_spelling()
        self.assertEqual(
            hits,
            [],
            f"Found correctly-spelled 'InfoCategory' in {len(hits)} location(s): {hits}. "
            "The DB column is 'InfoCategory ' (typo preserved). See SAFE-07.",
        )

    def test_meta_scanner_detects_injected_correct_spelling(self):
        """TEST-04: verify the scanner actually works by injecting a known-bad file."""
        temp = _SCAN_ROOT / "_temp_meta_test.py"
        try:
            temp.write_text('x = "InfoCategory"  # intentional for meta-test\n', encoding="utf-8")
            hits = _scan_for_correct_spelling()
            self.assertTrue(
                any("_temp_meta_test.py" in h[0] for h in hits),
                f"Meta-test failed: scanner did not detect injected file. Hits: {hits}",
            )
        finally:
            if temp.exists():
                temp.unlink()

        # Confirm cleanup worked
        hits_after = _scan_for_correct_spelling()
        self.assertEqual(hits_after, [], "Meta-test cleanup failed — production tree still has hits")


if __name__ == "__main__":
    unittest.main()
