"""Master CLI Entrypoint: Dropshipping Winner Intelligence & Prospecting System.

Unified programmatically driven entrypoint coordinating the complete 4-stage pipeline:
1. Data Prospecting & Multi-Source Extraction (hunter.hunter_engine.HunterEngine)
   -> Persists raw structured candidates to data/candidates.json
2. 7 Golden Rules Quantitative Audit (hunter.audit_engine.AuditEngine)
   -> Audits 4 KO Gates, 7 Operational Rubrics, Unit Economics -> data/audit_results.json
3. Visual Analytics & Comparison Dashboard (hunter.visualizer.Visualizer)
   -> Generates ranking_productos.png (1080p @ 300 DPI) & ranking_productos.html
4. Winner Dossier & 4 Conversion Hooks Synthesizer (hunter.dossier_generator.DossierGenerator)
   -> Formats Remotion Modalidad 3 blueprints -> dossier_productos_ganadores.md

Strictly adheres to headless constraints:
- Zero PyAutoGUI / zero visible window hijackers / non-blocking execution.
- Windows PowerShell UTF-8 console output safe.
- Deterministic offline fallback enabled via --offline flag.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hunter.audit_engine import AuditEngine
from hunter.dossier_generator import DossierGenerator
from hunter.hunter_engine import HunterEngine
from hunter.models import AuditResult, RawCandidate

# Lazy/conditional import for visualizer
try:
    from hunter.visualizer import Visualizer
    HAS_VISUALIZER = True
except ImportError:
    HAS_VISUALIZER = False

# Configure logging
logger = logging.getLogger("hunter.cli")


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure console logger formatting and severity level."""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)


def run_harvest_stage(
    data_dir: Path,
    offline_mode: bool = False,
    keywords: Optional[List[str]] = None,
) -> Tuple[List[RawCandidate], Path]:
    """Execute Stage 1: Prospecting across TikTok, Meta, Trends, and AliExpress."""
    logger.info("================================================================================")
    logger.info(" [STAGE 1/4] PROSPECTING & MULTI-SOURCE EXTRACTION (HunterEngine)")
    logger.info("================================================================================")
    logger.info(" Mode: %s", "Deterministic Offline Mock" if offline_mode else "Live Network Scraping")

    engine = HunterEngine(offline_mode=offline_mode)
    candidates = engine.harvest(search_keywords=keywords, include_seeds=True)
    
    candidates_path = data_dir / "candidates.json"
    engine.save_candidates(candidates, output_path=candidates_path)
    logger.info(" [+] Extracted %d product candidates -> %s", len(candidates), candidates_path)
    return candidates, candidates_path


def run_audit_stage(
    candidates: List[RawCandidate],
    data_dir: Path,
    export_json_path: Optional[Union[str, Path]] = None,
) -> Tuple[List[AuditResult], Path]:
    """Execute Stage 2: 7 Golden Rules Audit & Unit Economics calculation."""
    logger.info("================================================================================")
    logger.info(" [STAGE 2/4] 7 GOLDEN RULES AUDIT & SCORING (AuditEngine)")
    logger.info("================================================================================")

    auditor = AuditEngine(data_dir=data_dir)
    results = auditor.audit_candidates(candidates)

    audit_path = Path(export_json_path) if export_json_path else data_dir / "audit_results.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    serialized = [r.to_dict() for r in results]
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2, ensure_ascii=False)

    winners = [r for r in results if r.tier == "WINNER"]
    contenders = [r for r in results if r.tier == "CONTENDER"]
    disqualified = [r for r in results if r.tier == "DISQUALIFIED"]

    logger.info(
        " [+] Audited %d candidates: 🏆 %d Winners, ⚠️ %d Contenders, ❌ %d Disqualified -> %s",
        len(results), len(winners), len(contenders), len(disqualified), audit_path
    )
    return results, audit_path


def run_visualize_stage(
    results: List[AuditResult],
    output_png: str = "ranking_productos.png",
    output_html: str = "ranking_productos.html",
) -> Dict[str, str]:
    """Execute Stage 3: High-Res PNG and Interactive HTML Ranking Dashboard."""
    logger.info("================================================================================")
    logger.info(" [STAGE 3/4] VISUAL ANALYTICS & DASHBOARD (Visualizer)")
    logger.info("================================================================================")

    if not HAS_VISUALIZER:
        logger.warning("Visualizer module (hunter.visualizer) not available. Skipping visual generation.")
        return {"png": "", "html": ""}

    vis = Visualizer()
    paths = vis.visualize_all(results, output_png=output_png, output_html=output_html)
    logger.info(" [+] Generated Comparison Chart (1080p @ 300 DPI): %s", paths.get("png"))
    logger.info(" [+] Generated Interactive Dashboard (HTML5): %s", paths.get("html"))
    return paths


def run_dossier_stage(
    results: List[AuditResult],
    data_dir: Path,
    output_path: str = "dossier_productos_ganadores.md",
) -> Path:
    """Execute Stage 4: Winner Dossier & 4 Remotion Modalidad 3 Conversion Hooks."""
    logger.info("================================================================================")
    logger.info(" [STAGE 4/4] WINNER DOSSIER & 4 CONVERSION HOOKS (DossierGenerator)")
    logger.info("================================================================================")

    generator = DossierGenerator(data_dir=data_dir)
    dossier_file = Path(output_path)
    generator.generate_dossier(results, output_path=dossier_file)

    winners = [r for r in results if r.tier == "WINNER" or r.passed_audit]
    logger.info(
        " [+] Compiled Winner Dossier containing %d validated products & Remotion specs -> %s",
        len(winners), dossier_file
    )
    return dossier_file


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments supporting full pipeline and individual stages."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Dropshipping Winner Intelligence & Prospecting System — Master CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --offline                     # Run full end-to-end pipeline in deterministic offline mode
  python main.py --harvest-only                # Extract raw candidates to data/candidates.json
  python main.py --audit-only                  # Audit existing candidates to data/audit_results.json
  python main.py --visualize-only              # Render ranking_productos.png & ranking_productos.html
  python main.py --dossier-only                # Compile dossier_productos_ganadores.md
  python main.py --export-json custom.json     # Export audit results to custom JSON path
  python main.py --generate-dossier out.md     # Compile dossier to custom Markdown path
        """,
    )

    # Core Execution Modes
    parser.add_argument(
        "--offline",
        action="store_true",
        default=False,
        help="Execute in 100%% deterministic offline fallback mode with local fixtures (zero network calls)",
    )

    # Single-stage execution switches
    parser.add_argument(
        "--harvest-only",
        action="store_true",
        default=False,
        help="Run only Stage 1: Prospecting / data harvesting",
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        default=False,
        help="Run only Stage 2: 7 Golden Rules quantitative audit",
    )
    parser.add_argument(
        "--visualize-only",
        action="store_true",
        default=False,
        help="Run only Stage 3: Visual analytics (ranking_productos.png & .html)",
    )
    parser.add_argument(
        "--dossier-only",
        action="store_true",
        default=False,
        help="Run only Stage 4: Winner dossier and 4 conversion hooks",
    )

    # Artifact output overrides
    parser.add_argument(
        "--export-json",
        nargs="?",
        const="data/audit_results.json",
        default=None,
        metavar="PATH",
        help="Export structured audit results to JSON (default: data/audit_results.json)",
    )
    parser.add_argument(
        "--generate-dossier",
        nargs="?",
        const="dossier_productos_ganadores.md",
        default="dossier_productos_ganadores.md",
        metavar="PATH",
        help="Destination path for winner dossier Markdown (default: dossier_productos_ganadores.md)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Base directory for persistence data files (default: 'data')",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Generic target output file override",
    )
    parser.add_argument(
        "--keywords",
        type=str,
        nargs="*",
        default=None,
        help="Optional search query keywords for prospecting",
    )

    # Logging controls
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable detailed debug logging output",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        default=False,
        help="Suppress informational console logs",
    )

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Master CLI execution function."""
    args = parse_arguments(argv)
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    data_dir = (PROJECT_ROOT / args.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    dossier_output = args.output if (args.dossier_only and args.output) else args.generate_dossier

    logger.info("================================================================================")
    logger.info(" 🚀 DROPSHIPPING HUNTER — WINNER INTELLIGENCE & PROSPECTING SYSTEM")
    logger.info("================================================================================")
    logger.info(" Project Root: %s", PROJECT_ROOT)
    logger.info(" Data Dir    : %s", data_dir)
    logger.info(" Mode        : %s", "Deterministic Offline" if args.offline else "Programmatic Live")
    logger.info(" Headless    : True (Zero GUI / Windows PowerShell Clean)")
    logger.info("--------------------------------------------------------------------------------")

    try:
        # Check single-stage triggers
        if args.harvest_only:
            run_harvest_stage(data_dir=data_dir, offline_mode=args.offline, keywords=args.keywords)
            print("\n[SUCCESS] Stage 1 (Harvest) completed successfully.")
            return 0

        if args.audit_only:
            candidates_path = data_dir / "candidates.json"
            if not candidates_path.exists():
                logger.info("candidates.json not found; running harvest first...")
                candidates, _ = run_harvest_stage(data_dir=data_dir, offline_mode=args.offline, keywords=args.keywords)
            else:
                with open(candidates_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                candidates = [RawCandidate.from_dict(item) for item in raw_data]
            run_audit_stage(candidates, data_dir=data_dir, export_json_path=args.export_json)
            print("\n[SUCCESS] Stage 2 (Audit) completed successfully.")
            return 0

        if args.visualize_only:
            audit_path = data_dir / "audit_results.json"
            if not audit_path.exists():
                logger.error("Audit results not found at: %s. Run audit stage first.", audit_path)
                return 1
            with open(audit_path, "r", encoding="utf-8") as f:
                raw_audit = json.load(f)
            audit_results = [AuditResult.from_dict(item) for item in raw_audit]
            run_visualize_stage(audit_results)
            print("\n[SUCCESS] Stage 3 (Visualize) completed successfully.")
            return 0

        if args.dossier_only:
            audit_path = data_dir / "audit_results.json"
            if not audit_path.exists():
                logger.error("Audit results not found at: %s. Run audit stage first.", audit_path)
                return 1
            with open(audit_path, "r", encoding="utf-8") as f:
                raw_audit = json.load(f)
            audit_results = [AuditResult.from_dict(item) for item in raw_audit]
            run_dossier_stage(audit_results, data_dir=data_dir, output_path=dossier_output)
            print(f"\n[SUCCESS] Stage 4 (Dossier) completed successfully -> {dossier_output}")
            return 0

        # Full End-to-End Pipeline Execution
        # 1. Harvest
        candidates, _ = run_harvest_stage(
            data_dir=data_dir,
            offline_mode=args.offline,
            keywords=args.keywords,
        )

        # 2. Audit
        audit_results, _ = run_audit_stage(
            candidates=candidates,
            data_dir=data_dir,
            export_json_path=args.export_json,
        )

        # 3. Visualize
        run_visualize_stage(
            results=audit_results,
            output_png="ranking_productos.png",
            output_html="ranking_productos.html",
        )

        # 4. Dossier & Hooks
        dossier_path = run_dossier_stage(
            results=audit_results,
            data_dir=data_dir,
            output_path=dossier_output,
        )

        logger.info("================================================================================")
        logger.info(" ✨ FULL PIPELINE EXECUTED SUCCESSFULLY")
        logger.info("================================================================================")
        logger.info(" 1. Candidates Dataset : %s", data_dir / "candidates.json")
        logger.info(" 2. Audit Report       : %s", data_dir / "audit_results.json")
        logger.info(" 3. Comparison Chart   : ranking_productos.png")
        logger.info(" 4. HTML Dashboard     : ranking_productos.html")
        logger.info(" 5. Winner Dossier     : %s", dossier_path)
        logger.info("================================================================================")
        print(f"\n[SUCCESS] End-to-End Execution Complete. Winner dossier ready at: {dossier_path}")
        return 0

    except Exception as exc:
        logger.exception("Fatal unhandled error in pipeline: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
