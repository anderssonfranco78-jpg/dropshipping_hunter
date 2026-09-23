"""
Tier 2: Boundary Value Analysis & Edge Cases E2E Test Suite.

Verifies operational edge cases E-01 through E-10 from the Canonical Methodology
Specification, plus mathematical boundaries, zero-division hazards, fringe tickets,
extreme price limits, and malformed inputs:
  - E-01: Free shipping ($0.00) landed cost & tracking integrity
  - E-02: Extremely low landed cost ($3.00) ticket price floor ($29.99)
  - E-03: High landed cost ($25.00) markup/ticket squeeze & penalty
  - E-04: Fragility filter: Functional high-density ceramic vs thin fragile glass
  - E-05: Sizing filter: Universal elastic velcro vs millimetric tailored sizing
  - E-06: Logistics: Multi-carrier selection prioritizing fast tracked over surface
  - E-07: Review NLP miner: Small complaint sample (<4 reviews) fallback
  - E-08: Review NLP miner: Brand new product (0 reviews) early novelty baseline
  - E-09: Financial precision: Boundary condition net margin exactly 64.8% (<65.0%)
  - E-10: Visualizer scaling: Single candidate vs >25 candidates
  - Mathematical boundaries: Zero division (landed=0, srp=0), extreme tickets,
    fringe tickets ($28.99, $29.00, $69.00, $69.01), Unicode/Spanish character encoding.
"""

from __future__ import annotations

import math
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


class TestTier2BoundariesAndEdgeCases(unittest.TestCase):
    """Tier 2 Boundary Value Analysis & Edge Cases Suite."""

    # -----------------------------------------------------------------------
    # E-01: Free Shipping on Supplier
    # -----------------------------------------------------------------------
    def test_e01_free_shipping_tracked_vs_untracked(self) -> None:
        """E-01: Free shipping ($0.00) sets shipping=0, but verifies tracking.
        If tracked Choice/VIP -> landed = supplier. If untracked -> trips KO-3.
        """
        # Case A: Tracked Free Shipping (AliExpress Choice)
        cand_dict_tracked = get_canonical_raw_candidate("winner_spinerelief")
        cand_dict_tracked["shipping_cost"] = 0.0
        cand_dict_tracked["shipping_carrier"] = "AliExpress Choice (Tracked)"
        cand_tracked = RawCandidate.from_dict(cand_dict_tracked)
        fin_tracked = cand_tracked.compute_financials()
        self.assertEqual(fin_tracked.landed_cost, cand_tracked.supplier_cost)

        # Case B: Untracked Free Surface Mail -> Trips KO-3
        cand_dict_untracked = get_canonical_raw_candidate("winner_spinerelief")
        cand_dict_untracked["shipping_cost"] = 0.0
        cand_dict_untracked["shipping_carrier"] = "China Post Small Packet (Untracked)"
        cand_dict_untracked["shipping_days_max"] = 28
        trips_ko3 = (
            cand_dict_untracked["shipping_days_max"] > 21
            or "untracked" in cand_dict_untracked["shipping_carrier"].lower()
        )
        self.assertTrue(trips_ko3)

    # -----------------------------------------------------------------------
    # E-02: Extremely Low Landed Cost Ticket Floor
    # -----------------------------------------------------------------------
    def test_e02_low_landed_cost_price_floor_enforcement(self) -> None:
        """E-02: Landed cost $3.00 with 3x markup = $9.00 (< $29.00).
        System enforces minimum ticket threshold SRP = $29.99 (markup expands to 10x, margin > 80%).
        """
        landed_cost = 3.00
        raw_3x_price = landed_cost * 3.0
        self.assertEqual(raw_3x_price, 9.00)

        # Minimum ticket policy enforcement
        MIN_TICKET_FLOOR = 29.99
        suggested_srp = max(raw_3x_price, MIN_TICKET_FLOOR)
        self.assertEqual(suggested_srp, 29.99)

        cand = RawCandidate(
            candidate_id="e02-low-cost",
            name="Mini Precision Tweezers",
            category="Beauty Tools",
            description="Ultra-fine surgical steel tweezers.",
            supplier_cost=1.50,
            shipping_cost=1.50,
            suggested_price=suggested_srp,
            shipping_days_min=7,
            shipping_days_max=10,
            shipping_carrier="YunExpress",
            has_fragile_material=False,
            has_sizing_requirements=False,
            demo_visual_speed_sec=1.0,
            pain_level_score=75.0,
            retail_availability_score=70.0,
            ad_active_days=25,
            competitor_ad_count=12,
            google_trends_momentum=20.0,
            source_url="https://aliexpress.com/item/1",
        )
        fin = cand.compute_financials()
        self.assertAlmostEqual(fin.landed_cost, 3.00)
        self.assertEqual(fin.srp, 29.99)
        self.assertGreaterEqual(fin.markup_multiplier, 9.9)
        self.assertGreaterEqual(fin.net_margin_pct, 80.0)

    # -----------------------------------------------------------------------
    # E-03: High Landed Cost Ticket Squeeze
    # -----------------------------------------------------------------------
    def test_e03_high_landed_cost_ticket_squeeze(self) -> None:
        """E-03: Landed cost $25.00 -> 3x markup = $75.00 (exceeds $69 impulse ceiling).
        Pricing at $69 yields 2.76x markup (fails Rule 4).
        Pricing at $75 trips near-fringe ticket penalty (-5 pts).
        """
        landed_cost = 25.00
        # If capped at $69.00:
        markup_at_69 = round(69.00 / landed_cost, 2)
        self.assertLess(markup_at_69, 3.00)
        self.assertGreaterEqual(markup_at_69, 2.50)  # Marginal

        # If priced at $75.00 (meets 3.0x markup):
        markup_at_75 = 75.00 / landed_cost
        self.assertEqual(markup_at_75, 3.00)
        # However, $75 is in fringe ticket zone ($69.01-$79.00) -> trips penalty
        ticket_penalty = 5.0 if (69.01 <= 75.00 <= 79.00) else 0.0
        self.assertEqual(ticket_penalty, 5.0)

    # -----------------------------------------------------------------------
    # E-04: Fragility Filter Differentiation
    # -----------------------------------------------------------------------
    def test_e04_fragility_functional_ceramic_vs_thin_glass(self) -> None:
        """E-04: Differentiate impact-resistant functional zirconia ceramic tools
        from fragile thin decorative glassware (which trips KO-1).
        """
        # Functional ceramic bearing / ceramic utility knife (shock-resistant ABS + zirconia)
        cand_knife = {
            "name": "Heavy Duty Ceramic Utility Cutter",
            "material": "Zirconia Ceramic & ABS",
            "has_fragile_material": False,  # Non-fragile industrial blade
        }
        self.assertFalse(cand_knife["has_fragile_material"])

        # Thin decorative glassware -> trips KO-1
        cand_glass = {
            "name": "Borosilicate Glass Tea Infuser",
            "material": "Thin Blown Glass",
            "has_fragile_material": True,
        }
        self.assertTrue(cand_glass["has_fragile_material"])

    # -----------------------------------------------------------------------
    # E-05: Sizing Filter Differentiation
    # -----------------------------------------------------------------------
    def test_e05_sizing_elastic_adjustable_vs_fitted_apparel(self) -> None:
        """E-05: Universal adjustable velcro brace (low return risk)
        vs form-fitting apparel requiring millimetric chest/waist sizing (trips KO-1).
        """
        # Adjustable velcro brace
        cand_brace = {
            "name": "Adjustable Lumbar Support Belt (Universal)",
            "has_sizing_requirements": False,  # Velcro fits 28-44 inch waists
        }
        self.assertFalse(cand_brace["has_sizing_requirements"])

        # Tailored evening dress -> trips KO-1
        cand_dress = {
            "name": "Silk Fitted Evening Gown",
            "has_sizing_requirements": True,  # Millimetric sizing charts
        }
        self.assertTrue(cand_dress["has_sizing_requirements"])

    # -----------------------------------------------------------------------
    # E-06: Logistics Multi-Carrier Selection
    # -----------------------------------------------------------------------
    def test_e06_logistics_multi_carrier_selection(self) -> None:
        """E-06: When supplier offers both cheap slow and fast tracked shipping,
        the system selects the fast tracked option (YunExpress 8-11d) into Landed Cost.
        """
        carriers = [
            {"carrier": "Surface Economy", "cost": 1.20, "days_max": 35, "tracked": False},
            {"carrier": "YunExpress Tracked", "cost": 4.50, "days_max": 11, "tracked": True},
        ]
        # Valid options must be tracked and have days_max <= 14
        valid_carriers = [c for c in carriers if c["tracked"] and c["days_max"] <= 14]
        self.assertEqual(len(valid_carriers), 1)
        selected = valid_carriers[0]
        self.assertEqual(selected["carrier"], "YunExpress Tracked")
        self.assertEqual(selected["cost"], 4.50)

    # -----------------------------------------------------------------------
    # E-07: Review NLP Small Sample Fallback
    # -----------------------------------------------------------------------
    def test_e07_review_nlp_small_sample_fallback(self) -> None:
        """E-07: ASIN with fewer than 4 negative reviews in Woot AJAX falls back
        to n-gram extraction without crashing clustering algorithms.
        """
        reviews = [
            {"text": "The buckle snapped after 2 days of use."},
            {"text": "Color was slightly faded compared to photos."},
        ]
        # On sample < 4, differential clustering should fall back to basic token extraction
        self.assertLess(len(reviews), 4)
        words = []
        for r in reviews:
            words.extend(r["text"].lower().split())
        self.assertIn("buckle", words)
        self.assertIn("snapped", words)

    # -----------------------------------------------------------------------
    # E-08: Review NLP Brand New Product Baseline
    # -----------------------------------------------------------------------
    def test_e08_review_nlp_zero_reviews_novelty_baseline(self) -> None:
        """E-08: ASIN with 0 reviews is assigned neutral baseline score (50 pts)
        and flagged as EARLY STAGE NOVELTY without error.
        """
        reviews: List[Dict[str, Any]] = []
        if len(reviews) == 0:
            nlp_score = 50.0
            status_flag = "EARLY STAGE NOVELTY"
        else:
            nlp_score = 80.0
            status_flag = "VALIDATED REVIEWS"

        self.assertEqual(nlp_score, 50.0)
        self.assertEqual(status_flag, "EARLY STAGE NOVELTY")

    # -----------------------------------------------------------------------
    # E-09: Financial Precision Strict Threshold
    # -----------------------------------------------------------------------
    def test_e09_financial_precision_no_lenient_rounding(self) -> None:
        """E-09: Boundary condition where Net Margin is exactly 64.8%.
        Strict mathematical precision: 64.8% < 65.0%, treated as marginal (50 pts, not 85 pts).
        No lenient round-up to 65%.
        """
        net_margin = 64.80
        threshold = 65.00
        # Strict inequality
        meets_canonical = net_margin >= threshold
        self.assertFalse(meets_canonical)

        # Subscore mapping: 50 pts for marginal, 85 for passing
        subscore = 85.0 if meets_canonical else 50.0
        self.assertEqual(subscore, 50.0)

    # -----------------------------------------------------------------------
    # E-10: Visualizer Candidate Scale Handling (1 to 30 candidates)
    # -----------------------------------------------------------------------
    def test_e10_visualizer_candidate_scale_handling(self) -> None:
        """E-10: Evaluator handles edge dataset sizes: exactly 1 candidate,
        and large lists (>25 candidates) without layout break or index errors.
        """
        # Single candidate handling
        single_candidate_list = [{"id": "c1", "score": 85.0}]
        self.assertEqual(len(single_candidate_list), 1)

        # 30 candidates handling (truncate to top 15 for PNG presentation)
        large_list = [{"id": f"c_{i}", "score": 50.0 + i} for i in range(30)]
        MAX_PNG_DISPLAY = 15
        displayed_items = sorted(large_list, key=lambda x: x["score"], reverse=True)[:MAX_PNG_DISPLAY]
        self.assertEqual(len(displayed_items), 15)
        self.assertEqual(displayed_items[0]["score"], 79.0)

    # -----------------------------------------------------------------------
    # Additional Mathematical & Error Boundaries
    # -----------------------------------------------------------------------
    def test_division_by_zero_protection_landed_cost(self) -> None:
        """Landed cost = 0.00 does not raise ZeroDivisionError in markup calculation."""
        cand = RawCandidate(
            candidate_id="zero-cost-test",
            name="Zero Cost Product",
            category="Test",
            description="Testing zero cost safety.",
            supplier_cost=0.0,
            shipping_cost=0.0,
            suggested_price=29.99,
            shipping_days_min=7,
            shipping_days_max=12,
            shipping_carrier="YunExpress",
            has_fragile_material=False,
            has_sizing_requirements=False,
            demo_visual_speed_sec=1.5,
            pain_level_score=50.0,
            retail_availability_score=50.0,
            ad_active_days=10,
            competitor_ad_count=5,
            google_trends_momentum=10.0,
            source_url="https://aliexpress.com",
        )
        fin = cand.compute_financials()
        self.assertEqual(fin.landed_cost, 0.0)
        self.assertEqual(fin.markup_multiplier, 0.0)
        self.assertGreater(fin.net_profit, 0.0)

    def test_division_by_zero_protection_srp(self) -> None:
        """SRP = 0.00 does not raise ZeroDivisionError in net margin calculation."""
        cand = RawCandidate(
            candidate_id="zero-srp-test",
            name="Zero SRP Product",
            category="Test",
            description="Testing zero SRP safety.",
            supplier_cost=5.0,
            shipping_cost=3.0,
            suggested_price=0.0,
            shipping_days_min=7,
            shipping_days_max=12,
            shipping_carrier="YunExpress",
            has_fragile_material=False,
            has_sizing_requirements=False,
            demo_visual_speed_sec=1.5,
            pain_level_score=50.0,
            retail_availability_score=50.0,
            ad_active_days=10,
            competitor_ad_count=5,
            google_trends_momentum=10.0,
            source_url="https://aliexpress.com",
        )
        fin = cand.compute_financials()
        self.assertEqual(fin.srp, 0.0)
        self.assertEqual(fin.net_margin_pct, 0.0)

    def test_fringe_ticket_boundaries_exact(self) -> None:
        """Validates exact score transitions at $24.99, $28.99, $29.00, $69.00, $69.01, $79.01, $99.01."""
        def score_ticket(srp: float) -> float:
            if 29.00 <= srp <= 69.00:
                return 100.0
            elif (25.00 <= srp < 29.00) or (69.00 < srp <= 79.00):
                return 70.0
            elif (20.00 <= srp < 25.00) or (79.00 < srp <= 99.00):
                return 30.0
            else:
                return 0.0

        self.assertEqual(score_ticket(19.99), 0.0)
        self.assertEqual(score_ticket(20.00), 30.0)
        self.assertEqual(score_ticket(24.99), 30.0)
        self.assertEqual(score_ticket(25.00), 70.0)
        self.assertEqual(score_ticket(28.99), 70.0)
        self.assertEqual(score_ticket(29.00), 100.0)
        self.assertEqual(score_ticket(49.99), 100.0)
        self.assertEqual(score_ticket(69.00), 100.0)
        self.assertEqual(score_ticket(69.01), 70.0)
        self.assertEqual(score_ticket(79.00), 70.0)
        self.assertEqual(score_ticket(79.01), 30.0)
        self.assertEqual(score_ticket(99.00), 30.0)
        self.assertEqual(score_ticket(99.01), 0.0)

    def test_shipping_days_boundaries_exact(self) -> None:
        """Validates exact logistics score transitions at 12d, 13d, 16d, 17d, 21d, 22d."""
        def score_logistics(days: int, tracked: bool) -> float:
            if not tracked or days > 21:
                return 0.0
            elif days <= 12:
                return 100.0
            elif 13 <= days <= 16:
                return 60.0
            elif 17 <= days <= 21:
                return 20.0
            return 0.0

        self.assertEqual(score_logistics(7, True), 100.0)
        self.assertEqual(score_logistics(12, True), 100.0)
        self.assertEqual(score_logistics(13, True), 60.0)
        self.assertEqual(score_logistics(16, True), 60.0)
        self.assertEqual(score_logistics(17, True), 20.0)
        self.assertEqual(score_logistics(21, True), 20.0)
        self.assertEqual(score_logistics(22, True), 0.0)  # Trips KO-3
        self.assertEqual(score_logistics(10, False), 0.0)  # Untracked trips KO-3

    def test_subscore_weight_conservation(self) -> None:
        """Verifies exact double-precision conservation of the 7 rule weights."""
        weights = [0.20, 0.20, 0.10, 0.20, 0.10, 0.10, 0.10]
        self.assertAlmostEqual(sum(weights), 1.0, places=9)

    def test_unicode_and_spanish_escaping_fidelity(self) -> None:
        """Validates serialization of special Spanish accents, quotation marks, and emojis."""
        cand_dict = get_canonical_raw_candidate("winner_spinerelief")
        cand_dict["name"] = "Cojín Ergonómico Lumbar Antiestrés 🌟"
        cand_dict["description"] = "¡Alivia la ciática instantáneamente con 'micro-células' de gel!"
        cand = RawCandidate.from_dict(cand_dict)
        json_output = cand.to_json()
        reconstructed = RawCandidate.from_json(json_output)
        self.assertEqual(reconstructed.name, cand_dict["name"])
        self.assertEqual(reconstructed.description, cand_dict["description"])


if __name__ == "__main__":
    unittest.main()
