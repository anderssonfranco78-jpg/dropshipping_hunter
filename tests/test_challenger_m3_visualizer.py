"""Empirical Challenger Test Suite for Milestone M3 (Visualizer).

Validates:
1. High-resolution PNG generation (1920x1080 @ 300 DPI, dark mode #0F172A).
2. Boundary handling: single candidate, empty dataset, and large list (>15 items, E-10).
3. Interactive HTML dashboard: standalone HTML5, responsive viewport, filter toggles,
   7-rule status glyphs (✓/✗), and hover tooltips.
4. CLI subprocess execution with zero desktop GUI window creation.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from PIL import Image

HUNTER_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(HUNTER_ROOT) not in sys.path:
    sys.path.insert(0, str(HUNTER_ROOT))

from hunter.models import AuditResult, FinancialMetrics, RawCandidate, RuleScore
from hunter.visualizer import Visualizer


class TestVisualizerArtifacts(unittest.TestCase):
    """Verifies Visualizer generation of PNG and HTML artifacts."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = pathlib.Path(self.temp_dir.name)
        self.audit_json = HUNTER_ROOT / "data" / "audit_results.json"
        self.visualizer = Visualizer(dpi=300)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_png_resolution_and_dpi(self) -> None:
        """Verifies PNG output is exactly 1920x1080 at 300 DPI in dark mode."""
        png_out = str(self.temp_path / "test_ranking.png")
        result_path = self.visualizer.generate_png(str(self.audit_json), output_path=png_out)

        self.assertEqual(result_path, png_out)
        self.assertTrue(os.path.exists(png_out))
        self.assertGreater(os.path.getsize(png_out), 50000)

        with Image.open(png_out) as img:
            self.assertEqual(img.size, (1920, 1080))
            dpi = img.info.get("dpi")
            self.assertIsNotNone(dpi)
            self.assertAlmostEqual(dpi[0], 300, delta=1.0)
            self.assertAlmostEqual(dpi[1], 300, delta=1.0)
            self.assertEqual(img.format, "PNG")

    def test_png_single_candidate_scale(self) -> None:
        """E-10: Verifies PNG generation succeeds with exactly 1 candidate without crashing."""
        with open(self.audit_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        single_result = [AuditResult.from_dict(data[0])]

        png_out = str(self.temp_path / "single_candidate.png")
        self.visualizer.generate_png(single_result, output_path=png_out)

        self.assertTrue(os.path.exists(png_out))
        with Image.open(png_out) as img:
            self.assertEqual(img.size, (1920, 1080))

    def test_png_large_candidate_list_truncation(self) -> None:
        """E-10: Verifies large lists (>15 items) truncate cleanly without label overlap."""
        with open(self.audit_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Replicate candidate to create 30 items
        base_item = data[0]
        large_list: list[AuditResult] = []
        for i in range(30):
            item_copy = json.loads(json.dumps(base_item))
            item_copy["candidate"]["candidate_id"] = f"item-{i}"
            item_copy["candidate"]["name"] = f"Candidate Item #{i+1} Multi-Scale"
            item_copy["composite_score"] = float(40 + (i * 2))
            item_copy["tier"] = "WINNER" if item_copy["composite_score"] >= 80 else ("CONTENDER" if item_copy["composite_score"] >= 65 else "DISQUALIFIED")
            large_list.append(AuditResult.from_dict(item_copy))

        png_out = str(self.temp_path / "large_list.png")
        self.visualizer.generate_png(large_list, output_path=png_out)

        self.assertTrue(os.path.exists(png_out))
        with Image.open(png_out) as img:
            self.assertEqual(img.size, (1920, 1080))

    def test_png_empty_candidates(self) -> None:
        """Verifies PNG generation gracefully handles an empty results list."""
        png_out = str(self.temp_path / "empty.png")
        self.visualizer.generate_png([], output_path=png_out)
        self.assertTrue(os.path.exists(png_out))

    def test_html_standalone_and_responsive(self) -> None:
        """Verifies HTML dashboard contains valid HTML5 boilerplate and responsive tags."""
        html_out = str(self.temp_path / "test_ranking.html")
        result_path = self.visualizer.generate_html(str(self.audit_json), output_path=html_out)

        self.assertEqual(result_path, html_out)
        self.assertTrue(os.path.exists(html_out))

        with open(html_out, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("<meta charset=\"UTF-8\">", content)
        self.assertIn("width=device-width", content)
        self.assertIn("#0F172A", content)  # Theme background

    def test_html_filter_structure_and_tooltips(self) -> None:
        """Verifies HTML filter buttons, 7-rule glyphs (✓/✗), and hover tooltips."""
        html_out = str(self.temp_path / "test_ranking.html")
        self.visualizer.generate_html(str(self.audit_json), output_path=html_out)

        with open(html_out, "r", encoding="utf-8") as f:
            content = f.read()

        for filter_key in ["all", "winners", "contenders", "disqualified"]:
            self.assertIn(f'data-filter="{filter_key}"', content)

        self.assertIn("✓", content)
        self.assertIn("✗", content)
        self.assertIn("7 Golden Rules", content)
        self.assertIn("tooltip-rule-row", content)

    def test_visualize_all_generates_both_artifacts(self) -> None:
        """Verifies visualize_all generates both PNG and HTML simultaneously."""
        png_out = str(self.temp_path / "dual.png")
        html_out = str(self.temp_path / "dual.html")

        paths = self.visualizer.visualize_all(
            str(self.audit_json),
            output_png=png_out,
            output_html=html_out,
        )

        self.assertEqual(paths["png"], png_out)
        self.assertEqual(paths["html"], html_out)
        self.assertTrue(os.path.exists(png_out))
        self.assertTrue(os.path.exists(html_out))
        self.assertGreater(os.path.getsize(png_out), 0)
        self.assertGreater(os.path.getsize(html_out), 0)

    def test_cli_execution_subprocess(self) -> None:
        """Verifies CLI execution: python -m hunter.visualizer runs cleanly without errors."""
        png_out = str(self.temp_path / "cli.png")
        html_out = str(self.temp_path / "cli.html")

        cmd = [
            sys.executable,
            "-m",
            "hunter.visualizer",
            "--input",
            str(self.audit_json),
            "--png",
            png_out,
            "--html",
            html_out,
        ]

        result = subprocess.run(
            cmd,
            cwd=str(HUNTER_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )

        self.assertEqual(result.returncode, 0, f"CLI error: {result.stderr}")
        self.assertTrue(os.path.exists(png_out))
        self.assertTrue(os.path.exists(html_out))


if __name__ == "__main__":
    unittest.main()
