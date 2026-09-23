#!/usr/bin/env python3
"""
Master E2E Test Suite Runner for Dropshipping Winner Intelligence & Prospecting System.

Coordinates and executes all 4 test tiers:
  Tier 1: Feature Coverage (test_tier1_features.py - 23 features in isolation)
  Tier 2: Boundary Value Analysis & Edge Cases (test_tier2_boundaries.py - E-01 to E-10)
  Tier 3: Cross-Module Interactions (test_tier3_combinations.py - pairwise integration)
  Tier 4: Real-World Workload Scenarios (test_tier4_scenarios.py - multi-product pipelines)

Usage:
  python tests/test_e2e_runner.py                # Run all 4 tiers
  python tests/test_e2e_runner.py --tier 1       # Run specific tier (1, 2, 3, or 4)
  python tests/test_e2e_runner.py -v             # Verbose output
  python tests/test_e2e_runner.py --failfast     # Stop on first failure
  python -m unittest tests/test_e2e_runner.py    # Unittest discovery
  pytest tests/test_e2e_runner.py                # Pytest execution
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import unittest
from typing import Dict, List, Tuple

# Workspace root configuration
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ensure console supports utf-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import tests

# Tier module definitions
TIER_MODULES: Dict[int, Dict[str, str]] = {
    1: {
        "name": "Tier 1: Feature Coverage",
        "description": "23 features from PROJECT.md in strict isolation (>=5 tests per feature)",
        "module": "tests.test_tier1_features",
    },
    2: {
        "name": "Tier 2: Boundary Value Analysis & Edge Cases",
        "description": "Operational edge cases E-01 to E-10, zero division, fringe tickets, logistics limits",
        "module": "tests.test_tier2_boundaries",
    },
    3: {
        "name": "Tier 3: Cross-Module Interactions",
        "description": "Pairwise integration: Scraper -> Candidate Schema -> Audit -> Visualizer -> Dossier",
        "module": "tests.test_tier3_combinations",
    },
    4: {
        "name": "Tier 4: Real-World Workload Scenarios",
        "description": "Multi-product candidate harvest, winner selection, Remotion hooks, headless execution",
        "module": "tests.test_tier4_scenarios",
    },
}


def run_single_tier(
    tier_number: int,
    verbosity: int = 1,
    failfast: bool = False,
) -> Tuple[bool, int, int, int, int, float, List[str]]:
    """Execute tests for a specific tier.

    Returns:
        (passed, total, failures, errors, skipped, elapsed, error_details)
    """
    tier_info = TIER_MODULES[tier_number]
    mod_name = tier_info["module"]

    loader = unittest.TestLoader()
    try:
        suite = loader.loadTestsFromName(mod_name)
    except Exception as e:
        return False, 0, 0, 1, 0, 0.0, [f"Failed to load {mod_name}: {e}"]

    stream = sys.stdout if verbosity > 1 else open(os.devnull, "w")
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=verbosity,
        failfast=failfast,
    )

    t0 = time.time()
    result = runner.run(suite)
    elapsed = time.time() - t0

    if verbosity <= 1:
        stream.close()

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = result.wasSuccessful()

    err_msgs: List[str] = []
    for test, trace in result.failures:
        err_msgs.append(f"[FAIL] {test}: {trace}")
    for test, trace in result.errors:
        err_msgs.append(f"[ERROR] {test}: {trace}")

    return passed, total, failures, errors, skipped, elapsed, err_msgs


def run_all_tiers(
    verbosity: int = 1,
    failfast: bool = False,
    selected_tier: int = 0,
) -> int:
    """Execute all or selected test tiers and render a structured console summary."""
    print("=" * 80)
    print(" 🚀 DROPSHIPPING HUNTER — E2E TEST SUITE RUNNER")
    print("=" * 80)
    print(f" Working Directory : {PROJECT_ROOT}")
    print(f" Python Runtime    : {sys.version.split()[0]} ({sys.platform})")
    print(f" Mode              : 100% Deterministic Offline & Headless")
    print("=" * 80)

    tiers_to_run = [selected_tier] if selected_tier in TIER_MODULES else sorted(TIER_MODULES.keys())

    grand_total = 0
    grand_failures = 0
    grand_errors = 0
    grand_skipped = 0
    grand_elapsed = 0.0
    all_passed = True
    tier_results = []

    for tier_num in tiers_to_run:
        info = TIER_MODULES[tier_num]
        print(f"\n▶ Executing {info['name']}...")
        print(f"  Description: {info['description']}")

        passed, total, failures, errors, skipped, elapsed, err_msgs = run_single_tier(
            tier_num, verbosity=verbosity, failfast=failfast
        )

        grand_total += total
        grand_failures += failures
        grand_errors += errors
        grand_skipped += skipped
        grand_elapsed += elapsed
        if not passed:
            all_passed = False

        status_str = "PASSED" if passed else "FAILED"
        tier_results.append({
            "tier": tier_num,
            "name": info["name"],
            "total": total,
            "passed": total - failures - errors - skipped,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
            "elapsed": elapsed,
            "status": status_str,
            "err_msgs": err_msgs,
        })

        print(f"  Result: {status_str} ({total - failures - errors - skipped}/{total} passed, {skipped} skipped, {elapsed:.3f}s)")

    # Print Summary Table
    print("\n" + "=" * 80)
    print(" 📊 COMPREHENSIVE TEST SUITE EXECUTION SUMMARY")
    print("=" * 80)
    print(f" {'Tier':<8} | {'Tier Name':<38} | {'Pass':<6} | {'Fail':<6} | {'Skip':<6} | {'Status':<10}")
    print("-" * 80)

    for tr in tier_results:
        print(
            f" Tier {tr['tier']:<3} | {tr['name']:<38} | {tr['passed']:<6} | "
            f"{tr['failures'] + tr['errors']:<6} | {tr['skipped']:<6} | {tr['status']:<10}"
        )

    print("-" * 80)
    passed_total = grand_total - grand_failures - grand_errors - grand_skipped
    overall_status = "ALL TIERS PASSED" if all_passed else "FAILURES DETECTED"
    print(
        f" {'TOTAL':<8} | {'All Executed Test Suites':<38} | {passed_total:<6} | "
        f"{grand_failures + grand_errors:<6} | {grand_skipped:<6} | {overall_status:<10}"
    )
    print("=" * 80)
    print(f" Total Tests Run: {grand_total} in {grand_elapsed:.3f}s")
    print("=" * 80)

    # Print failure details if any
    if not all_passed:
        print("\n❌ DETAILED FAILURE LOG:")
        for tr in tier_results:
            for msg in tr["err_msgs"]:
                print("-" * 60)
                print(msg)
        return 1

    return 0


# ===========================================================================
# Unittest Discovery Wrapper (for python -m unittest tests/test_e2e_runner.py)
# ===========================================================================
class MasterE2ETestRunner(unittest.TestCase):
    """Unittest TestCase wrapping all 4 tiers for standard unittest discovery."""

    def test_run_tier_1_feature_coverage(self) -> None:
        """Executes Tier 1: Feature Coverage."""
        passed, total, f, e, s, el, msgs = run_single_tier(1)
        self.assertTrue(passed, f"Tier 1 failures: {msgs}")

    def test_run_tier_2_boundary_corner(self) -> None:
        """Executes Tier 2: Boundary Value Analysis & Edge Cases."""
        passed, total, f, e, s, el, msgs = run_single_tier(2)
        self.assertTrue(passed, f"Tier 2 failures: {msgs}")

    def test_run_tier_3_cross_feature(self) -> None:
        """Executes Tier 3: Cross-Module Interactions."""
        passed, total, f, e, s, el, msgs = run_single_tier(3)
        self.assertTrue(passed, f"Tier 3 failures: {msgs}")

    def test_run_tier_4_real_world_scenarios(self) -> None:
        """Executes Tier 4: Real-World Workload Scenarios."""
        passed, total, f, e, s, el, msgs = run_single_tier(4)
        self.assertTrue(passed, f"Tier 4 failures: {msgs}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Master E2E Test Suite Runner for Dropshipping Winner Intelligence & Prospecting System"
    )
    parser.add_argument(
        "--tier",
        type=int,
        choices=[1, 2, 3, 4],
        default=0,
        help="Run only a specific tier (1, 2, 3, or 4). Default: all tiers.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable detailed verbose output for each test case.",
    )
    parser.add_argument(
        "--failfast",
        action="store_true",
        help="Stop execution immediately on first failure or error.",
    )

    args = parser.parse_args()
    verbosity = 2 if args.verbose else 1
    exit_code = run_all_tiers(
        verbosity=verbosity,
        failfast=args.failfast,
        selected_tier=args.tier,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
