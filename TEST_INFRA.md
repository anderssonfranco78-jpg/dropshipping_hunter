# TEST_INFRA: E2E Test Suite Infrastructure & Architecture

**Project**: Dropshipping Winner Intelligence & Prospecting System (`dropshipping_hunter`)  
**Architecture**: Headless Organic Market Intelligence & 7 Golden Rules Audit Pipeline  
**Execution Environment**: Windows PowerShell, Python 3.10+ (Current runtime: Python 3.14.5)  
**Target Integrity Mode**: Development & Deterministic Offline Verification  
**Author**: E2E Test Suite Architect (`test_writer_e2e_1`)

---

## 1. Executive Summary & Test Philosophy

The `dropshipping_hunter` test suite is designed as an **opaque-box, requirement-driven, 4-tier verification harness**. It establishes strict behavioral validation across all 23 features defined in `PROJECT.md` and enforces the canonical e-commerce standards of `07-Manual-Maestro-Dropshipping-Seleccion-Producto-Ganador.md` and `ORIGINAL_REQUEST.md`.

### Core Architectural Principles
1. **Opaque-Box Requirement Derivation**: Test assertions are derived strictly from business requirements, operational scoring rubrics, and interface contracts—never tailored to match implementation quirks.
2. **Zero Desktop GUI Automation**: Strictly validates headless and programmatic execution. Prohibits GUI mouse automation (`pyautogui`), visible browser popups, or keyboard hijacking.
3. **100% Deterministic & Offline Resilient**: All tests execute with zero required external network calls, using deterministic mocks and offline fixture generators with full schema parity.
4. **Progressive Testability & Graceful Milestone Activation**: The test harness supports milestone-by-milestone development (M1 to M5). Tests for features under active implementation gracefully activate as modules come online, while asserting contract invariants across all tiers.
5. **Defensive Boundary & Adversarial Hardening**: Rigorous boundary value analysis (E-01 to E-10), zero division protection, extreme price tolerances, and malformed payload resilience.

---

## 2. 4-Tier Test Suite Hierarchy

The test suite is partitioned into four progressive tiers located in `dropshipping_hunter/tests/`:

```
dropshipping_hunter/tests/
├── __init__.py                  # Package environment, sys.path resolution & dynamic module loader
├── test_tier1_features.py       # Tier 1: Feature Isolation Coverage (>=5 tests per core feature)
├── test_tier2_boundaries.py     # Tier 2: Boundary Value Analysis & Edge Cases (E-01 to E-10)
├── test_tier3_combinations.py   # Tier 3: Cross-Module Interactions & Pairwise Integration
├── test_tier4_scenarios.py      # Tier 4: Real-World Workload Scenarios & Multi-Product Pipelines
└── test_e2e_runner.py           # Unified master test runner executable via CLI, unittest, or pytest
```

### Tier Descriptions

| Tier | File | Scope | Target Test Count |
|:---|:---|:---|:---:|
| **Tier 1** | `test_tier1_features.py` | Isolated unit and behavioral verification of all 23 core features in isolation (Scrapers, 7 Golden Rules, 4 KO Gates, Finance, Visualizer, Dossier, CLI, Tests). | $\ge 115$ tests |
| **Tier 2** | `test_tier2_boundaries.py` | Edge cases E-01 through E-10 from methodology specification, zero division, extreme prices ($0 to $10,000), fringe tickets ($28.99, $69.01), Unicode/Spanish characters, missing fields. | $\ge 25$ tests |
| **Tier 3** | `test_tier3_combinations.py` | Cross-module pairwise interactions (Scraper $\rightarrow$ Candidate Pipeline $\rightarrow$ Audit Engine $\rightarrow$ Visualizer $\rightarrow$ Dossier), KO gate disqualification cascading, contender handling. | $\ge 15$ tests |
| **Tier 4** | `test_tier4_scenarios.py` | Full multi-product real-world datasets (8-15 products), winner filtering (SpineRelief Pro, Pet Hair Roller, Ultrasonic Cleaner), Remotion hook compliance, headless execution. | $\ge 10$ tests |
| **Runner** | `test_e2e_runner.py` | Master orchestrator providing structured console reporting, tier selection (`--tier N`), verbosity controls (`-v`), failfast (`--failfast`), and standardized exit codes. | Unified Harness |

---

## 3. Feature Traceability Matrix (All 23 Features)

Every feature in `PROJECT.md § Feature Inventory` is mapped to its primary test coverage tier:

| # | Feature Code | Milestone | Module / Contract | Primary Test Methods in Test Suite |
|:---|:---|:---:|:---|:---|
| 1 | TikTok Top Ads Extractor | M1 | `hunter.scrapers.tiktok_creative` | `test_f01_tiktok_*` (duration $\ge 21$d, web conversions, CTR parsing, query, fallback) |
| 2 | Meta Ad Library Scraper | M1 | `hunter.scrapers.meta_ad_library` | `test_f02_meta_*` (active ads count, scaling threshold $\ge 15$, query structure, retry, fallback) |
| 3 | Google Trends Client | M1 | `hunter.scrapers.google_trends` | `test_f03_trends_*` (3-mo momentum, breakout detection, backoff/retry, cache, fallback) |
| 4 | AliExpress Freight API | M1 | `hunter.scrapers.aliexpress_freight` | `test_f04_aliexpress_*` (freight calc, YunExpress/ePacket line, 7-12d window, cost derivation) |
| 5 | Candidate Pipeline & Schema | M1 | `hunter.models.RawCandidate` | `test_f05_candidate_schema_*` (validation, to_json/from_json, to_dict/from_dict, field errors) |
| 6 | Headless PowerShell Arch | M1 | `hunter.hunter_engine` / CLI | `test_f06_headless_powershell_*` (zero GUI imports, silent execution, non-blocking, headless) |
| 7 | Rule 1: Visual WOW Scorer | M2 | `hunter.audit_engine` | `test_f07_rule1_visual_wow_*` (0-3s demo, 100/70/40/0 pts rubric, weight 0.20 verification) |
| 8 | Rule 2: Acute Pain Scorer | M2 | `hunter.audit_engine` | `test_f08_rule2_acute_pain_*` (visceral pain, passion niche, 100/70/30/0 pts, weight 0.20) |
| 9 | Rule 3: Retail Scarcity | M2 | `hunter.audit_engine` | `test_f09_rule3_retail_scarcity_*` (supermarket absence, 100/60/20/0 pts, weight 0.10) |
| 10 | Rule 4: Unit Economics | M2 | `hunter.audit_engine` | `test_f10_rule4_unit_economics_*` (markup $\ge 3\times$, margin $\ge 65\%$, 100/85/50/0 pts, weight 0.20) |
| 11 | Rule 5: Ticket Range | M2 | `hunter.audit_engine` | `test_f11_rule5_ticket_range_*` ($29-$69 sweet spot, fringe tickets, 100/70/30/0 pts, weight 0.10) |
| 12 | Rule 6: Sizing & Fragility | M2 | `hunter.audit_engine` | `test_f12_rule6_sizing_fragility_*` (zero sizing/fragility, 100/60/0 pts, KO-1 trigger, weight 0.10) |
| 13 | Rule 7: Tracked Logistics | M2 | `hunter.audit_engine` | `test_f13_rule7_tracked_logistics_*` (7-12d window, YunExpress/ePacket, 100/60/20/0 pts, KO-3) |
| 14 | 4 Hard Knockout Gates | M2 | `hunter.audit_engine` | `test_f14_ko_gates_*` (KO-1 Fragility, KO-2 Margin, KO-3 Logistics, KO-4 Zero WOW, multi-gate) |
| 15 | Winner Tier Classifier | M2 | `hunter.audit_engine` | `test_f15_winner_tier_*` (WINNER $\ge 80$, CONTENDER 65-79.9, DISQUALIFIED $<65$, subscore floor) |
| 16 | Financial Equations Engine | M2 | `hunter.models.FinancialMetrics` | `test_f16_financial_equations_*` (landed cost, SRP rounding, fees $2.9\%+\$0.30$, reserve $1\%$, profit) |
| 17 | Comparison PNG Generator | M3 | `hunter.visualizer` | `test_f17_visualizer_png_*` (1920x1080 300 DPI, dark mode canvas, horizontal bars, scorecards) |
| 18 | Interactive HTML Dashboard | M3 | `hunter.visualizer` | `test_f18_visualizer_html_*` (HTML5 standalone, responsive, tooltips, filter toggles, glyphs) |
| 19 | 4 Conversion Hooks Engine | M4 | `hunter.dossier_generator` | `test_f19_conversion_hooks_*` (Curiosity, Pain Agitation, Contrarian, Transformation formulas) |
| 20 | Remotion Hook Formatter | M4 | `hunter.dossier_generator` | `test_f20_remotion_hooks_*` (TTS Neural2-C/B voices, 1.0s acoustic pause, Floating3DText) |
| 21 | Winner Technical Dossier | M4 | `hunter.dossier_generator` | `test_f21_winner_dossier_*` (minimum 3 validated winners, links, posting slots, markdown report) |
| 22 | Unified CLI Runner | M4 | `main.py` | `test_f22_cli_runner_*` (CLI parsing, help flag, headless pipeline coordination, exit codes) |
| 23 | E2E Opaque-Box Test Suite | M5 | `tests.test_e2e_runner` | `test_f23_test_suite_harness_*` (discovery, zero facades, deterministic timing, exit code 0) |

---

## 4. Execution & Verification Guide

### 4.1. Standard Test Commands

All test files are 100% compliant with standard Python `unittest` and `pytest`.

```powershell
# 1. Run via Unified Master E2E Runner (Recommended)
python -m unittest tests/test_e2e_runner.py -v

# 2. Run Master Runner Standalone
python tests/test_e2e_runner.py -v

# 3. Run Specific Tiers via Standalone Runner
python tests/test_e2e_runner.py --tier 1
python tests/test_e2e_runner.py --tier 2
python tests/test_e2e_runner.py --tier 3
python tests/test_e2e_runner.py --tier 4

# 4. Run via unittest Discovery (All Tiers)
python -m unittest discover -s tests -p "test_*.py" -v

# 5. Run via pytest (if installed)
pytest tests/ -v
```

### 4.2. Exit Code Semantics
- **`0`**: 100% assertions passed across all executed test cases.
- **`1`**: Any test failure, assertion error, or unhandled exception.
- **`2`**: Invalid CLI command line arguments or missing configuration.

---

## 5. Test Data Contracts & Offline Fixtures

To ensure 100% deterministic offline repeatability, the test suite utilizes standard candidate fixtures based on canonical e-commerce products:

1. **`SpineRelief Pro Ergonomic Gel Pad`**: High WOW (1.5s), severe pain relief, $11.00 landed cost, $39.99 SRP (3.64x markup, 67.84% net margin), YunExpress 8-11 days. **Canonical Winner ($\ge 85$ pts)**.
2. **`PurePaws Electrostatic Hair Remover`**: High WOW (1.0s), pet owner passion, $7.50 landed cost, $29.99 SRP (4.0x markup, 70.83% net margin), YunExpress 7-10 days. **Canonical Winner ($\ge 85$ pts)**.
3. **`SparkleWave Ultrasonic Cleaner`**: High WOW (2.0s), jewelry restoration, $12.00 landed cost, $44.99 SRP (3.75x markup, 69.17% net margin), YunExpress 8-12 days. **Canonical Winner ($\ge 80$ pts)**.
4. **`CrystalGlow Decorative Glass Vase`**: Fragile blown glass, trips **KO-1 Fragility Veto**.
5. **`SilkElegance Tailored Evening Dress`**: Millimetric chest/waist sizing, trips **KO-1 Sizing Veto**.
6. **`Cheap White USB Cable`**: Commodity retail item (Walmart $4.99, markup 1.8x), trips **KO-2 Margin Veto** and **KO-4 Commodity Veto**.
7. **`OceanBreeze Slow Freight Fan`**: 35-day sea freight, trips **KO-3 Logistics Veto**.
8. **`Compact Desktop Mini Heater`**: Landed $18.00, SRP $49.99 (2.78x markup), trips marginal penalty $\rightarrow$ **Contender (65-79 pts)**.
