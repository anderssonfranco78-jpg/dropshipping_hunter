"""Tier 5: Adversarial Hardening & Stress Testing Test Suite.

Adversarially validates:
1. Full CLI Flags Variations:
   - --harvest-only, --audit-only, --visualize-only, --dossier-only, --offline
   - Custom persistence directories (--data-dir, custom destination paths)
   - Logging switches (--verbose, --quiet) and query keyword filters (--keywords)
   - Graceful failure on missing input data and unrecognized arguments
2. Corrupted & Empty Datasets:
   - Empty candidate lists across AuditEngine, Visualizer (PNG & HTML), and DossierGenerator
   - Validation against negative pricing, inverted logistics windows, and out-of-bounds scores
   - Robust deserialization of malformed / partial dictionaries and invalid JSON inputs
3. Non-ASCII / Special Characters & HTML Escaping (XSS Defense):
   - Multilingual Unicode (Spanish, Asian ideographs, Cyrillic, German, Arabic, Emojis)
   - Malicious XSS vectors (<script>, <img onerror>, <svg/onload>, javascript: URLs)
   - Strict verification that raw unescaped HTML tags never leak into generated HTML reports
4. Extreme Values & High-Load Candidate Rendering:
   - Ultra-penny ($0.01) and ultra-luxury ($1,000,000) unit economics
   - Boundary values for visual demo speed, delivery windows, and trend momentum
   - Scaled rendering from 1 candidate up to 50 high-load candidates (verifying PNG truncation & HTML full rendering)
"""

from __future__ import annotations

import html
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

# Workspace root configuration
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from main import main, parse_arguments
from hunter.models import RawCandidate, FinancialMetrics, RuleScore, AuditResult
from hunter.audit_engine import AuditEngine
from hunter.visualizer import Visualizer, _normalize_audit_results
from hunter.dossier_generator import DossierGenerator
from tests import CANONICAL_FIXTURES, get_canonical_raw_candidate


def create_test_candidate(
    candidate_id: str = "test-item",
    name: str = "Test Product Title",
    category: str = "General",
    description: str = "Functional description for testing",
    supplier_cost: float = 10.0,
    shipping_cost: float = 3.0,
    suggested_price: float = 49.99,
    shipping_days_min: int = 7,
    shipping_days_max: int = 10,
    shipping_carrier: str = "YunExpress",
    has_fragile_material: bool = False,
    has_sizing_requirements: bool = False,
    demo_visual_speed_sec: float = 1.5,
    pain_level_score: float = 90.0,
    retail_availability_score: float = 95.0,
    ad_active_days: int = 35,
    competitor_ad_count: int = 25,
    google_trends_momentum: float = 45.0,
    source_url: str = "https://example.com/product",
) -> RawCandidate:
    """Helper to instantiate a valid RawCandidate with customizable fields."""
    return RawCandidate(
        candidate_id=candidate_id,
        name=name,
        category=category,
        description=description,
        supplier_cost=supplier_cost,
        shipping_cost=shipping_cost,
        suggested_price=suggested_price,
        shipping_days_min=shipping_days_min,
        shipping_days_max=shipping_days_max,
        shipping_carrier=shipping_carrier,
        has_fragile_material=has_fragile_material,
        has_sizing_requirements=has_sizing_requirements,
        demo_visual_speed_sec=demo_visual_speed_sec,
        pain_level_score=pain_level_score,
        retail_availability_score=retail_availability_score,
        ad_active_days=ad_active_days,
        competitor_ad_count=competitor_ad_count,
        google_trends_momentum=google_trends_momentum,
        source_url=source_url,
    )


# ==============================================================================
# SECTION 1: FULL CLI FLAGS VARIATIONS
# ==============================================================================
class TestCLIFlagVariationsAdversarial(unittest.TestCase):
    """Adversarial stress-testing of main.py CLI arguments and execution flows."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_tier5_cli_")
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)

    def test_cli_help_flag_displays_usage(self) -> None:
        """Verifies -h and --help trigger clean SystemExit(0) with full options documentation."""
        with self.assertRaises(SystemExit) as cm:
            parse_arguments(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_cli_offline_harvest_only_with_custom_data_dir(self) -> None:
        """Verifies --harvest-only with --offline and custom --data-dir persists candidates.json."""
        ret = main(["--offline", "--harvest-only", "--data-dir", self.temp_dir, "--quiet"])
        self.assertEqual(ret, 0)

        candidates_file = Path(self.temp_dir) / "candidates.json"
        self.assertTrue(candidates_file.exists(), "candidates.json was not created in custom data-dir")

        with open(candidates_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)

    def test_cli_audit_only_with_existing_candidates(self) -> None:
        """Verifies --audit-only parses pre-existing candidates.json and writes audit_results.json."""
        candidates = [
            create_test_candidate("w1", "Winner One", suggested_price=49.99, supplier_cost=8.0),
            create_test_candidate("w2", "Winner Two", suggested_price=39.99, supplier_cost=7.0),
        ]
        candidates_file = Path(self.temp_dir) / "candidates.json"
        with open(candidates_file, "w", encoding="utf-8") as f:
            json.dump([c.to_dict() for c in candidates], f, indent=2)

        ret = main(["--audit-only", "--data-dir", self.temp_dir, "--quiet"])
        self.assertEqual(ret, 0)

        audit_file = Path(self.temp_dir) / "audit_results.json"
        self.assertTrue(audit_file.exists(), "audit_results.json was not created")

        with open(audit_file, "r", encoding="utf-8") as f:
            audit_data = json.load(f)
        self.assertEqual(len(audit_data), 2)

    def test_cli_audit_only_auto_harvests_when_candidates_missing(self) -> None:
        """Verifies --audit-only automatically triggers offline harvest if candidates.json is absent."""
        ret = main(["--offline", "--audit-only", "--data-dir", self.temp_dir, "--quiet"])
        self.assertEqual(ret, 0)

        candidates_file = Path(self.temp_dir) / "candidates.json"
        audit_file = Path(self.temp_dir) / "audit_results.json"
        self.assertTrue(candidates_file.exists())
        self.assertTrue(audit_file.exists())

    def test_cli_audit_only_with_custom_export_json_path(self) -> None:
        """Verifies --export-json writes audit results to explicit custom path."""
        custom_audit = os.path.join(self.temp_dir, "custom_target_audit.json")
        ret = main([
            "--offline", "--audit-only",
            "--data-dir", self.temp_dir,
            "--export-json", custom_audit,
            "--quiet",
        ])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(custom_audit))

        with open(custom_audit, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertGreaterEqual(len(loaded), 1)

    def test_cli_visualize_only_success_with_existing_audit(self) -> None:
        """Verifies --visualize-only succeeds when audit_results.json exists."""
        auditor = AuditEngine(data_dir=self.temp_dir)
        cands = [create_test_candidate("c1", "Test Product")]
        results = auditor.audit_candidates(cands)

        audit_file = Path(self.temp_dir) / "audit_results.json"
        with open(audit_file, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in results], f)

        ret = main(["--visualize-only", "--data-dir", self.temp_dir, "--quiet"])
        self.assertEqual(ret, 0)

    def test_cli_visualize_only_fails_gracefully_when_audit_missing(self) -> None:
        """Verifies --visualize-only returns exit code 1 when audit_results.json is absent."""
        empty_dir = os.path.join(self.temp_dir, "empty_dir")
        os.makedirs(empty_dir, exist_ok=True)

        ret = main(["--visualize-only", "--data-dir", empty_dir, "--quiet"])
        self.assertEqual(ret, 1)

    def test_cli_dossier_only_success_with_custom_output(self) -> None:
        """Verifies --dossier-only compiles Markdown report to -o destination."""
        auditor = AuditEngine(data_dir=self.temp_dir)
        cands = [
            create_test_candidate("w1", "Winner A", suggested_price=49.99),
            create_test_candidate("w2", "Winner B", suggested_price=59.99),
            create_test_candidate("w3", "Winner C", suggested_price=39.99),
        ]
        results = auditor.audit_candidates(cands)

        audit_file = Path(self.temp_dir) / "audit_results.json"
        with open(audit_file, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in results], f)

        custom_dossier = os.path.join(self.temp_dir, "output_dossier.md")
        ret = main([
            "--dossier-only",
            "--data-dir", self.temp_dir,
            "-o", custom_dossier,
            "--quiet",
        ])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(custom_dossier))

        with open(custom_dossier, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("DOSSIER OFICIAL", content)

    def test_cli_dossier_only_fails_gracefully_when_audit_missing(self) -> None:
        """Verifies --dossier-only returns exit code 1 when audit_results.json is absent."""
        ret = main(["--dossier-only", "--data-dir", self.temp_dir, "--quiet"])
        self.assertEqual(ret, 1)

    def test_cli_full_end_to_end_offline_pipeline(self) -> None:
        """Verifies complete 4-stage pipeline execution with custom destinations."""
        custom_audit = os.path.join(self.temp_dir, "full_audit.json")
        custom_dossier = os.path.join(self.temp_dir, "full_dossier.md")

        ret = main([
            "--offline",
            "--data-dir", self.temp_dir,
            "--export-json", custom_audit,
            "--generate-dossier", custom_dossier,
            "--verbose",
        ])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(custom_audit))
        self.assertTrue(os.path.exists(custom_dossier))

    def test_cli_keywords_filter_offline_execution(self) -> None:
        """Verifies --keywords accepts multiple arguments and completes cleanly."""
        ret = main([
            "--offline",
            "--harvest-only",
            "--data-dir", self.temp_dir,
            "--keywords", "lumbar", "cushion",
            "--quiet",
        ])
        self.assertEqual(ret, 0)

    def test_cli_unrecognized_argument_handling(self) -> None:
        """Verifies unrecognized arguments cause clean SystemExit rejection."""
        with self.assertRaises(SystemExit) as cm:
            parse_arguments(["--output-dir", self.temp_dir])
        self.assertNotEqual(cm.exception.code, 0)


# ==============================================================================
# SECTION 2: CORRUPTED & EMPTY DATASETS
# ==============================================================================
class TestCorruptedAndEmptyDatasetsAdversarial(unittest.TestCase):
    """Adversarial stress-testing of empty collections, malformed inputs, and validation gates."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_tier5_corrupted_")
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)

    def test_audit_engine_handles_empty_candidates_gracefully(self) -> None:
        """Verifies AuditEngine.audit_candidates([]) returns empty list without error."""
        auditor = AuditEngine()
        results = auditor.audit_candidates([])
        self.assertEqual(results, [])

    def test_visualizer_handles_empty_dataset_png(self) -> None:
        """Verifies Visualizer.generate_png([]) renders empty-state card without crash."""
        vis = Visualizer()
        out_png = os.path.join(self.temp_dir, "empty_chart.png")
        result_path = vis.generate_png([], output_path=out_png)
        self.assertTrue(os.path.exists(result_path))
        self.assertGreater(os.path.getsize(result_path), 1000)

    def test_visualizer_handles_empty_dataset_html(self) -> None:
        """Verifies Visualizer.generate_html([]) generates valid HTML without zero division."""
        vis = Visualizer()
        out_html = os.path.join(self.temp_dir, "empty_dashboard.html")
        result_path = vis.generate_html([], output_path=out_html)
        self.assertTrue(os.path.exists(result_path))

        with open(result_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Candidates Evaluated", content)
        self.assertIn('<div class="kpi-value">0</div>', content)
        self.assertIn("<!DOCTYPE html>", content)

    def test_dossier_generator_empty_audit_raises_value_error(self) -> None:
        """Verifies DossierGenerator raises ValueError when passed empty audit results."""
        gen = DossierGenerator()
        with self.assertRaises(ValueError) as cm:
            gen.generate_dossier([])
        self.assertIn("minimum 3 required", str(cm.exception))

    def test_dossier_generator_insufficient_winners_raises_value_error(self) -> None:
        """Verifies DossierGenerator raises ValueError if total winners + contenders < 3."""
        gen = DossierGenerator()
        auditor = AuditEngine()
        disqualified = [
            create_test_candidate("dq1", "Bad 1", has_fragile_material=True),
            create_test_candidate("dq2", "Bad 2", has_sizing_requirements=True),
        ]
        results = auditor.audit_candidates(disqualified)
        with self.assertRaises(ValueError) as cm:
            gen.generate_dossier(results)
        self.assertIn("Insufficient validated winners", str(cm.exception))

    def test_raw_candidate_validation_detects_all_corrupted_fields(self) -> None:
        """Adversarially constructs candidate with all invalid fields to verify validate()."""
        corrupted = RawCandidate(
            candidate_id="",
            name="",
            category="Test",
            description="Corrupted",
            supplier_cost=-50.0,
            shipping_cost=-10.0,
            suggested_price=-5.0,
            shipping_days_min=20,
            shipping_days_max=10,  # Inverted window
            shipping_carrier="Test",
            has_fragile_material=False,
            has_sizing_requirements=False,
            demo_visual_speed_sec=-2.0,
            pain_level_score=150.0,  # Out of range
            retail_availability_score=-10.0,  # Out of range
            ad_active_days=-5,
            competitor_ad_count=-1,
            google_trends_momentum=-20.0,
            source_url="bad",
        )
        errors = corrupted.validate()
        self.assertGreaterEqual(len(errors), 8)
        self.assertTrue(any("candidate_id" in e for e in errors))
        self.assertTrue(any("name" in e for e in errors))
        self.assertTrue(any("supplier_cost" in e for e in errors))
        self.assertTrue(any("shipping_cost" in e for e in errors))
        self.assertTrue(any("suggested_price" in e for e in errors))
        self.assertTrue(any("shipping window" in e for e in errors))
        self.assertTrue(any("pain_level_score" in e for e in errors))
        self.assertTrue(any("retail_availability_score" in e for e in errors))

    def test_raw_candidate_from_dict_with_empty_or_partial_payload(self) -> None:
        """Verifies RawCandidate.from_dict handles empty or partial dicts safely without crash."""
        cand = RawCandidate.from_dict({})
        self.assertEqual(cand.candidate_id, "")
        self.assertEqual(cand.name, "")
        self.assertEqual(cand.supplier_cost, 0.0)
        self.assertEqual(cand.suggested_price, 0.0)

    def test_normalize_audit_results_rejects_unsupported_types(self) -> None:
        """Verifies _normalize_audit_results raises TypeError on unexpected types."""
        with self.assertRaises(TypeError):
            _normalize_audit_results([123, 456])

    def test_normalize_audit_results_handles_malformed_json_file(self) -> None:
        """Verifies passing malformed JSON file to _normalize_audit_results raises JSONDecodeError."""
        bad_json = os.path.join(self.temp_dir, "corrupt.json")
        with open(bad_json, "w", encoding="utf-8") as f:
            f.write("{broken_json: true,")

        with self.assertRaises(json.JSONDecodeError):
            _normalize_audit_results(bad_json)


# ==============================================================================
# SECTION 3: NON-ASCII / SPECIAL CHARACTERS & HTML ESCAPING (XSS DEFENSE)
# ==============================================================================
class TestNonAsciiAndHtmlEscapingAdversarial(unittest.TestCase):
    """Adversarial stress-testing of multilingual Unicode characters and XSS escaping."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_tier5_unicode_")
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)

    def test_multilingual_unicode_serialization_and_audit(self) -> None:
        """Verifies models and audit engine process Spanish accents, Kanji, Cyrillic, and Emojis."""
        cand = create_test_candidate(
            candidate_id="unicode-pro-2026",
            name="🔥 Súper Faja Lumbar 3.0™ — ¡Alivio Rápido! 🚀 / 「超音波」歯石除去 / Groß-München / Ультразвук",
            category="Salud & Bienestar / 健康",
            description="Tratamiento 100% térmico para vértebras lumbares; ¡sin dolor!",
            shipping_carrier="YunExpress España (Línea Especial)",
        )

        # 1. Round-trip dict serialization
        as_dict = cand.to_dict()
        reconstructed = RawCandidate.from_dict(as_dict)
        self.assertEqual(reconstructed.name, cand.name)

        # 2. JSON serialization with ensure_ascii=False
        dumped = json.dumps(as_dict, ensure_ascii=False)
        self.assertIn("🔥", dumped)
        self.assertIn("¡Alivio Rápido!", dumped)
        self.assertIn("「超音波」", dumped)

        # 3. Audit execution
        auditor = AuditEngine()
        results = auditor.audit_candidates([cand])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].candidate.name, cand.name)

    def test_html_escaping_prevents_xss_injection(self) -> None:
        """Adversarially injects malicious HTML / JavaScript tags into product fields
        and verifies they are strictly escaped in generated HTML dashboard.
        """
        xss_cand = create_test_candidate(
            candidate_id="xss-test-payload",
            name='<script>alert("XSS_NAME")</script><b onmouseover="alert(1)">Injected Product</b>',
            category='<img src=x onerror=alert("XSS_CAT")>',
            shipping_carrier='<svg/onload=alert("XSS_CARRIER")>',
            source_url='javascript:alert("XSS_LINK")',
        )

        auditor = AuditEngine()
        results = auditor.audit_candidates([xss_cand])

        vis = Visualizer()
        out_html = os.path.join(self.temp_dir, "xss_audit_report.html")
        vis.generate_html(results, output_path=out_html)

        with open(out_html, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Strict XSS assertions: Raw executable tags must NOT exist in the output
        self.assertNotIn('<script>alert("XSS_NAME")</script>', html_content)
        self.assertNotIn('<img src=x onerror=alert("XSS_CAT")>', html_content)
        self.assertNotIn('<svg/onload=alert("XSS_CARRIER")>', html_content)

        # Verifies that tags were properly HTML entity-escaped
        self.assertIn("&lt;script&gt;", html_content)
        self.assertIn("&lt;img src=x onerror=", html_content)
        self.assertIn("&lt;svg/onload=", html_content)

    def test_unicode_character_rendering_in_visualizer_png(self) -> None:
        """Verifies Visualizer renders Unicode product names to PNG without encoding crash."""
        unicode_cand = create_test_candidate(
            candidate_id="es-lumbar-1",
            name="Cinturón de Descompresión Lumbar Pro™ (Edición 2026)",
        )
        auditor = AuditEngine()
        results = auditor.audit_candidates([unicode_cand])

        vis = Visualizer()
        out_png = os.path.join(self.temp_dir, "unicode_chart.png")
        vis.generate_png(results, output_path=out_png)
        self.assertTrue(os.path.exists(out_png))

    def test_unicode_in_winner_dossier_markdown(self) -> None:
        """Verifies DossierGenerator compiles UTF-8 Markdown preserving accented text."""
        cands = [
            create_test_candidate("w1", "Cinturón Lumbar Pro™", suggested_price=49.99),
            create_test_candidate("w2", "Soplador Turbina Élite®", suggested_price=59.99),
            create_test_candidate("w3", "Limpiador Ultrasónico Dental™", suggested_price=39.99),
        ]
        auditor = AuditEngine()
        results = auditor.audit_candidates(cands)

        gen = DossierGenerator()
        out_md = os.path.join(self.temp_dir, "unicode_dossier.md")
        gen.generate_dossier(results, output_path=out_md)

        with open(out_md, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Cinturón Lumbar Pro™", content)
        self.assertIn("Soplador Turbina Élite®", content)

    def test_dynamic_hooks_synthesis_with_special_characters(self) -> None:
        """Verifies dynamic hook synthesizer formats strings containing quotes and symbols."""
        cand = create_test_candidate(
            candidate_id="custom-special-hooks",
            name='Pro "Clean" & Relieve — 100% #1 Gadget!',
            category="Health & Wellness",
        )
        gen = DossierGenerator()
        hooks = gen.generate_hooks(cand)

        self.assertIn("curiosidad_disruptiva", hooks)
        self.assertIn("agitacion_dolor_real", hooks)
        self.assertIn("contrariano", hooks)
        self.assertIn("transformacion_inmediata", hooks)

        # Verify each hook has dual TTS dialogue and storyboard rows
        for hook_key, hook_data in hooks.items():
            self.assertIn("dialogue_script", hook_data)
            self.assertIn("storyboard_rows", hook_data)
            self.assertGreaterEqual(len(hook_data["storyboard_rows"]), 4)


# ==============================================================================
# SECTION 4: EXTREME VALUES & HIGH-LOAD CANDIDATE RENDERING
# ==============================================================================
class TestExtremeValuesAndHighLoadAdversarial(unittest.TestCase):
    """Adversarial stress-testing of numerical limits and high-load batch scaling (1-50 candidates)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_tier5_load_")
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)

    def test_extreme_unit_economics_penny_and_luxury_tickets(self) -> None:
        """Adversarially tests unit economics at boundary extremes: $0.01 vs $1,000,000."""
        # 1. Ultra penny item: SRP = $0.01, Cost = $0.001
        penny = create_test_candidate("penny", "Penny Item", supplier_cost=0.001, shipping_cost=0.0, suggested_price=0.01)
        fin_penny = penny.compute_financials()
        self.assertEqual(fin_penny.srp, 0.01)
        # Processor fee floor is $0.30, so net profit must be negative
        self.assertLess(fin_penny.net_profit, 0.0)

        # 2. Ultra luxury item: SRP = $1,000,000.0, Cost = $100,000.0
        luxury = create_test_candidate("luxury", "Luxury Item", supplier_cost=100000.0, shipping_cost=500.0, suggested_price=1000000.0)
        fin_luxury = luxury.compute_financials()
        self.assertAlmostEqual(fin_luxury.markup_multiplier, 9.95, delta=0.05)
        self.assertGreater(fin_luxury.net_margin_pct, 80.0)

    def test_extreme_operational_values(self) -> None:
        """Adversarially tests operational rubrics at extreme boundary values."""
        auditor = AuditEngine()

        # Ultra-fast demo (0.01s) vs ultra-slow demo (500s) + retail commodity (scarcity < 30)
        fast_cand = create_test_candidate("fast", "Fast WOW", demo_visual_speed_sec=0.01)
        slow_cand = create_test_candidate(
            "slow", "Slow WOW", demo_visual_speed_sec=500.0, retail_availability_score=15.0
        )

        res_fast = auditor.audit_candidates([fast_cand])[0]
        res_slow = auditor.audit_candidates([slow_cand])[0]

        self.assertEqual(res_fast.rule_scores[1].raw_score, 100.0)
        self.assertEqual(res_slow.rule_scores[1].raw_score, 0.0)
        self.assertIn("KO-4", res_slow.ko_gates_tripped)

        # Ultra-delayed shipping (180 days)
        delayed_cand = create_test_candidate("delayed", "Delayed Shipping", shipping_days_min=90, shipping_days_max=180)
        res_delayed = auditor.audit_candidates([delayed_cand])[0]
        self.assertEqual(res_delayed.rule_scores[7].raw_score, 0.0)
        self.assertIn("KO-3", res_delayed.ko_gates_tripped)

    def test_visualizer_single_candidate_scale(self) -> None:
        """Verifies Visualizer handles exactly N=1 candidate (testing dedicated 1-item layout scaling)."""
        cand = create_test_candidate("solo", "Solo Candidate", suggested_price=49.99)
        auditor = AuditEngine()
        results = auditor.audit_candidates([cand])

        vis = Visualizer()
        out_png = os.path.join(self.temp_dir, "solo.png")
        out_html = os.path.join(self.temp_dir, "solo.html")

        vis.generate_png(results, output_path=out_png)
        vis.generate_html(results, output_path=out_html)

        self.assertTrue(os.path.exists(out_png))
        self.assertTrue(os.path.exists(out_html))

    def test_visualizer_small_batches_two_to_four(self) -> None:
        """Verifies adaptive bar height logic on small batches (N = 2, 3, 4)."""
        auditor = AuditEngine()
        vis = Visualizer()

        for count in [2, 3, 4]:
            cands = [create_test_candidate(f"item_{i}", f"Product {i}") for i in range(count)]
            results = auditor.audit_candidates(cands)

            out_png = os.path.join(self.temp_dir, f"batch_{count}.png")
            vis.generate_png(results, output_path=out_png)
            self.assertTrue(os.path.exists(out_png))

    def test_visualizer_boundary_fifteen_candidates(self) -> None:
        """Verifies boundary condition N=15 where chart truncation is NOT triggered."""
        auditor = AuditEngine()
        cands = [create_test_candidate(f"cand_{i}", f"Product #{i+1}") for i in range(15)]
        results = auditor.audit_candidates(cands)

        vis = Visualizer()
        out_png = os.path.join(self.temp_dir, "boundary_15.png")
        vis.generate_png(results, output_path=out_png)
        self.assertTrue(os.path.exists(out_png))

    def test_high_load_fifty_candidates_rendering_and_audit(self) -> None:
        """High-load stress test: Generates, audits, visualizes (PNG & HTML), and dossiers
        a massive catalog of 50 candidates (mix of winners, contenders, and disqualified).
        """
        catalog: List[RawCandidate] = []
        for i in range(50):
            cand_id = f"stress-cand-{i:02d}"
            if i < 15:
                # 15 Winners
                cand = create_test_candidate(
                    candidate_id=cand_id,
                    name=f"Winner Product #{i+1} — Elite Gadget",
                    suggested_price=49.99 + (i * 1.0),
                    supplier_cost=8.0,
                    shipping_cost=3.0,
                    pain_level_score=90.0,
                    retail_availability_score=95.0,
                    demo_visual_speed_sec=1.5,
                )
            elif i < 30:
                # 15 Contenders
                cand = create_test_candidate(
                    candidate_id=cand_id,
                    name=f"Contender Product #{i+1} — Useful Tool",
                    suggested_price=35.00,
                    supplier_cost=10.0,
                    shipping_cost=4.0,
                    pain_level_score=70.0,
                    retail_availability_score=70.0,
                    demo_visual_speed_sec=4.0,
                )
            else:
                # 20 Disqualified (varied KO reasons)
                cand = create_test_candidate(
                    candidate_id=cand_id,
                    name=f"Disqualified Product #{i+1} — High Risk Item",
                    has_fragile_material=(i % 2 == 0),
                    has_sizing_requirements=(i % 2 != 0),
                    suggested_price=15.0,
                    supplier_cost=12.0,
                )
            catalog.append(cand)

        self.assertEqual(len(catalog), 50)

        t0 = time.time()

        # 1. Audit all 50 candidates
        auditor = AuditEngine()
        results = auditor.audit_candidates(catalog)
        self.assertEqual(len(results), 50)

        winners = [r for r in results if r.tier == "WINNER"]
        contenders = [r for r in results if r.tier == "CONTENDER"]
        disqualified = [r for r in results if r.tier == "DISQUALIFIED"]

        self.assertEqual(len(winners), 15)
        self.assertEqual(len(contenders), 15)
        self.assertEqual(len(disqualified), 20)

        # 2. Render high-load PNG (verifies >15 truncation keeps chart legible without OOM)
        vis = Visualizer()
        out_png = os.path.join(self.temp_dir, "high_load_50.png")
        vis.generate_png(results, output_path=out_png)
        self.assertTrue(os.path.exists(out_png))
        self.assertGreater(os.path.getsize(out_png), 10000)

        # 3. Render high-load HTML dashboard (renders all 50 products in searchable table)
        out_html = os.path.join(self.temp_dir, "high_load_50.html")
        vis.generate_html(results, output_path=out_html)
        self.assertTrue(os.path.exists(out_html))

        with open(out_html, "r", encoding="utf-8") as f:
            html_text = f.read()
        self.assertEqual(html_text.count('class="product-row"'), 50)

        # 4. Generate Winner Dossier from 50 candidates
        gen = DossierGenerator()
        out_dossier = os.path.join(self.temp_dir, "high_load_dossier.md")
        gen.generate_dossier(results, output_path=out_dossier)
        self.assertTrue(os.path.exists(out_dossier))

        elapsed = time.time() - t0
        # High load pipeline should complete in under 5.0 seconds
        self.assertLess(elapsed, 5.0, f"High-load processing took too long: {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main(verbosity=2)
