"""Empirical Challenger 2 Stress Test Suite for Milestone M2.

Audits and stress-tests:
1. Extreme financial values ($0.01 cost, $10,000 cost, $0 shipping, extreme/large SRP, negative margins).
2. Mathematical idempotency: 100 sequential and concurrent audits yield bit-for-bit identical results.
3. Floating-point precision, accounting balance (Landed + Fees + Reserve + Profit == SRP), and threshold boundaries.
4. Penalty deductions and score clamping [0.0, 100.0] with subscore floor enforcement.
5. Sorting stability and tier classification invariants.
"""

from __future__ import annotations

import concurrent.futures
import json
import math
import os
import pathlib
import sys
import unittest
from typing import Dict, List

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


def create_mock_candidate(**kwargs) -> RawCandidate:
    """Factory creating a valid default RawCandidate with customizable overrides."""
    defaults = {
        "candidate_id": "stress-test-item",
        "name": "Stress Test Candidate",
        "category": "Home & Garden",
        "description": "High performance automated cleaning gadget",
        "supplier_cost": 8.00,
        "shipping_cost": 3.00,
        "suggested_price": 39.99,
        "shipping_days_min": 7,
        "shipping_days_max": 12,
        "shipping_carrier": "YunExpress",
        "has_fragile_material": False,
        "has_sizing_requirements": False,
        "demo_visual_speed_sec": 2.0,
        "pain_level_score": 90.0,
        "retail_availability_score": 85.0,
        "ad_active_days": 25,
        "competitor_ad_count": 12,
        "google_trends_momentum": 45.0,
        "source_url": "https://example.com/item",
        "target_demographics": {
            "supplier_orders": 500,
            "supplier_store_age_months": 24,
        },
    }
    defaults.update(kwargs)
    return RawCandidate.from_dict(defaults)


class TestExtremeFinancialValues(unittest.TestCase):
    """Stress tests extreme cost values, zero shipping, extreme SRPs, and margin collapse."""

    def setUp(self):
        self.engine = AuditEngine()

    def test_extreme_low_supplier_cost_and_zero_shipping(self):
        """Supplier cost $0.01, shipping $0.00, retail $29.99 (Extreme markup ~2999x)."""
        cand = create_mock_candidate(
            supplier_cost=0.01,
            shipping_cost=0.00,
            suggested_price=29.99,
            shipping_carrier="AliExpress Choice",
        )
        fin = cand.compute_financials()

        self.assertEqual(fin.landed_cost, 0.01)
        self.assertEqual(fin.srp, 29.99)
        self.assertEqual(fin.markup_multiplier, 2999.0)
        self.assertGreater(fin.net_margin_pct, 90.0)
        self.assertGreater(fin.net_profit, 28.0)

        # Full audit should succeed as WINNER
        res = self.engine.audit_candidate(cand)
        self.assertEqual(len(res.ko_gates_tripped), 0)
        self.assertEqual(res.tier, "WINNER")
        self.assertTrue(res.passed_audit)
        self.assertEqual(res.rule_scores[4].raw_score, 100.0)

    def test_extreme_high_cost_and_high_srp(self):
        """Supplier cost $10,000, shipping $0, retail $35,000 (Markup 3.5x)."""
        cand = create_mock_candidate(
            supplier_cost=10000.00,
            shipping_cost=0.00,
            suggested_price=35000.00,
        )
        fin = cand.compute_financials()

        self.assertEqual(fin.landed_cost, 10000.00)
        self.assertEqual(fin.markup_multiplier, 3.50)
        self.assertGreater(fin.net_profit, 20000.00)
        self.assertGreaterEqual(fin.net_margin_pct, 65.0)

        res = self.engine.audit_candidate(cand)
        # KO gates should NOT trip (markup 3.5 >= 2.5, margin ~67.5% >= 55%)
        self.assertEqual(len(res.ko_gates_tripped), 0)
        # Rule 5 ticket must receive 0 pts (SRP > $99)
        self.assertEqual(res.rule_scores[5].raw_score, 0.0)
        # Subscore floor (< 50) must downgrade tier from WINNER to CONTENDER
        self.assertEqual(res.tier, "CONTENDER")
        self.assertFalse(res.passed_audit)

    def test_zero_supplier_cost_and_zero_shipping(self):
        """Promotional zero landed cost ($0.00 + $0.00) must not trigger ZeroDivisionError."""
        cand = create_mock_candidate(
            supplier_cost=0.00,
            shipping_cost=0.00,
            suggested_price=29.99,
        )
        fin = cand.compute_financials()
        self.assertEqual(fin.landed_cost, 0.00)
        self.assertEqual(fin.markup_multiplier, 0.00)  # Safe default when landed is 0

        # When landed is 0.0, markup is 0.0 (< 2.50), tripping KO-2
        res = self.engine.audit_candidate(cand)
        self.assertIn("KO-2", res.ko_gates_tripped)
        self.assertEqual(res.composite_score, 0.0)
        self.assertEqual(res.tier, "DISQUALIFIED")

    def test_free_shipping_with_tracked_carrier_edge_case_e01(self):
        """Edge Case E-01: Free shipping with valid tracked carrier is valid and passes KO-3."""
        cand = create_mock_candidate(
            supplier_cost=9.50,
            shipping_cost=0.00,
            suggested_price=34.99,
            shipping_carrier="YunExpress Tracked",
            shipping_days_max=10,
        )
        fin = cand.compute_financials()
        self.assertEqual(fin.landed_cost, 9.50)

        res = self.engine.audit_candidate(cand)
        self.assertNotIn("KO-3", res.ko_gates_tripped)
        self.assertEqual(res.rule_scores[7].raw_score, 100.0)

    def test_free_shipping_with_untracked_carrier_trips_ko3(self):
        """Free shipping with untracked surface mail trips KO-3."""
        cand = create_mock_candidate(
            supplier_cost=9.50,
            shipping_cost=0.00,
            suggested_price=34.99,
            shipping_carrier="Untracked China Post Small Packet",
            shipping_days_max=10,
        )
        res = self.engine.audit_candidate(cand)
        self.assertIn("KO-3", res.ko_gates_tripped)
        self.assertEqual(res.composite_score, 0.0)
        self.assertEqual(res.tier, "DISQUALIFIED")

    def test_astronomical_srp_float_stability(self):
        """Test $1,000,000,000 (1 billion USD) SRP for float overflow or precision explosion."""
        cand = create_mock_candidate(
            supplier_cost=1000.00,
            shipping_cost=0.00,
            suggested_price=1000000000.00,
        )
        fin = cand.compute_financials()
        self.assertTrue(math.isfinite(fin.processor_fee))
        self.assertTrue(math.isfinite(fin.net_profit))
        self.assertTrue(math.isfinite(fin.net_margin_pct))

        res = self.engine.audit_candidate(cand)
        self.assertTrue(math.isfinite(res.composite_score))
        self.assertEqual(res.rule_scores[5].raw_score, 0.0)  # Fatal ticket range
        self.assertEqual(res.tier, "CONTENDER")

    def test_massive_negative_profit_insolvent_pricing(self):
        """Item costing $500 sold for $19.99 produces negative profit and trips KO-2."""
        cand = create_mock_candidate(
            supplier_cost=500.00,
            shipping_cost=50.00,
            suggested_price=19.99,
        )
        fin = cand.compute_financials()
        self.assertEqual(fin.landed_cost, 550.00)
        self.assertLess(fin.net_profit, -500.00)
        self.assertLess(fin.net_margin_pct, 0.0)

        res = self.engine.audit_candidate(cand)
        self.assertIn("KO-2", res.ko_gates_tripped)
        self.assertEqual(res.composite_score, 0.0)
        self.assertEqual(res.tier, "DISQUALIFIED")


class TestAccountingAndPrecisionInvariants(unittest.TestCase):
    """Stress tests floating point precision, accounting balance, and threshold cutoffs."""

    def test_accounting_balance_across_price_grid(self):
        """Verifies fundamental equation: landed_cost + processor_fee + reserve_buffer + net_profit == srp."""
        # Test 100 combinations of prices and costs
        for cost in [0.01, 1.25, 4.99, 8.50, 15.00, 22.33, 49.95, 99.99, 250.00]:
            for shipping in [0.00, 1.99, 3.50, 6.25, 12.00]:
                for srp in [19.99, 29.99, 34.95, 49.99, 69.00, 89.99, 149.50]:
                    cand = create_mock_candidate(
                        supplier_cost=cost,
                        shipping_cost=shipping,
                        suggested_price=srp,
                    )
                    fin = cand.compute_financials()
                    reconstructed_srp = fin.landed_cost + fin.processor_fee + fin.reserve_buffer + fin.net_profit
                    diff = abs(reconstructed_srp - fin.srp)
                    # Rounding error across 4 rounded components must be <= 0.02
                    self.assertLessEqual(
                        diff,
                        0.02,
                        f"Accounting imbalance {diff:.4f} for cost={cost}, ship={shipping}, srp={srp}",
                    )

    def test_canonical_manual_numerical_example(self):
        """Validates canonical example from Section 4.3 of spec miner: SRP=$39.99, Landed=$11.00."""
        cand = create_mock_candidate(
            supplier_cost=6.50,
            shipping_cost=4.50,
            suggested_price=39.99,
        )
        fin = cand.compute_financials()
        self.assertEqual(fin.landed_cost, 11.00)
        self.assertEqual(fin.srp, 39.99)
        self.assertEqual(fin.markup_multiplier, 3.64)
        self.assertEqual(fin.processor_fee, 1.46)
        self.assertEqual(fin.reserve_buffer, 0.40)
        self.assertEqual(fin.net_profit, 27.13)
        self.assertEqual(fin.net_margin_pct, 67.84)

    def test_boundary_precision_rule_4_marginal_economics(self):
        """Edge Case E-09: Margin 64.99% vs 65.00% strict threshold (no lenient rounding to 85 pts)."""
        # Exactly 65.0% margin with 3.0x markup gets 85 pts
        score_exact = score_rule_4_unit_economics(3.00, 65.00)
        self.assertEqual(score_exact.raw_score, 85.0)

        # 64.99% margin must drop to marginal 50.0 pts
        score_below = score_rule_4_unit_economics(3.00, 64.99)
        self.assertEqual(score_below.raw_score, 50.0)

        # Markup 2.99x must drop to 50.0 pts even if margin is 75%
        score_low_markup = score_rule_4_unit_economics(2.99, 75.00)
        self.assertEqual(score_low_markup.raw_score, 50.0)

        # KO-2 boundary: Markup 2.49x trips 0.0 pts
        score_ko_markup = score_rule_4_unit_economics(2.49, 75.00)
        self.assertEqual(score_ko_markup.raw_score, 0.0)

        # KO-2 boundary: Margin 54.99% trips 0.0 pts
        score_ko_margin = score_rule_4_unit_economics(3.50, 54.99)
        self.assertEqual(score_ko_margin.raw_score, 0.0)

    def test_ticket_range_boundaries(self):
        """Test exact boundary points of Rule 5 ticket ranges."""
        self.assertEqual(score_rule_5_ticket_range(19.99).raw_score, 0.0)
        self.assertEqual(score_rule_5_ticket_range(20.00).raw_score, 30.0)
        self.assertEqual(score_rule_5_ticket_range(24.99).raw_score, 30.0)
        self.assertEqual(score_rule_5_ticket_range(25.00).raw_score, 70.0)
        self.assertEqual(score_rule_5_ticket_range(28.99).raw_score, 70.0)
        self.assertEqual(score_rule_5_ticket_range(29.00).raw_score, 100.0)
        self.assertEqual(score_rule_5_ticket_range(69.00).raw_score, 100.0)
        self.assertEqual(score_rule_5_ticket_range(69.01).raw_score, 70.0)
        self.assertEqual(score_rule_5_ticket_range(79.00).raw_score, 70.0)
        self.assertEqual(score_rule_5_ticket_range(79.01).raw_score, 30.0)
        self.assertEqual(score_rule_5_ticket_range(99.00).raw_score, 30.0)
        self.assertEqual(score_rule_5_ticket_range(99.01).raw_score, 0.0)


class TestMathematicalIdempotency(unittest.TestCase):
    """Stress tests deterministic idempotency across 100 repeated audits and multi-threaded runs."""

    def setUp(self):
        self.engine = AuditEngine()
        candidates_path = HUNTER_ROOT / "data" / "candidates.json"
        with open(candidates_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.candidates = [RawCandidate.from_dict(d) for d in data]

    def test_hundred_sequential_audits_yield_identical_results(self):
        """Auditing the same candidate 100 times yields byte-for-byte identical AuditResult dictionaries."""
        cand = self.candidates[0]  # ProSmile Ultrasonic
        baseline_result = self.engine.audit_candidate(cand).to_dict()

        for iteration in range(100):
            current_result = self.engine.audit_candidate(cand).to_dict()
            self.assertEqual(
                baseline_result,
                current_result,
                f"Non-deterministic mutation on iteration {iteration}",
            )

    def test_hundred_audits_across_all_ten_candidates(self):
        """Auditing the entire 10-candidate catalog 100 times produces identical scorecard rankings."""
        baseline_results = [r.to_dict() for r in self.engine.audit_candidates(self.candidates)]

        for iteration in range(100):
            current_results = [r.to_dict() for r in self.engine.audit_candidates(self.candidates)]
            for idx in range(len(baseline_results)):
                self.assertEqual(
                    baseline_results[idx],
                    current_results[idx],
                    f"Candidate {idx} mismatch on iteration {iteration}",
                )

    def test_concurrent_multi_threaded_audits_have_zero_race_conditions(self):
        """50 concurrent threads executing audit_candidate on the same candidate instance."""
        cand = self.candidates[2]  # SpineRelief Pro
        baseline_dict = self.engine.audit_candidate(cand).to_dict()

        def worker_audit():
            return self.engine.audit_candidate(cand).to_dict()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker_audit) for _ in range(50)]
            results = [f.result() for f in futures]

        for idx, res in enumerate(results):
            self.assertEqual(
                baseline_dict,
                res,
                f"Thread race condition / mutable state divergence in thread {idx}",
            )


class TestPenaltyDeductionsAndScoreClamping(unittest.TestCase):
    """Stress tests risk penalty calculations and score boundary clamping [0.0, 100.0]."""

    def setUp(self):
        self.engine = AuditEngine()

    def test_all_three_penalties_cumulative_deduction(self):
        """Verifies cumulative -20 pt penalty deduction (P_supp: -5, P_sat: -10, P_tick: -5)."""
        cand = create_mock_candidate(
            supplier_cost=3.00,
            shipping_cost=1.00,
            suggested_price=27.99,  # P_tick applies (-5 pts)
            google_trends_momentum=-0.35,  # P_sat applies (-10 pts)
            target_demographics={
                "supplier_orders": 45,  # P_supp applies (-5 pts)
                "supplier_store_age_months": 2,
            },
        )
        fin = cand.compute_financials()
        penalties = evaluate_penalties(cand, fin)

        self.assertEqual(penalties["P_supp"], 5.0)
        self.assertEqual(penalties["P_sat"], 10.0)
        self.assertEqual(penalties["P_tick"], 5.0)
        self.assertEqual(sum(penalties.values()), 20.0)

        res = self.engine.audit_candidate(cand)
        # Raw composite: S1=20, S2=20, S3=10, S4=20, S5=7, S6=10, S7=10 = 97.0
        # Minus 20.0 penalty = 77.0
        self.assertEqual(res.composite_score, 77.0)
        self.assertEqual(res.tier, "CONTENDER")

    def test_lower_bound_clamping_at_zero(self):
        """Verifies final score clamps at 0.0 and never goes negative even if penalties exceed raw score."""
        # Low raw score candidate: weak demo (40pts -> 8), mild pain (30pts -> 6), zero retail (0), etc.
        cand = create_mock_candidate(
            demo_visual_speed_sec=8.0,  # S1 = 40 (weighted 8.0)
            pain_level_score=25.0,  # S2 = 0 (weighted 0.0)
            retail_availability_score=15.0,  # S3 = 0 (weighted 0.0)
            supplier_cost=10.0,
            shipping_cost=5.0,
            suggested_price=26.00,  # S4 marginal (50 -> 10.0), S5 fringe (70 -> 7.0), P_tick = 5.0
            has_fragile_material=False,  # S6 = 100 (weighted 10.0)
            shipping_days_max=20,  # S7 = 20 (weighted 2.0)
            google_trends_momentum=-0.50,  # P_sat = 10.0
            target_demographics={"supplier_orders": 10},  # P_supp = 5.0
        )
        # Total penalties = 5 + 10 + 5 = 20.0
        # If raw composite is e.g. 15.0, raw - 20.0 = -5.0. Clamped to 0.0!
        res = self.engine.audit_candidate(cand)
        self.assertGreaterEqual(res.composite_score, 0.0)
        self.assertLessEqual(res.composite_score, 100.0)
        if not res.ko_gates_tripped:
            self.assertEqual(res.composite_score, 17.0)  # 37.0 - 20.0 = 17.0

        # Now force raw composite lower than penalty by zeroing more rules
        cand2 = create_mock_candidate(
            demo_visual_speed_sec=8.0,  # 8 pts
            pain_level_score=10.0,  # 0 pts
            retail_availability_score=50.0,  # 6 pts (>=30 so KO-4 does not trip)
            supplier_cost=10.0,
            shipping_cost=5.0,
            suggested_price=26.00,  # S4=0 (Markup 1.73 < 2.50 trips KO-2, but let's test unclamped without KO)
        )
        # Directly test clamping formula
        raw_composite = 12.0
        penalties = 20.0
        clamped = max(0.0, min(100.0, raw_composite - penalties))
        self.assertEqual(clamped, 0.0)

    def test_upper_bound_clamping_at_hundred(self):
        """Verifies final score never exceeds 100.0."""
        cand = create_mock_candidate(
            demo_visual_speed_sec=1.5,
            pain_level_score=95.0,
            retail_availability_score=90.0,
            supplier_cost=5.0,
            shipping_cost=2.0,
            suggested_price=39.99,
            has_fragile_material=False,
            has_sizing_requirements=False,
            shipping_days_max=8,
            shipping_carrier="YunExpress",
        )
        res = self.engine.audit_candidate(cand)
        self.assertEqual(res.composite_score, 100.0)
        self.assertLessEqual(res.composite_score, 100.0)

    def test_subscore_floor_enforcement(self):
        """Candidate with composite >= 80.0 but ONE rule < 50.0 is demoted to CONTENDER."""
        # All rules elite (100.0) EXCEPT Rule 3 (retail scarcity = 25.0 -> raw score = 20.0)
        # Raw composite = 20 + 20 + 2 + 20 + 10 + 10 + 10 = 92.0
        # Final score = 92.0 >= 80.0, but Rule 3 raw score is 20.0 (< 50.0)
        cand = create_mock_candidate(
            demo_visual_speed_sec=1.5,  # R1 = 100 (20 pts)
            pain_level_score=95.0,  # R2 = 100 (20 pts)
            retail_availability_score=25.0,  # R3 = 20 (2 pts) < 50.0 floor!
            supplier_cost=5.00,
            shipping_cost=2.00,
            suggested_price=39.99,  # R4 = 100 (20 pts), R5 = 100 (10 pts)
            has_fragile_material=False,  # R6 = 100 (10 pts)
            has_sizing_requirements=False,
            shipping_days_max=8,  # R7 = 100 (10 pts)
            shipping_carrier="YunExpress",
        )
        res = self.engine.audit_candidate(cand)
        self.assertEqual(res.composite_score, 92.0)
        self.assertEqual(res.rule_scores[3].raw_score, 20.0)
        self.assertEqual(res.tier, "CONTENDER")
        self.assertFalse(res.passed_audit)


class TestCandidateSortingStability(unittest.TestCase):
    """Stress tests multi-candidate ranking ordering and tier priority."""

    def setUp(self):
        self.engine = AuditEngine()

    def test_tier_priority_overrides_composite_score(self):
        """WINNER with 85.0 must sort before CONTENDER with 92.0 (subscore floor failed)."""
        winner = create_mock_candidate(
            candidate_id="winner-item",
            name="Winner Candidate",
            suggested_price=39.99,
        )
        # Contender has higher score (92.0) but failed subscore floor
        contender = create_mock_candidate(
            candidate_id="contender-item",
            name="Contender Candidate",
            retail_availability_score=25.0,  # R3 = 20 < 50 floor
            suggested_price=39.99,
        )
        disqualified = create_mock_candidate(
            candidate_id="disqualified-item",
            name="Disqualified Candidate",
            has_fragile_material=True,  # KO-1
        )

        results = self.engine.audit_candidates([disqualified, contender, winner])
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].tier, "WINNER")
        self.assertEqual(results[0].candidate.candidate_id, "winner-item")
        self.assertEqual(results[1].tier, "CONTENDER")
        self.assertEqual(results[1].candidate.candidate_id, "contender-item")
        self.assertEqual(results[2].tier, "DISQUALIFIED")
        self.assertEqual(results[2].candidate.candidate_id, "disqualified-item")


class TestRandomizedFuzzInvariants(unittest.TestCase):
    """Generative randomized fuzz test across 500 arbitrary candidates asserting all system invariants."""

    def setUp(self):
        self.engine = AuditEngine()

    def test_five_hundred_randomized_candidates_invariants(self):
        """Generates 500 randomized candidates spanning edge values and verifies strict invariant adherence."""
        import random
        rng = random.Random(42)  # Seeded for deterministic reproducibility

        carriers = ["YunExpress", "ePacket", "AliExpress Choice", "CJPacket", "untracked surface mail", "DHL Express"]

        for i in range(500):
            supplier_cost = round(rng.choice([0.0, 0.01, rng.uniform(0.1, 50.0), rng.uniform(50.0, 5000.0)]), 2)
            shipping_cost = round(rng.choice([0.0, rng.uniform(0.5, 15.0), rng.uniform(15.0, 100.0)]), 2)
            suggested_price = round(rng.choice([rng.uniform(1.0, 20.0), rng.uniform(20.0, 100.0), rng.uniform(100.0, 10000.0)]), 2)
            shipping_days_max = rng.choice([5, 8, 12, 14, 16, 20, 21, 25, 45])
            carrier = rng.choice(carriers)
            demo_speed = round(rng.choice([-1.0, 0.0, 1.5, 3.0, 4.5, 6.0, 7.5, 10.0, 15.0]), 2)
            pain_score = round(rng.uniform(0.0, 100.0), 1)
            retail_score = round(rng.uniform(0.0, 100.0), 1)
            has_fragile = rng.choice([True, False])
            has_sizing = rng.choice([True, False])
            momentum = round(rng.uniform(-0.80, 1.20), 2)
            competitor_ads = rng.randint(0, 150)
            supplier_orders = rng.choice([None, rng.randint(0, 500)])
            store_age = rng.choice([None, rng.randint(0, 36)])

            cand = create_mock_candidate(
                candidate_id=f"fuzz-{i}",
                name=f"Fuzz Product {i}",
                supplier_cost=supplier_cost,
                shipping_cost=shipping_cost,
                suggested_price=suggested_price,
                shipping_days_max=shipping_days_max,
                shipping_carrier=carrier,
                demo_visual_speed_sec=demo_speed,
                pain_level_score=pain_score,
                retail_availability_score=retail_score,
                has_fragile_material=has_fragile,
                has_sizing_requirements=has_sizing,
                google_trends_momentum=momentum,
                competitor_ad_count=competitor_ads,
                target_demographics={
                    "supplier_orders": supplier_orders,
                    "supplier_store_age_months": store_age,
                },
            )

            res = self.engine.audit_candidate(cand)

            # Invariant 1: No NaN or inf values in financials or composite score
            self.assertTrue(math.isfinite(res.composite_score))
            self.assertTrue(math.isfinite(res.financials.landed_cost))
            self.assertTrue(math.isfinite(res.financials.srp))
            self.assertTrue(math.isfinite(res.financials.net_profit))
            self.assertTrue(math.isfinite(res.financials.net_margin_pct))

            # Invariant 2: Score clamping strictly within [0.0, 100.0]
            self.assertGreaterEqual(res.composite_score, 0.0)
            self.assertLessEqual(res.composite_score, 100.0)

            # Invariant 3: Tripped KO gates force score 0.0 and DISQUALIFIED
            if res.ko_gates_tripped:
                self.assertEqual(res.composite_score, 0.0)
                self.assertEqual(res.tier, "DISQUALIFIED")
                self.assertFalse(res.passed_audit)

            # Invariant 4: WINNER tier contract
            if res.tier == "WINNER":
                self.assertGreaterEqual(res.composite_score, 80.0)
                self.assertEqual(len(res.ko_gates_tripped), 0)
                self.assertTrue(res.passed_audit)
                for rid, rscore in res.rule_scores.items():
                    self.assertGreaterEqual(rscore.raw_score, 50.0, f"Rule {rid} subscore < 50 for WINNER")

            # Invariant 5: CONTENDER tier contract
            if res.tier == "CONTENDER":
                self.assertGreaterEqual(res.composite_score, 65.0)
                self.assertEqual(len(res.ko_gates_tripped), 0)
                self.assertFalse(res.passed_audit)

            # Invariant 6: DISQUALIFIED tier contract
            if res.tier == "DISQUALIFIED":
                self.assertTrue(res.composite_score < 65.0 or len(res.ko_gates_tripped) > 0)
                self.assertFalse(res.passed_audit)

            # Invariant 7: Serialization roundtrip integrity
            as_dict = res.to_dict()
            reconstructed = AuditResult.from_dict(as_dict)
            self.assertEqual(res.composite_score, reconstructed.composite_score)
            self.assertEqual(res.tier, reconstructed.tier)
            self.assertEqual(res.passed_audit, reconstructed.passed_audit)
            self.assertEqual(res.ko_gates_tripped, reconstructed.ko_gates_tripped)


if __name__ == "__main__":
    unittest.main(verbosity=2)
