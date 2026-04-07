from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "sample_module.py"


class CliTests(unittest.TestCase):
    def test_reports_local_raise_and_unresolved_open_call(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "except_tool.cli", str(FIXTURE), "19"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertIn("Statement at line 19: value = load_value(\"config.txt\")", result.stdout)
        self.assertIn("ValueError via load_value -> read_number -> parse_number", result.stdout)
        self.assertIn("open via load_value -> read_number -> open", result.stdout)


if __name__ == "__main__":
    unittest.main()
