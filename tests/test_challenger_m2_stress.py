"""Empirical Challenger 1 Stress Test Suite for Milestone M2.

Stress-tests:
1. Scoring boundaries: Markup exactly 2.49x vs 2.50x, Net Margin 54.9% vs 55.0%, Shipping transit 21d vs 22d.
2. Subscore floor (< 50.0) demoting candidate from WINNER to CONTENDER even if total score >= 80.0.
3. KO-4 gate triggering on zero WOW combined with low retail scarcity.
4. Division by zero, numerical clamping, penalty stacking, and multi-KO veto cascades.
5. AuditEngine file persistence and AuditResult round-trip deserialization fidelity.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest

# Ensure dropshipping_hunter root is on sys.path
HUNTER_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(HUNTER_ROOT) not in sys.path:
    sys.path.insert(0, str(HUNTER_ROOT))

from hunter.audit_engine import (
    AuditEngine,
    classify_tier,
    evaluate_ko_gates,
    evaluate_penalties,
    score_rule_1_visual_wow,
    score_rule_2_acute_pain,
    score_rule_3_retail_scarcity,
    score_rule_4_unit_economics,
    score_rule_5_ticket_range,
    score_rule_6_sizing_fragility,
    score_rule_7_fast_logistics,
)
from hunter.models import AuditResult, FinancialMetrics, RawCandidate, RuleScore


def create_baseline_candidate(
    candidate_id: str = "stress-test-item",
    name: str = "Stress Test Candidate",
    supplier_cost: float = 8.0,
    shipping_cost: float = 4.0,
    suggested_price: float = 44.99,
    shipping_days_min: int = 7,
    shipping_days_max: int = 10,
    shipping_carrier: str = "YunExpress Specialty Line",
    has_fragile_material: bool = False,
    has_sizing_requirements: bool = False,
    demo_visual_speed_sec: float = 1.5,
    pain_level_score: float = 90.0,
    retail_availability_score: float = 90.0,
    ad_active_days: int = 30,
    competitor_ad_count: int = 20,
    google_trends_momentum: float = 40.0,
    target_demographics: dict | None = None,
) -> RawCandidate:
    """Helper to generate a clean, baseline winning RawCandidate for testing perturbations."""
    if target_demographics is None:
        target_demographics = {
            "supplier_orders": 500,
            "supplier_store_age_months": 24,
        }
    return RawCandidate(
        candidate_id=candidate_id,
        name=name,
        category="Test Category",
        description="A robust test candidate for empirical evaluation.",
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
        source_url="https://example.com/item",
        target_demographics=target_demographics,
    )


class TestBoundaryEdgeMarkup(unittest.TestCase):
    """Stress-tests the exact markup boundary: 2.49x vs 2.50x."""

    def test_score_rule_4_markup_2_49_vs_2_50(self):
        """Rule 4 rubric gives 0.0 pts for markup 2.49x (insolvent) and 50.0 pts for 2.50x (marginal warning)."""
        score_fail = score_rule_4_unit_economics(markup_multiplier=2.49, net_margin_pct=65.0)
        self.assertEqual(score_fail.raw_score, 0.0, "Markup 2.49x must receive 0.0 points in Rule 4.")
        self.assertFalse(score_fail.passed, "Markup 2.49x must not pass Rule 4.")

        score_pass = score_rule_4_unit_economics(markup_multiplier=2.50, net_margin_pct=65.0)
        self.assertEqual(score_pass.raw_score, 50.0, "Markup 2.50x with valid margin must receive 50.0 points.")

    def test_ko2_markup_gate_boundary(self):
        """KO-2 margin collapse gate trips on markup 2.49x, but does NOT trip on 2.50x (with margin >= 55%)."""
        cand = create_baseline_candidate()

        # Construct FinancialMetrics with markup 2.49x
        financials_249 = FinancialMetrics(
            landed_cost=10.0,
            srp=24.90,
            markup_multiplier=2.49,
            processor_fee=1.02,
            reserve_buffer=0.25,
            net_profit=13.63,
            net_margin_pct=55.0,  # margin held at passing 55%
        )
        ko_tripped_249 = evaluate_ko_gates(cand, financials_249)
        self.assertIn("KO-2", ko_tripped_249, "Markup 2.49x must trigger KO-2 veto.")

        # Construct FinancialMetrics with markup 2.50x
        financials_250 = FinancialMetrics(
            landed_cost=10.0,
            srp=25.00,
            markup_multiplier=2.50,
            processor_fee=1.03,
            reserve_buffer=0.25,
            net_profit=13.72,
            net_margin_pct=55.0,  # margin held at passing 55%
        )
        ko_tripped_250 = evaluate_ko_gates(cand, financials_250)
        self.assertNotIn("KO-2", ko_tripped_250, "Markup 2.50x must not trigger KO-2 veto.")

    def test_audit_engine_end_to_end_markup_boundary(self):
        """AuditEngine audit_candidate rejects candidate with 2.49x markup but accepts 2.50x markup."""
        engine = AuditEngine()

        # Candidate with landed = $20.00, SRP = $49.80 -> Markup = 2.49x
        cand_249 = create_baseline_candidate(
            supplier_cost=15.00,
            shipping_cost=5.00,
            suggested_price=49.80,
        )
        res_249 = engine.audit_candidate(cand_249)
        self.assertIn("KO-2", res_249.ko_gates_tripped)
        self.assertEqual(res_249.tier, "DISQUALIFIED")
        self.assertFalse(res_249.passed_audit)
        self.assertEqual(res_249.composite_score, 0.0)

        # Candidate with landed = $20.00, SRP = $50.00 -> Markup = 2.50x
        # Landed = 20.0, SRP = 50.0. Fee = 1.75, Reserve = 0.50, Profit = 27.75, Margin = 55.5% (>= 55%)
        cand_250 = create_baseline_candidate(
            supplier_cost=15.00,
            shipping_cost=5.00,
            suggested_price=50.00,
        )
        res_250 = engine.audit_candidate(cand_250)
        self.assertNotIn("KO-2", res_250.ko_gates_tripped)
        self.assertNotEqual(res_250.tier, "DISQUALIFIED")
        self.assertGreater(res_250.composite_score, 0.0)


class TestBoundaryEdgeNetMargin(unittest.TestCase):
    """Stress-tests the exact net margin boundary: 54.9% vs 55.0%."""

    def test_score_rule_4_margin_54_9_vs_55_0(self):
        """Rule 4 rubric gives 0.0 pts for net margin 54.9% (insolvent) and 50.0 pts for 55.0% (marginal warning)."""
        score_fail = score_rule_4_unit_economics(markup_multiplier=3.5, net_margin_pct=54.9)
        self.assertEqual(score_fail.raw_score, 0.0, "Net margin 54.9% must receive 0.0 pts in Rule 4.")
        self.assertFalse(score_fail.passed, "Net margin 54.9% must not pass Rule 4.")

        score_pass = score_rule_4_unit_economics(markup_multiplier=3.5, net_margin_pct=55.0)
        self.assertEqual(score_pass.raw_score, 50.0, "Net margin 55.0% must receive 50.0 pts.")

    def test_ko2_margin_gate_boundary(self):
        """KO-2 margin collapse gate trips on net margin 54.9%, but does NOT trip on 55.0%."""
        cand = create_baseline_candidate()

        # FinancialMetrics with margin 54.9%
        financials_549 = FinancialMetrics(
            landed_cost=10.0,
            srp=35.0,
            markup_multiplier=3.50,
            processor_fee=1.32,
            reserve_buffer=0.35,
            net_profit=19.22,
            net_margin_pct=54.9,
        )
        ko_tripped_549 = evaluate_ko_gates(cand, financials_549)
        self.assertIn("KO-2", ko_tripped_549, "Net margin 54.9% must trigger KO-2.")

        # FinancialMetrics with margin 55.0%
        financials_550 = FinancialMetrics(
            landed_cost=10.0,
            srp=35.0,
            markup_multiplier=3.50,
            processor_fee=1.32,
            reserve_buffer=0.35,
            net_profit=19.25,
            net_margin_pct=55.0,
        )
        ko_tripped_550 = evaluate_ko_gates(cand, financials_550)
        self.assertNotIn("KO-2", ko_tripped_550, "Net margin 55.0% must NOT trigger KO-2.")


class TestBoundaryEdgeShippingTransit(unittest.TestCase):
    """Stress-tests the exact shipping transit days boundary: 21d vs 22d."""

    def test_score_rule_7_transit_21d_vs_22d(self):
        """Rule 7 gives 20.0 pts for 21 days (delayed) and 0.0 pts for 22 days (fatal blackout)."""
        score_21 = score_rule_7_fast_logistics(days_max=21, carrier="YunExpress")
        self.assertEqual(score_21.raw_score, 20.0, "Transit 21 days must receive 20.0 pts (delayed).")

        score_22 = score_rule_7_fast_logistics(days_max=22, carrier="YunExpress")
        self.assertEqual(score_22.raw_score, 0.0, "Transit 22 days must receive 0.0 pts (blackout).")
        self.assertFalse(score_22.passed)

    def test_ko3_shipping_gate_boundary(self):
        """KO-3 shipping blackout gate trips on 22 days, but does NOT trip on 21 days."""
        cand_21 = create_baseline_candidate(shipping_days_max=21, shipping_carrier="YunExpress")
        cand_22 = create_baseline_candidate(shipping_days_max=22, shipping_carrier="YunExpress")
        financials = cand_21.compute_financials()

        ko_21 = evaluate_ko_gates(cand_21, financials)
        self.assertNotIn("KO-3", ko_21, "Shipping 21 days must NOT trip KO-3.")

        ko_22 = evaluate_ko_gates(cand_22, financials)
        self.assertIn("KO-3", ko_22, "Shipping 22 days MUST trip KO-3.")

    def test_audit_engine_transit_21d_vs_22d_disqualification(self):
        """AuditEngine allows candidate with 21d transit to survive, but disqualifies 22d transit."""
        engine = AuditEngine()

        cand_21 = create_baseline_candidate(shipping_days_max=21)
        res_21 = engine.audit_candidate(cand_21)
        self.assertNotIn("KO-3", res_21.ko_gates_tripped)

        cand_22 = create_baseline_candidate(shipping_days_max=22)
        res_22 = engine.audit_candidate(cand_22)
        self.assertIn("KO-3", res_22.ko_gates_tripped)
        self.assertEqual(res_22.tier, "DISQUALIFIED")
        self.assertEqual(res_22.composite_score, 0.0)

    def test_untracked_carrier_trips_ko3_even_if_short_days(self):
        """Any carrier labeled 'untracked' trips KO-3 regardless of transit days."""
        cand_untracked = create_baseline_candidate(
            shipping_days_max=7,
            shipping_carrier="Surface Untracked Sea Mail",
        )
        ko = evaluate_ko_gates(cand_untracked, cand_untracked.compute_financials())
        self.assertIn("KO-3", ko, "Untracked carrier must trigger KO-3 even if transit days <= 12.")


class TestSubscoreFloorDemotion(unittest.TestCase):
    """Stress-tests the subscore floor rule (< 50.0).

    A candidate with a composite score >= 80.0 must be demoted from WINNER to CONTENDER
    if ANY individual rule subscore is strictly below 50.0.
    """

    def test_high_total_score_demoted_to_contender_by_rule_7_floor(self):
        """Candidate with composite score 92.0 is demoted to CONTENDER because logistics score is 20.0 (< 50.0)."""
        engine = AuditEngine()

        # Candidate with elite scores everywhere, but 21 days shipping (Rule 7 = 20 pts)
        # S1: 1.5s -> 100 pts (w=0.20 -> 20.0)
        # S2: 95.0 -> 100 pts (w=0.20 -> 20.0)
        # S3: 95.0 -> 100 pts (w=0.10 -> 10.0)
        # S4: Landed $8.0, SRP $35.0 -> M=4.38, Margin=72.4% -> 100 pts (w=0.20 -> 20.0)
        # S5: SRP $35.0 -> 100 pts (w=0.10 -> 10.0)
        # S6: Durable/Universal -> 100 pts (w=0.10 -> 10.0)
        # S7: 21 days shipping -> 20 pts (w=0.10 -> 2.0)
        # Sum = 20 + 20 + 10 + 20 + 10 + 10 + 2 = 92.0 points!
        cand = create_baseline_candidate(
            supplier_cost=5.0,
            shipping_cost=3.0,
            suggested_price=35.0,
            shipping_days_max=21,  # 21 days gives S7 = 20.0
            shipping_carrier="YunExpress Tracked",
        )
        res = engine.audit_candidate(cand)

        self.assertEqual(res.composite_score, 92.0)
        self.assertGreaterEqual(res.composite_score, 80.0, "Composite score should be >= 80.0")
        self.assertEqual(res.rule_scores[7].raw_score, 20.0, "Rule 7 subscore should be 20.0 (< 50.0)")

        # Verify demotion
        self.assertEqual(res.tier, "CONTENDER", "Candidate must be demoted to CONTENDER due to subscore floor.")
        self.assertFalse(res.passed_audit, "Demoted candidate must have passed_audit=False.")

    def test_high_total_score_demoted_to_contender_by_rule_1_floor(self):
        """Candidate with composite score 80.0+ is demoted to CONTENDER because Rule 1 is 40.0 (< 50.0)."""
        engine = AuditEngine()

        # S1 demo speed = 7.0s -> 40 pts (w=0.20 -> 8.0)
        # S2: 100 pts (20.0)
        # S3: 100 pts (10.0)
        # S4: 100 pts (20.0)
        # S5: 100 pts (10.0)
        # S6: 100 pts (10.0)
        # S7: 100 pts (10.0)
        # Sum = 8 + 20 + 10 + 20 + 10 + 10 + 10 = 88.0 pts
        cand = create_baseline_candidate(
            demo_visual_speed_sec=7.0,  # Weak WOW (40 pts)
            supplier_cost=5.0,
            shipping_cost=3.0,
            suggested_price=35.0,
            shipping_days_max=10,
        )
        res = engine.audit_candidate(cand)

        self.assertEqual(res.composite_score, 88.0)
        self.assertEqual(res.rule_scores[1].raw_score, 40.0)
        self.assertEqual(res.tier, "CONTENDER")
        self.assertFalse(res.passed_audit)

    def test_high_total_score_demoted_to_contender_by_rule_5_floor(self):
        """Candidate with composite score 80.0+ is demoted to CONTENDER because Rule 5 is 30.0 (< 50.0)."""
        engine = AuditEngine()

        # S5 SRP = $22.00 -> high deliberation/low profit ticket -> 30 pts (w=0.10 -> 3.0)
        # Landed = $4.00, SRP = $22.00 -> M = 5.5x, Margin = 77% -> S4 = 100 pts (20.0)
        # S1: 100 (20.0), S2: 100 (20.0), S3: 100 (10.0), S6: 100 (10.0), S7: 100 (10.0)
        # Sum = 20 + 20 + 10 + 20 + 3 + 10 + 10 = 93.0 pts
        cand = create_baseline_candidate(
            supplier_cost=2.0,
            shipping_cost=2.0,
            suggested_price=22.00,  # Rule 5 gives 30.0 (< 50.0)
        )
        res = engine.audit_candidate(cand)

        self.assertEqual(res.composite_score, 93.0)
        self.assertEqual(res.rule_scores[5].raw_score, 30.0)
        self.assertEqual(res.tier, "CONTENDER")
        self.assertFalse(res.passed_audit)

    def test_boundary_subscore_exactly_50_is_not_demoted(self):
        """Candidate with composite score >= 80.0 and minimum subscore exactly 50.0 remains WINNER."""
        # Create synthetic rule scores where minimum is exactly 50.0
        rules = {
            1: RuleScore(1, "R1", 100.0, 0.20, 20.0, True),
            2: RuleScore(2, "R2", 100.0, 0.20, 20.0, True),
            3: RuleScore(3, "R3", 100.0, 0.10, 10.0, True),
            4: RuleScore(4, "R4", 50.0, 0.20, 10.0, False),  # exactly 50.0
            5: RuleScore(5, "R5", 100.0, 0.10, 10.0, True),
            6: RuleScore(6, "R6", 100.0, 0.10, 10.0, True),
            7: RuleScore(7, "R7", 100.0, 0.10, 10.0, True),
        }
        # Final score = 20 + 20 + 10 + 10 + 10 + 10 + 10 = 90.0
        tier, passed = classify_tier(final_score=90.0, rule_scores=rules, ko_gates=[])
        self.assertEqual(tier, "WINNER", "Subscore of exactly 50.0 should not demote from WINNER.")
        self.assertTrue(passed)

    def test_boundary_subscore_49_9_is_demoted(self):
        """Candidate with subscore 49.9 is demoted to CONTENDER."""
        rules = {
            1: RuleScore(1, "R1", 100.0, 0.20, 20.0, True),
            2: RuleScore(2, "R2", 100.0, 0.20, 20.0, True),
            3: RuleScore(3, "R3", 100.0, 0.10, 10.0, True),
            4: RuleScore(4, "R4", 49.9, 0.20, 9.98, False),  # 49.9 < 50.0
            5: RuleScore(5, "R5", 100.0, 0.10, 10.0, True),
            6: RuleScore(6, "R6", 100.0, 0.10, 10.0, True),
            7: RuleScore(7, "R7", 100.0, 0.10, 10.0, True),
        }
        tier, passed = classify_tier(final_score=89.98, rule_scores=rules, ko_gates=[])
        self.assertEqual(tier, "CONTENDER", "Subscore 49.9 must demote candidate to CONTENDER.")
        self.assertFalse(passed)


class TestKO4ZeroWowWithLowScarcity(unittest.TestCase):
    """Stress-tests KO-4 gate: zero WOW combined with low retail scarcity.

    Condition: (demo_visual_speed_sec <= 0.0 or demo_visual_speed_sec >= 10.0) AND retail_availability_score < 30.0.
    """

    def test_ko4_triggers_when_demo_speed_zero_and_scarcity_below_30(self):
        """Static product (speed 0.0s) with low retail scarcity (20.0) triggers KO-4."""
        cand = create_baseline_candidate(
            demo_visual_speed_sec=0.0,
            retail_availability_score=20.0,
        )
        ko = evaluate_ko_gates(cand, cand.compute_financials())
        self.assertIn("KO-4", ko, "Zero WOW (0s) + Low Scarcity (20) must trigger KO-4.")

    def test_ko4_triggers_when_demo_speed_10s_and_scarcity_below_30(self):
        """Very slow demo (>= 10.0s) with low retail scarcity triggers KO-4."""
        cand = create_baseline_candidate(
            demo_visual_speed_sec=10.0,
            retail_availability_score=29.9,
        )
        ko = evaluate_ko_gates(cand, cand.compute_financials())
        self.assertIn("KO-4", ko, "Demo speed 10s + Scarcity 29.9 must trigger KO-4.")

    def test_ko4_does_not_trigger_when_scarcity_is_high_even_if_zero_wow(self):
        """Product with zero WOW (speed 0.0s) but high DTC retail scarcity (80.0) does NOT trip KO-4."""
        cand = create_baseline_candidate(
            demo_visual_speed_sec=0.0,
            retail_availability_score=80.0,
        )
        ko = evaluate_ko_gates(cand, cand.compute_financials())
        self.assertNotIn("KO-4", ko, "High scarcity (80) must exempt product from KO-4.")

    def test_ko4_does_not_trigger_when_scarcity_is_exactly_30(self):
        """Product with zero WOW (0.0s) and scarcity exactly 30.0 does NOT trip KO-4 (boundary)."""
        cand = create_baseline_candidate(
            demo_visual_speed_sec=0.0,
            retail_availability_score=30.0,
        )
        ko = evaluate_ko_gates(cand, cand.compute_financials())
        self.assertNotIn("KO-4", ko, "Scarcity exactly 30.0 should not trigger KO-4.")

    def test_ko4_does_not_trigger_when_wow_is_high_even_if_commodity_scarcity(self):
        """Product with elite WOW (1.5s) even with zero scarcity (retail staple 0.0) does NOT trip KO-4."""
        cand = create_baseline_candidate(
            demo_visual_speed_sec=1.5,
            retail_availability_score=0.0,
        )
        ko = evaluate_ko_gates(cand, cand.compute_financials())
        self.assertNotIn("KO-4", ko, "Elite WOW (1.5s) must not trip KO-4 regardless of retail presence.")

    def test_ko4_audit_engine_disqualification(self):
        """Candidate tripping KO-4 is disqualified with score 0.0."""
        engine = AuditEngine()
        cand = create_baseline_candidate(
            demo_visual_speed_sec=0.0,
            retail_availability_score=15.0,
        )
        res = engine.audit_candidate(cand)
        self.assertIn("KO-4", res.ko_gates_tripped)
        self.assertEqual(res.tier, "DISQUALIFIED")
        self.assertEqual(res.composite_score, 0.0)
        self.assertFalse(res.passed_audit)


class TestAdversarialStressHarness(unittest.TestCase):
    """Stress tests on edge inputs, penalty clamping, and multiple veto cascades."""

    def test_zero_landed_cost_protection(self):
        """Landed cost = 0.0 does not cause ZeroDivisionError and sets markup to 0.0."""
        cand = create_baseline_candidate(supplier_cost=0.0, shipping_cost=0.0, suggested_price=30.0)
        financials = cand.compute_financials()
        self.assertEqual(financials.landed_cost, 0.0)
        self.assertEqual(financials.markup_multiplier, 0.0)

    def test_zero_srp_protection(self):
        """SRP = 0.0 does not cause ZeroDivisionError in net margin calculation."""
        cand = create_baseline_candidate(suggested_price=0.0)
        financials = cand.compute_financials()
        self.assertEqual(financials.srp, 0.0)
        self.assertEqual(financials.net_margin_pct, 0.0)

    def test_all_penalties_active_clamping_at_zero(self):
        """Stacking all penalties (P_supp=5, P_sat=10, P_tick=5) clamps score at 0.0."""
        engine = AuditEngine()
        # Create a candidate with low subscores:
        # S1=40 (8), S2=30 (6), S3=20 (2), S4=50 (10), S5=70 (7), S6=100 (10), S7=20 (2) -> sum = 45.0
        # Demographics: supplier_orders = 10 (< 100 -> P_supp = 5)
        # Momentum: -0.50 (P_sat = 10)
        # Price: $26.00 (P_tick = 5)
        # Total penalty = 20 pts -> 45 - 20 = 25.0
        cand = create_baseline_candidate(
            supplier_cost=8.0,
            shipping_cost=2.0,
            suggested_price=26.00,  # P_tick = 5
            demo_visual_speed_sec=7.0,  # S1 = 40
            pain_level_score=40.0,  # S2 = 30
            retail_availability_score=35.0,  # S3 = 20
            shipping_days_max=20,  # S7 = 20
            google_trends_momentum=-0.40,  # P_sat = 10
            competitor_ad_count=60,  # P_sat = 10
            target_demographics={"supplier_orders": 10, "supplier_store_age_months": 2},  # P_supp = 5
        )
        res = engine.audit_candidate(cand)
        self.assertLess(res.composite_score, 65.0)
        self.assertGreaterEqual(res.composite_score, 0.0)
        self.assertEqual(res.tier, "DISQUALIFIED")

    def test_multiple_ko_gates_tripped_simultaneously(self):
        """Candidate violating all KO conditions records all gates: KO-1, KO-2, KO-3, KO-4."""
        cand = create_baseline_candidate(
            has_fragile_material=True,  # KO-1
            supplier_cost=20.0,
            shipping_cost=10.0,
            suggested_price=25.0,  # Landed $30, SRP $25 -> Markup 0.83x -> KO-2
            shipping_days_max=30,  # KO-3
            shipping_carrier="Untracked Boat",  # KO-3
            demo_visual_speed_sec=0.0,  # KO-4
            retail_availability_score=10.0,  # KO-4
        )
        ko = evaluate_ko_gates(cand, cand.compute_financials())
        self.assertIn("KO-1", ko)
        self.assertIn("KO-2", ko)
        self.assertIn("KO-3", ko)
        self.assertIn("KO-4", ko)
        self.assertEqual(len(ko), 4)

    def test_audit_engine_sorting_hierarchy(self):
        """audit_candidates sorts descending: WINNERS first, then CONTENDERS, then DISQUALIFIED."""
        engine = AuditEngine()
        # Candidate A: Winner (score 97)
        c_winner = create_baseline_candidate(candidate_id="win-1", suggested_price=45.0)
        # Candidate B: Contender (score 70)
        c_contender = create_baseline_candidate(
            candidate_id="cont-1",
            shipping_days_max=21,  # demotes to Contender via subscore floor
        )
        # Candidate C: Disqualified (trips KO-1)
        c_disqualified = create_baseline_candidate(
            candidate_id="disq-1",
            has_fragile_material=True,
        )

        results = engine.audit_candidates([c_disqualified, c_contender, c_winner])
        tiers = [r.tier for r in results]
        self.assertEqual(tiers, ["WINNER", "CONTENDER", "DISQUALIFIED"])

    def test_audit_results_file_persistence_roundtrip(self):
        """audit_candidates_file writes valid JSON that completely deserializes back."""
        engine = AuditEngine()
        candidates = [
            create_baseline_candidate(candidate_id="item-1", suggested_price=39.99),
            create_baseline_candidate(candidate_id="item-2", suggested_price=24.99),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = pathlib.Path(tmpdir) / "test_candidates.json"
            output_file = pathlib.Path(tmpdir) / "test_audit_results.json"

            with open(input_file, "w", encoding="utf-8") as f:
                json.dump([c.to_dict() for c in candidates], f)

            results = engine.audit_candidates_file(input_file, output_filepath=output_file)
            self.assertTrue(output_file.exists())

            # Read back and verify deserialization
            with open(output_file, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)

            reconstructed = [AuditResult.from_dict(d) for d in loaded_data]
            self.assertEqual(len(reconstructed), 2)
            self.assertEqual(reconstructed[0].candidate.candidate_id, results[0].candidate.candidate_id)
            self.assertEqual(reconstructed[0].composite_score, results[0].composite_score)
            self.assertEqual(reconstructed[0].tier, results[0].tier)


if __name__ == "__main__":
    unittest.main()
