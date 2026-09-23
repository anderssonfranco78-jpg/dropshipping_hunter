"""7 Golden Rules Audit & Quantitative Scoring Engine.

Implements the canonical Antigravity dropshipping evaluation standard:
- 4 Hard Knockout Gates (KO-1: Sizing/Fragility, KO-2: Margin Collapse, KO-3: Shipping Blackout, KO-4: Zero WOW Commodity)
- 7 Operational Rubrics with canonical weights:
    S1: Visual WOW 0-3s (20%)
    S2: Acute Pain / Passion (20%)
    S3: Retail Scarcity (10%)
    S4: Unit Economics & Markup (20%)
    S5: Ticket Range Sweet Spot (10%)
    S6: Zero Sizing / Fragility (10%)
    S7: Fast Tracked Logistics (10%)
- Risk Penalty deductions (P_supp, P_sat, P_tick)
- Winner Tier Classification:
    🏆 WINNER (>= 80.0, no subscore < 50.0, zero KO tripped)
    ⚠️ CONTENDER (65.0 - 79.9, zero KO tripped)
    ❌ DISQUALIFIED (< 65.0 or any KO gate tripped)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from hunter.models import AuditResult, FinancialMetrics, RawCandidate, RuleScore

# Windows console encoding safeguard
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Configure logging
logger = logging.getLogger("hunter.audit_engine")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ==============================================================================
# 7 GOLDEN RULES OPERATIONAL RUBRICS
# ==============================================================================

def score_rule_1_visual_wow(demo_speed_sec: float) -> RuleScore:
    """Rule 1: Visual WOW (0 to 3s) — Weight 0.20 (20 pts).
    
    Objective: Stop the infinite feed scroll on short-form video in <= 3 seconds.
    - 100 pts (Elite WOW): Demonstration / transformation visible in <= 3.0s.
    - 70 pts (Moderate WOW): Clear utility requiring 3.1 - 6.0s.
    - 40 pts (Weak WOW): Slow demo taking 6.1 - 9.9s.
    - 0 pts (Zero WOW): Static, decorative, or speed <= 0s / >= 10s.
    """
    if demo_speed_sec <= 0.0 or demo_speed_sec >= 10.0:
        raw = 0.0
    elif demo_speed_sec <= 3.0:
        raw = 100.0
    elif demo_speed_sec <= 6.0:
        raw = 70.0
    else:
        raw = 40.0

    weight = 0.20
    return RuleScore(
        rule_id=1,
        name="Visual WOW (0-3s)",
        raw_score=raw,
        weight=weight,
        weighted_score=round(raw * weight, 2),
        passed=raw >= 60.0,
    )


def score_rule_2_acute_pain(pain_level_score: float) -> RuleScore:
    """Rule 2: Acute Pain / Passion — Weight 0.20 (20 pts).
    
    Objective: Eradicate an acute daily physical pain or feed an intense identity obsession.
    - 100 pts: Severe pain relief or deep identity passion (pain >= 85.0).
    - 70 pts: Moderate chore inconvenience or general hobby (60.0 <= pain < 85.0).
    - 30 pts: Passive comfort or mild convenience (30.0 <= pain < 60.0).
    - 0 pts: Zero pain / purely ornamental item (pain < 30.0).
    """
    if pain_level_score >= 85.0:
        raw = 100.0
    elif pain_level_score >= 60.0:
        raw = 70.0
    elif pain_level_score >= 30.0:
        raw = 30.0
    else:
        raw = 0.0

    weight = 0.20
    return RuleScore(
        rule_id=2,
        name="Acute Pain / Passion",
        raw_score=raw,
        weight=weight,
        weighted_score=round(raw * weight, 2),
        passed=raw >= 60.0,
    )


def score_rule_3_retail_scarcity(retail_availability_score: float) -> RuleScore:
    """Rule 3: Retail Scarcity — Weight 0.10 (10 pts).
    
    Objective: Eliminate immediate offline substitution at supermarkets or pharmacies.
    - 100 pts: Novel DTC gadget completely absent from retail (scarcity >= 80.0).
    - 60 pts: Available only in specialized boutiques at high markups (50.0 <= scarcity < 80.0).
    - 20 pts: Common online commodity with minor variation (20.0 <= scarcity < 50.0).
    - 0 pts: Stocked at Walmart, Target, Dollar Tree, or local pharmacies (scarcity < 20.0).
    """
    if retail_availability_score >= 80.0:
        raw = 100.0
    elif retail_availability_score >= 50.0:
        raw = 60.0
    elif retail_availability_score >= 20.0:
        raw = 20.0
    else:
        raw = 0.0

    weight = 0.10
    return RuleScore(
        rule_id=3,
        name="Retail Scarcity",
        raw_score=raw,
        weight=weight,
        weighted_score=round(raw * weight, 2),
        passed=raw >= 60.0,
    )


def score_rule_4_unit_economics(markup_multiplier: float, net_margin_pct: float) -> RuleScore:
    """Rule 4: Unit Economics & Markup — Weight 0.20 (20 pts).
    
    Objective: Guarantee unit solvency and healthy cash flow under $0 ad spend.
    - 100 pts: Elite economics (Markup >= 3.50x AND Net Margin >= 70.0%).
    - 85 pts: Canonical standard (Markup >= 3.00x AND Net Margin >= 65.0%).
    - 50 pts: Marginal economics / warning (2.50x <= Markup < 3.00x OR 55.0% <= Margin < 65.0%).
    - 0 pts: Insolvent collapse (Markup < 2.50x OR Net Margin < 55.0% — trips KO-2).
    """
    if markup_multiplier < 2.50 or net_margin_pct < 55.0:
        raw = 0.0
    elif markup_multiplier >= 3.50 and net_margin_pct >= 70.0:
        raw = 100.0
    elif markup_multiplier >= 3.00 and net_margin_pct >= 65.0:
        raw = 85.0
    else:
        raw = 50.0

    weight = 0.20
    return RuleScore(
        rule_id=4,
        name="Unit Economics & Markup",
        raw_score=raw,
        weight=weight,
        weighted_score=round(raw * weight, 2),
        passed=raw >= 60.0,
    )


def score_rule_5_ticket_range(srp: float) -> RuleScore:
    """Rule 5: Ticket Range Sweet Spot ($29 - $69 USD) — Weight 0.10 (10 pts).
    
    Objective: Maximize impulse mobile conversion without deliberation friction.
    - 100 pts: Golden sweet spot ($29.00 <= SRP <= $69.00).
    - 70 pts: Acceptable fringe ($25.00 <= SRP < $29.00 OR $69.00 < SRP <= $79.00).
    - 30 pts: High deliberation or low profit ($20.00 <= SRP < $25.00 OR $79.00 < SRP <= $99.00).
    - 0 pts: Fatal ticket danger (SRP < $20.00 OR SRP > $99.00).
    """
    if srp < 20.00 or srp > 99.00:
        raw = 0.0
    elif 29.00 <= srp <= 69.00:
        raw = 100.0
    elif (25.00 <= srp < 29.00) or (69.00 < srp <= 79.00):
        raw = 70.0
    elif (20.00 <= srp < 25.00) or (79.00 < srp <= 99.00):
        raw = 30.0
    else:
        raw = 0.0

    weight = 0.10
    return RuleScore(
        rule_id=5,
        name="Ticket Range Sweet Spot",
        raw_score=raw,
        weight=weight,
        weighted_score=round(raw * weight, 2),
        passed=raw >= 60.0,
    )


def score_rule_6_sizing_fragility(has_fragile: bool, has_sizing: bool) -> RuleScore:
    """Rule 6: Zero Sizing & Zero Fragility Risk Filter — Weight 0.10 (10 pts).
    
    Objective: Keep returns and international parcel breakage disputes strictly < 2%.
    - 100 pts: Zero risk (one-size-fits-all, durable ABS/TPU/silicone/metal).
    - 0 pts: Fatal disqualification (fragile glass/ceramic or millimetric sizing — trips KO-1).
    """
    if has_fragile or has_sizing:
        raw = 0.0
    else:
        raw = 100.0

    weight = 0.10
    return RuleScore(
        rule_id=6,
        name="Zero Sizing / Fragility",
        raw_score=raw,
        weight=weight,
        weighted_score=round(raw * weight, 2),
        passed=raw >= 60.0,
    )


def score_rule_7_fast_logistics(days_max: int, carrier: str) -> RuleScore:
    """Rule 7: Fast Tracked Logistics Verifier — Weight 0.10 (10 pts).
    
    Objective: 7-12 day tracked delivery window to protect merchant accounts.
    - 100 pts: Fast tracked line <= 12 days (YunExpress, ePacket, Choice, CJPacket).
    - 60 pts: Standard tracked shipping 13-16 days.
    - 20 pts: Delayed logistics 17-21 days.
    - 0 pts: Untracked or transit > 21 days (trips KO-3).
    """
    c_lower = carrier.lower()
    if days_max > 21 or "untracked" in c_lower:
        raw = 0.0
    elif days_max <= 12:
        raw = 100.0
    elif days_max <= 16:
        raw = 60.0
    elif days_max <= 21:
        raw = 20.0
    else:
        raw = 0.0

    weight = 0.10
    return RuleScore(
        rule_id=7,
        name="Fast Tracked Logistics",
        raw_score=raw,
        weight=weight,
        weighted_score=round(raw * weight, 2),
        passed=raw >= 60.0,
    )


# ==============================================================================
# HARD KNOCKOUT GATES (BINARY VETOES)
# ==============================================================================

def evaluate_ko_gates(candidate: RawCandidate, financials: FinancialMetrics) -> List[str]:
    """Check candidate against the 4 Hard Knockout Gates.
    
    KO-1: Sizing / Fragility veto (fragile material or millimetric clothing sizing).
    KO-2: Margin collapse veto (markup < 2.50x or net margin < 55.0%).
    KO-3: Shipping blackout veto (transit > 21 days or untracked carrier).
    KO-4: Zero WOW / Commodity veto (demo speed <= 0s or >= 10s AND retail scarcity < 30).
    
    Returns:
        List of tripped gate identifiers (e.g. ['KO-1', 'KO-2']), empty if all clear.
    """
    ko_tripped: List[str] = []

    # KO-1: Sizing / Fragility veto
    if candidate.has_fragile_material or candidate.has_sizing_requirements:
        ko_tripped.append("KO-1")

    # KO-2: Margin collapse veto
    if financials.markup_multiplier < 2.50 or financials.net_margin_pct < 55.0:
        ko_tripped.append("KO-2")

    # KO-3: Shipping blackout veto
    if candidate.shipping_days_max > 21 or "untracked" in candidate.shipping_carrier.lower():
        ko_tripped.append("KO-3")

    # KO-4: Zero WOW / Commodity veto
    if (candidate.demo_visual_speed_sec <= 0.0 or candidate.demo_visual_speed_sec >= 10.0) and candidate.retail_availability_score < 30.0:
        ko_tripped.append("KO-4")

    return ko_tripped


# ==============================================================================
# RISK PENALTY ADJUSTMENTS
# ==============================================================================

def evaluate_penalties(candidate: RawCandidate, financials: FinancialMetrics) -> Dict[str, float]:
    """Compute risk penalty deductions.
    
    P_supp (-5 pts): Supplier orders < 100 or store age < 6 months.
    P_sat (-10 pts): Google Trends momentum < -0.20 or competitor active ads > 50.
    P_tick (-5 pts): Suggested price in near-fringe zone ($25-$28.99 or $69.01-$79.00).
    
    Returns:
        Dictionary of penalty codes to point deductions.
    """
    penalties: Dict[str, float] = {}

    # P_supp: Supplier Volatility
    demographics = candidate.target_demographics or {}
    orders = demographics.get("supplier_orders")
    store_age = demographics.get("supplier_store_age_months")
    if (orders is not None and orders < 100) or (store_age is not None and store_age < 6):
        penalties["P_supp"] = 5.0
    else:
        penalties["P_supp"] = 0.0

    # P_sat: Trend Saturation
    if candidate.google_trends_momentum < -0.20 or candidate.competitor_ad_count > 50:
        penalties["P_sat"] = 10.0
    else:
        penalties["P_sat"] = 0.0

    # P_tick: Near-Fringe Ticket
    srp = financials.srp
    if (25.00 <= srp < 29.00) or (69.00 < srp <= 79.00):
        penalties["P_tick"] = 5.0
    else:
        penalties["P_tick"] = 0.0

    return penalties


# ==============================================================================
# WINNER TIER CLASSIFIER
# ==============================================================================

def classify_tier(
    final_score: float,
    rule_scores: Dict[int, RuleScore],
    ko_gates: List[str],
) -> Tuple[str, bool]:
    """Categorize candidate into WINNER, CONTENDER, or DISQUALIFIED.
    
    - 🏆 WINNER: Final Score >= 80.0, no subscore < 50.0, zero KO gates tripped.
    - ⚠️ CONTENDER: 65.0 <= Final Score < 80.0 (or Final Score >= 80 with subscore < 50), zero KO tripped.
    - ❌ DISQUALIFIED: Final Score < 65.0 OR any KO gate tripped.
    
    Returns:
        tuple (tier_name, passed_audit)
    """
    if ko_gates:
        return "DISQUALIFIED", False

    if final_score < 65.0:
        return "DISQUALIFIED", False

    # Check subscore floor (< 50 points in any individual rule)
    has_subscore_below_50 = any(r.raw_score < 50.0 for r in rule_scores.values())

    if final_score >= 80.0:
        if not has_subscore_below_50:
            return "WINNER", True
        else:
            return "CONTENDER", False

    return "CONTENDER", False


# ==============================================================================
# AUDIT ENGINE CLASS
# ==============================================================================

class AuditEngine:
    """7 Golden Rules Quantitative Audit and Scoring Engine.
    
    Evaluates product candidates across 4 knockout gates, 7 operational rubrics,
    risk penalty adjustments, and tier classifications.
    """

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        """Initialize AuditEngine.
        
        Args:
            data_dir: Path to directory containing candidates.json and audit_results.json.
        """
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).resolve().parent.parent / "data"

    def audit_candidate(self, candidate: RawCandidate) -> AuditResult:
        """Audit an individual RawCandidate and generate a structured AuditResult.
        
        Args:
            candidate: RawCandidate dataclass instance.
            
        Returns:
            AuditResult containing financials, 7 rule scores, KO status, composite score, and tier.
        """
        financials = candidate.compute_financials()

        # Evaluate 7 Operational Rubrics
        rule_scores: Dict[int, RuleScore] = {
            1: score_rule_1_visual_wow(candidate.demo_visual_speed_sec),
            2: score_rule_2_acute_pain(candidate.pain_level_score),
            3: score_rule_3_retail_scarcity(candidate.retail_availability_score),
            4: score_rule_4_unit_economics(financials.markup_multiplier, financials.net_margin_pct),
            5: score_rule_5_ticket_range(financials.srp),
            6: score_rule_6_sizing_fragility(candidate.has_fragile_material, candidate.has_sizing_requirements),
            7: score_rule_7_fast_logistics(candidate.shipping_days_max, candidate.shipping_carrier),
        }

        # Check 4 Hard Knockout Gates
        ko_gates = evaluate_ko_gates(candidate, financials)

        if ko_gates:
            composite_score = 0.0
            tier = "DISQUALIFIED"
            passed_audit = False
        else:
            raw_composite = sum(r.weighted_score for r in rule_scores.values())
            penalties = evaluate_penalties(candidate, financials)
            total_penalty = sum(penalties.values())
            final_score = max(0.0, min(100.0, raw_composite - total_penalty))
            composite_score = round(final_score, 1)
            tier, passed_audit = classify_tier(composite_score, rule_scores, ko_gates)

        return AuditResult(
            candidate=candidate,
            financials=financials,
            rule_scores=rule_scores,
            ko_gates_tripped=ko_gates,
            composite_score=composite_score,
            tier=tier,
            passed_audit=passed_audit,
        )

    def audit_candidates(self, candidates: List[RawCandidate]) -> List[AuditResult]:
        """Audit a collection of candidates and sort descending by composite score.
        
        Args:
            candidates: List of RawCandidate instances.
            
        Returns:
            List of AuditResult instances sorted descending by composite_score.
        """
        results = [self.audit_candidate(cand) for cand in candidates]
        results.sort(key=lambda r: (r.tier == "WINNER", r.tier == "CONTENDER", r.composite_score), reverse=True)
        return results

    def audit_candidates_file(
        self,
        filepath: Union[str, Path],
        output_filepath: Optional[Union[str, Path]] = None,
    ) -> List[AuditResult]:
        """Load candidates from JSON, execute full audit, and optionally save results.
        
        Args:
            filepath: Path to candidates JSON file.
            output_filepath: Optional path to save audit_results.json.
            
        Returns:
            List of sorted AuditResult instances.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Candidates file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, list):
            raise ValueError(f"Expected list of candidate objects in {path}, got {type(raw_data).__name__}")

        candidates = [RawCandidate.from_dict(item) for item in raw_data]
        results = self.audit_candidates(candidates)

        if output_filepath is not None:
            out_path = Path(output_filepath)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            serialized = [r.to_dict() for r in results]
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2, ensure_ascii=False)
            logger.info("Persisted %d audit results to %s", len(results), out_path)

        return results


# ==============================================================================
# CLI EXECUTION & SCORECARD DISPLAY
# ==============================================================================

def format_scorecard_table(results: List[AuditResult]) -> str:
    """Format audit results into a high-visibility text table for PowerShell console."""
    lines = []
    separator = "=" * 116
    thin_sep = "-" * 116

    lines.append(separator)
    lines.append(" 🎯 ANTIGRAVITY — 7 GOLDEN RULES AUDIT SCORECARD & WINNER RANKING")
    lines.append(separator)
    header = (
        f"{'Rank':^6}| {'Tier':^13} | {'Score':^7} | {'Product Name':<38} | "
        f"{'Landed':^8} | {'SRP':^8} | {'Markup':^7} | {'Margin':^7} | {'Profit':^8} | {'KO Tripped':<10}"
    )
    lines.append(header)
    lines.append(thin_sep)

    for rank, res in enumerate(results, 1):
        tier_icons = {
            "WINNER": "🏆 WINNER",
            "CONTENDER": "⚠️ CONTENDER",
            "DISQUALIFIED": "❌ DISQUALIF.",
        }
        tier_display = tier_icons.get(res.tier, res.tier)
        ko_str = ", ".join(res.ko_gates_tripped) if res.ko_gates_tripped else "None"
        
        name = res.candidate.name
        if len(name) > 36:
            name = name[:33] + "..."

        row = (
            f" {rank:^4} | {tier_display:<13} | {res.composite_score:>5.1f} | {name:<38} | "
            f"${res.financials.landed_cost:>6.2f} | ${res.financials.srp:>6.2f} | "
            f"{res.financials.markup_multiplier:>5.2f}x | {res.financials.net_margin_pct:>5.1f}% | "
            f"${res.financials.net_profit:>6.2f} | {ko_str:<10}"
        )
        lines.append(row)

    lines.append(separator)
    winners = sum(1 for r in results if r.tier == "WINNER")
    contenders = sum(1 for r in results if r.tier == "CONTENDER")
    disqualified = sum(1 for r in results if r.tier == "DISQUALIFIED")
    lines.append(
        f" Audit Summary: {len(results)} Audited | {winners} Winners (🏆) | "
        f"{contenders} Contender (⚠️) | {disqualified} Disqualified (❌)"
    )
    lines.append(separator)
    return "\n".join(lines)


def safe_print(text: str) -> None:
    """Print text safely across Windows console code pages."""
    try:
        print(text)
    except UnicodeEncodeError:
        safe_text = (
            text.replace("🎯", "[ANTIGRAVITY]")
            .replace("🏆", "[WINNER]")
            .replace("⚠️", "[CONTENDER]")
            .replace("❌", "[DISQUALIFIED]")
        )
        try:
            print(safe_text)
        except UnicodeEncodeError:
            encoding = getattr(sys.stdout, "encoding", "ascii") or "ascii"
            print(safe_text.encode(encoding, errors="replace").decode(encoding))


def main() -> int:
    """CLI Entrypoint for python -m hunter.audit_engine."""
    parser = argparse.ArgumentParser(
        description="Dropshipping Hunter — 7 Golden Rules Audit & Quantitative Scoring Engine"
    )
    default_input = Path(__file__).resolve().parent.parent / "data" / "candidates.json"
    default_output = Path(__file__).resolve().parent.parent / "data" / "audit_results.json"

    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=str(default_input),
        help=f"Path to input candidates.json (default: {default_input})",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=str(default_output),
        help=f"Path to output audit_results.json (default: {default_output})",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress console scorecard printing",
    )

    args = parser.parse_args()

    try:
        engine = AuditEngine()
        results = engine.audit_candidates_file(args.input, output_filepath=args.output)

        if not args.quiet:
            table = format_scorecard_table(results)
            safe_print(table)
            safe_print(f"Results saved to: {args.output}\n")

        return 0
    except Exception as exc:
        logger.error("Audit Engine execution failed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
