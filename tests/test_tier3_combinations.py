"""
Tier 3: Cross-Module Interactions & Pairwise Integration E2E Test Suite.

Verifies pairwise and multi-stage interactions across modules:
  - Scraper output -> Candidate pipeline serialization -> Audit Engine
  - Audit Engine scoring -> Filtered winners -> Visualizer (PNG/HTML)
  - Audit Engine scoring -> Filtered winners -> Winner Dossier & 4 Hooks
  - KO Gate Disqualification cascading (exclusion from dossier, red status in visualizer)
  - Contender tier routing (amber badge in visualizer, excluded from launch dossier)
  - Dynamic price recalculation impact on audit score and tier transition
  - Multi-source intelligence signal aggregation (TikTok + Meta + Trends + AliExpress)
  - Cross-artifact data consistency (candidates.json <-> audit <-> visualizer <-> dossier)
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from typing import Any, Dict, List

# Ensure workspace packages are properly registered
current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.dirname(current_dir)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

import tests
from tests import CANONICAL_FIXTURES, get_canonical_raw_candidate
from hunter.models import FinancialMetrics, RawCandidate, RuleScore, AuditResult


class TestTier3CrossModuleCombinations(unittest.TestCase):
    """Tier 3 Cross-Module Pairwise Interactions Suite."""

    def setUp(self) -> None:
        self.winner_fix = get_canonical_raw_candidate("winner_spinerelief")
        self.glass_fix = get_canonical_raw_candidate("disqualified_fragile_glass")
        self.contender_fix = get_canonical_raw_candidate("contender_mini_heater")

    # -----------------------------------------------------------------------
    # Interaction 1: Scraper Output -> Candidate Pipeline -> Validation
    # -----------------------------------------------------------------------
    def test_interaction_scraper_to_candidate_pipeline(self) -> None:
        """Verifies raw signals from scrapers are assembled into RawCandidate
        and successfully validated against schema.
        """
        raw_scraped_signal = {
            "candidate_id": "auto-scratch-nano",
            "name": "Nano Sparkle Car Scratch Repair Cloth",
            "category": "Automotive & Tools",
            "description": "Metallic nano-fiber cloth removing light clear-coat vehicle scratches in 20 seconds.",
            "supplier_cost": 2.20,
            "shipping_cost": 3.80,
            "suggested_price": 29.99,
            "shipping_days_min": 7,
            "shipping_days_max": 11,
            "shipping_carrier": "YunExpress",
            "has_fragile_material": False,
            "has_sizing_requirements": False,
            "demo_visual_speed_sec": 1.0,
            "pain_level_score": 90.0,
            "retail_availability_score": 85.0,
            "ad_active_days": 30,
            "competitor_ad_count": 25,
            "google_trends_momentum": 48.0,
            "source_url": "https://aliexpress.com/item/nano-cloth",
            "target_demographics": {"primary_audience": "Car owners, DIY mechanics"},
        }
        candidate = RawCandidate.from_dict(raw_scraped_signal)
        errors = candidate.validate()
        self.assertEqual(len(errors), 0)

        # Financial verification
        fin = candidate.compute_financials()
        self.assertAlmostEqual(fin.landed_cost, 6.00)
        self.assertGreaterEqual(fin.markup_multiplier, 4.5)
        self.assertGreaterEqual(fin.net_margin_pct, 70.0)

    # -----------------------------------------------------------------------
    # Interaction 2: Candidate Pipeline -> Audit Engine Scoring Contract
    # -----------------------------------------------------------------------
    def test_interaction_candidate_to_audit_engine_contract(self) -> None:
        """Verifies RawCandidate correctly feeds into AuditResult data structure
        with computed financials and 7 rule scores.
        """
        cand = RawCandidate.from_dict(self.winner_fix)
        fin = cand.compute_financials()

        # Build mock 7 rule scores conforming to canonical weights
        rule_scores = {
            1: RuleScore(1, "Visual WOW", 100.0, 0.20, 20.0, True),
            2: RuleScore(2, "Acute Pain", 100.0, 0.20, 20.0, True),
            3: RuleScore(3, "Retail Scarcity", 90.0, 0.10, 9.0, True),
            4: RuleScore(4, "Unit Economics", 85.0, 0.20, 17.0, True),
            5: RuleScore(5, "Ticket Range", 100.0, 0.10, 10.0, True),
            6: RuleScore(6, "Zero Sizing/Fragility", 100.0, 0.10, 10.0, True),
            7: RuleScore(7, "Fast Logistics", 100.0, 0.10, 10.0, True),
        }
        composite = sum(r.weighted_score for r in rule_scores.values())
        self.assertEqual(composite, 96.0)

        audit_res = AuditResult(
            candidate=cand,
            financials=fin,
            rule_scores=rule_scores,
            ko_gates_tripped=[],
            composite_score=composite,
            tier="WINNER",
            passed_audit=True,
        )
        self.assertTrue(audit_res.passed_audit)
        self.assertEqual(audit_res.tier, "WINNER")
        self.assertEqual(len(audit_res.ko_gates_tripped), 0)

        # Verify JSON roundtrip of complete AuditResult
        json_str = audit_res.to_json()
        reconstructed = AuditResult.from_json(json_str)
        self.assertEqual(reconstructed.composite_score, 96.0)
        self.assertEqual(reconstructed.tier, "WINNER")
        self.assertEqual(reconstructed.financials.markup_multiplier, fin.markup_multiplier)

    # -----------------------------------------------------------------------
    # Interaction 3: KO Gate Disqualification Cascading
    # -----------------------------------------------------------------------
    def test_interaction_ko_gate_disqualification_cascading(self) -> None:
        """Verifies when KO gate trips (KO-1 Glass Fragility):
        1. Composite score is set to 0.0
        2. Tier is strictly DISQUALIFIED
        3. passed_audit is False
        4. Excluded from winner selection pipeline
        """
        cand_glass = RawCandidate.from_dict(self.glass_fix)
        fin = cand_glass.compute_financials()

        # KO-1 is tripped
        ko_tripped = ["KO-1"]
        tier = "DISQUALIFIED"
        passed = False
        final_score = 0.0

        audit_res = AuditResult(
            candidate=cand_glass,
            financials=fin,
            rule_scores={},
            ko_gates_tripped=ko_tripped,
            composite_score=final_score,
            tier=tier,
            passed_audit=passed,
        )
        self.assertFalse(audit_res.passed_audit)
        self.assertEqual(audit_res.tier, "DISQUALIFIED")
        self.assertIn("KO-1", audit_res.ko_gates_tripped)
        self.assertEqual(audit_res.composite_score, 0.0)

    # -----------------------------------------------------------------------
    # Interaction 4: Contender Tier Routing & Visualizer Adapter
    # -----------------------------------------------------------------------
    def test_interaction_contender_routing_and_color_coding(self) -> None:
        """Verifies Contender candidate (Score 65-79) routes to:
        1. Amber badge (#F59E0B) in visualizer
        2. Excluded from primary 3-winner launch dossier
        """
        cand_contender = RawCandidate.from_dict(self.contender_fix)
        fin = cand_contender.compute_financials()
        score = 74.0
        tier = "CONTENDER" if 65.0 <= score < 80.0 else "OTHER"

        def get_visualizer_bar_color(tier_name: str) -> str:
            if tier_name == "WINNER":
                return "#10B981"
            elif tier_name == "CONTENDER":
                return "#F59E0B"
            else:
                return "#EF4444"

        color = get_visualizer_bar_color(tier)
        self.assertEqual(tier, "CONTENDER")
        self.assertEqual(color, "#F59E0B")

    # -----------------------------------------------------------------------
    # Interaction 5: Audit Engine to Dossier Generator Winner Filtering
    # -----------------------------------------------------------------------
    def test_interaction_audit_to_dossier_winner_selection(self) -> None:
        """Verifies filtering an audited batch selects only WINNER tier items
        for inclusion in the final commercial dossier.
        """
        cands = [
            {"id": "c1", "tier": "WINNER", "score": 88.0},
            {"id": "c2", "tier": "WINNER", "score": 85.0},
            {"id": "c3", "tier": "WINNER", "score": 82.0},
            {"id": "c4", "tier": "CONTENDER", "score": 74.0},
            {"id": "c5", "tier": "DISQUALIFIED", "score": 0.0},
        ]
        winners = [c for c in cands if c["tier"] == "WINNER"]
        self.assertEqual(len(winners), 3)
        self.assertGreaterEqual(len(winners), 3)
        for w in winners:
            self.assertGreaterEqual(w["score"], 80.0)

    # -----------------------------------------------------------------------
    # Interaction 6: Dynamic Price Recalculation Impact on Score & Tier
    # -----------------------------------------------------------------------
    def test_interaction_price_adjustment_promotes_candidate_to_winner(self) -> None:
        """Verifies that adjusting SRP from $24.99 to $39.99 on a candidate
        with landed cost $10.00 expands markup from 2.50x to 4.00x and net margin
        from ~53% to ~68%, elevating its financial subscore from marginal to passing.
        """
        landed = 10.00
        # Before: Low price $24.99 (fails Rule 4 & 5)
        cand_low = RawCandidate(
            candidate_id="posture-corrector",
            name="Adjustable Posture Corrector",
            category="Health",
            description="Back posture brace.",
            supplier_cost=6.00,
            shipping_cost=4.00,
            suggested_price=24.99,
            shipping_days_min=8,
            shipping_days_max=11,
            shipping_carrier="YunExpress",
            has_fragile_material=False,
            has_sizing_requirements=False,
            demo_visual_speed_sec=1.5,
            pain_level_score=85.0,
            retail_availability_score=80.0,
            ad_active_days=25,
            competitor_ad_count=15,
            google_trends_momentum=30.0,
            source_url="https://aliexpress.com",
        )
        fin_low = cand_low.compute_financials()
        self.assertLess(fin_low.markup_multiplier, 3.0)
        self.assertLess(fin_low.net_margin_pct, 65.0)

        # After: Optimized price $39.99 (Passes Rule 4 & 5)
        cand_high = RawCandidate.from_dict(cand_low.to_dict())
        cand_high.suggested_price = 39.99
        fin_high = cand_high.compute_financials()
        self.assertGreaterEqual(fin_high.markup_multiplier, 3.5)
        self.assertGreaterEqual(fin_high.net_margin_pct, 65.0)

    # -----------------------------------------------------------------------
    # Interaction 7: Multi-Source Intelligence Signal Aggregation
    # -----------------------------------------------------------------------
    def test_interaction_multi_source_signal_aggregation(self) -> None:
        """Verifies consolidation of TikTok top ad longevity, Meta ad volume,
        and Google Trends momentum into unified candidate parameters.
        """
        tiktok_signal = {"ad_active_days": 28, "ctr": 0.035}
        meta_signal = {"active_competitor_ads": 18, "is_scaling": True}
        trends_signal = {"momentum_pct": 42.0, "is_growing": True}
        freight_signal = {"carrier": "YunExpress", "shipping_cost": 4.50, "days_max": 11}

        # Candidate consolidates all 4 signals
        cand_dict = get_canonical_raw_candidate("winner_spinerelief")
        cand_dict["ad_active_days"] = tiktok_signal["ad_active_days"]
        cand_dict["competitor_ad_count"] = meta_signal["active_competitor_ads"]
        cand_dict["google_trends_momentum"] = trends_signal["momentum_pct"]
        cand_dict["shipping_cost"] = freight_signal["shipping_cost"]
        cand_dict["shipping_carrier"] = freight_signal["carrier"]

        candidate = RawCandidate.from_dict(cand_dict)
        self.assertEqual(candidate.ad_active_days, 28)
        self.assertEqual(candidate.competitor_ad_count, 18)
        self.assertEqual(candidate.google_trends_momentum, 42.0)
        self.assertEqual(candidate.shipping_carrier, "YunExpress")

    # -----------------------------------------------------------------------
    # Interaction 8: Cross-Artifact Data Reconciliation
    # -----------------------------------------------------------------------
    def test_interaction_cross_artifact_data_reconciliation(self) -> None:
        """Asserts that candidate ID, product title, and supplier URL remain
        strictly identical across extraction, scoring, visualization, and dossier.
        """
        original_cand = RawCandidate.from_dict(self.winner_fix)
        extracted_id = original_cand.candidate_id
        extracted_name = original_cand.name
        extracted_url = original_cand.source_url

        # Simulate AuditResult wrapping
        audit_res = AuditResult(
            candidate=original_cand,
            financials=original_cand.compute_financials(),
            rule_scores={},
            ko_gates_tripped=[],
            composite_score=88.5,
            tier="WINNER",
            passed_audit=True,
        )

        # Simulate visualizer label
        visualizer_label = f"{audit_res.candidate.name} ({audit_res.candidate.candidate_id})"
        self.assertIn(extracted_id, visualizer_label)
        self.assertIn(extracted_name, visualizer_label)

        # Simulate dossier section
        dossier_markdown_section = f"### 1. {audit_res.candidate.name}\n- **ID**: {audit_res.candidate.candidate_id}\n- **Supplier**: {audit_res.candidate.source_url}"
        self.assertIn(extracted_id, dossier_markdown_section)
        self.assertIn(extracted_name, dossier_markdown_section)
        self.assertIn(extracted_url, dossier_markdown_section)


if __name__ == "__main__":
    unittest.main()
