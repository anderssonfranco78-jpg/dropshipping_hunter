"""Hunter Engine: Main prospecting and data aggregation engine.

Orchestrates headless extraction across:
- TikTok Creative Center (Top Ads: Web Conversions, >= 21d, high CTR)
- Meta Ad Library (Scaling footprint: 15-50+ active ads)
- Google Trends (Search momentum slope > +30% & Breakout queries)
- AliExpress Freight (Tracked carriers: YunExpress, ePacket, 7-12d)

Persists structured results conforming to RawCandidate schema in data/candidates.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from hunter.models import RawCandidate
from hunter.scrapers.aliexpress_freight import AliExpressFreightScraper
from hunter.scrapers.google_trends import GoogleTrendsScraper
from hunter.scrapers.meta_ad_library import MetaAdLibraryScraper
from hunter.scrapers.tiktok_creative import TikTokCreativeScraper

# Configure logging
logger = logging.getLogger("hunter.engine")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class HunterEngine:
    """Orchestrates candidate hunting, cross-source enrichment, and dataset persistence."""

    DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "candidates.json"

    def __init__(self, offline_mode: bool = False, timeout: float = 12.0):
        """Initialize HunterEngine with sub-scrapers.
        
        Args:
            offline_mode: If True, uses deterministic offline mocks across all scrapers.
            timeout: Network timeout in seconds.
        """
        self.offline_mode = offline_mode
        self.timeout = timeout
        
        self.tiktok_scraper = TikTokCreativeScraper(offline_mode=offline_mode, timeout=timeout)
        self.meta_scraper = MetaAdLibraryScraper(offline_mode=offline_mode, timeout=timeout)
        self.trends_scraper = GoogleTrendsScraper(offline_mode=offline_mode, timeout=timeout)
        self.freight_scraper = AliExpressFreightScraper(offline_mode=offline_mode, timeout=timeout)

    @classmethod
    def get_seed_candidates(cls) -> List[RawCandidate]:
        """Return the canonical validated seed candidates including winners and control products.
        
        Contains:
            - 4 Confirmed Winners (SpineRelief Pro, AeroForce X3, ProSmile Ultrasonic, SteamFur Pro)
            - 1 Contender (HydroClean Mop)
            - 5 Disqualified Controls (KO-1 Fragility, KO-1 Sizing, KO-2 Margin, KO-3 Logistics, KO-4 Zero WOW)
        """
        return [
            # 1. WINNER: SpineRelief Pro™
            RawCandidate(
                candidate_id="spinerelief-pro",
                name="SpineRelief Pro™ — Inflatable Lumbar Traction Belt",
                category="Health & Ergonomics",
                description=(
                    "Clinical-grade inflatable lumbar traction belt with 24 pneumatic columns providing "
                    "2.5 bar decompression for L1-L5 vertebrae and acute sciatica nerve relief."
                ),
                supplier_cost=10.00,
                shipping_cost=4.80,
                suggested_price=54.99,
                shipping_days_min=8,
                shipping_days_max=10,
                shipping_carrier="YunExpress Specialty Line",
                has_fragile_material=False,
                has_sizing_requirements=False,
                demo_visual_speed_sec=1.5,
                pain_level_score=95.0,
                retail_availability_score=95.0,
                ad_active_days=34,
                competitor_ad_count=38,
                google_trends_momentum=52.4,
                source_url="https://www.aliexpress.com/w/wholesale-lumbar-traction-belt.html",
                target_demographics={
                    "age": "35-65",
                    "gender": "all",
                    "occupations": ["truck drivers", "warehouse staff", "office desk workers"],
                    "symptoms": ["chronic lumbar stiffness", "sciatica nerve compression", "herniated disc pain"],
                },
            ),

            # 2. WINNER: AeroForce X3™
            RawCandidate(
                candidate_id="aeroforce-x3",
                name="AeroForce X3™ — 130,000 RPM Violent Turbo Blower",
                category="Automotive & Tactical Tools",
                description=(
                    "Handheld micro-turbine jet fan with 130,000 RPM brushless motor delivering 52 m/s "
                    "wind speed for contact-free car drying, detailing, and keyboard cleaning without swirl marks."
                ),
                supplier_cost=12.00,
                shipping_cost=4.80,
                suggested_price=59.99,
                shipping_days_min=8,
                shipping_days_max=11,
                shipping_carrier="YunExpress Special Battery Line",
                has_fragile_material=False,
                has_sizing_requirements=False,
                demo_visual_speed_sec=1.2,
                pain_level_score=90.0,
                retail_availability_score=90.0,
                ad_active_days=28,
                competitor_ad_count=42,
                google_trends_momentum=68.2,
                source_url="https://www.aliexpress.com/w/wholesale-turbo-jet-fan.html",
                target_demographics={
                    "age": "20-48",
                    "gender": "male",
                    "interests": ["car detailing", "PC gaming hardware", "tactical gear", "grilling"],
                },
            ),

            # 3. WINNER: ProSmile Ultrasonic™
            RawCandidate(
                candidate_id="prosmile-ultrasonic",
                name="ProSmile Ultrasonic™ — Smart Plaque & Calculus Scaler",
                category="Dental Health & Personal Care",
                description=(
                    "Home dental hygiene scaler with 40 kHz acoustic micro-vibrations and bioelectric "
                    "sensor that shatters solid calculus instantly while stopping automatically on gums."
                ),
                supplier_cost=4.50,
                shipping_cost=3.70,
                suggested_price=34.99,
                shipping_days_min=7,
                shipping_days_max=10,
                shipping_carrier="CJPacket Fast Line",
                has_fragile_material=False,
                has_sizing_requirements=False,
                demo_visual_speed_sec=1.5,
                pain_level_score=92.0,
                retail_availability_score=92.0,
                ad_active_days=42,
                competitor_ad_count=48,
                google_trends_momentum=41.6,
                source_url="https://www.aliexpress.com/w/wholesale-ultrasonic-dental-calculus-remover.html",
                target_demographics={
                    "age": "22-58",
                    "gender": "all",
                    "interests": ["teeth whitening", "coffee/tea drinkers", "smokers", "dental hygiene"],
                },
            ),

            # 4. WINNER: SteamFur Pro™
            RawCandidate(
                candidate_id="steamfur-pro",
                name="SteamFur Pro™ — 3-in-1 Ultrasonic Mist Pet Groomer",
                category="Pet Supplies & Home Care",
                description=(
                    "Conical silicone pet brush with integrated cold ion ultrasonic mist that neutralizes "
                    "static and allows peeling off shed pet hair in a single solid sheet in 2 seconds."
                ),
                supplier_cost=1.00,
                shipping_cost=2.50,
                suggested_price=29.99,
                shipping_days_min=7,
                shipping_days_max=10,
                shipping_carrier="YunExpress Ordinary",
                has_fragile_material=False,
                has_sizing_requirements=False,
                demo_visual_speed_sec=2.0,
                pain_level_score=88.0,
                retail_availability_score=85.0,
                ad_active_days=38,
                competitor_ad_count=29,
                google_trends_momentum=55.8,
                source_url="https://www.aliexpress.com/w/wholesale-steamy-cat-brush.html",
                target_demographics={
                    "age": "22-60",
                    "gender": "all",
                    "interests": ["cats", "dogs", "pet pampering", "clean home"],
                },
            ),

            # 5. CONTENDER: HydroClean Mop
            RawCandidate(
                candidate_id="hydroclean-mop",
                name="HydroClean Mop™ — Self-Cleaning Flat Floor Squeegee Mop",
                category="Home Improvement",
                description="Dual chamber microfiber flat mop system with scrape squeegee bucket.",
                supplier_cost=10.00,
                shipping_cost=6.00,
                suggested_price=44.99,
                shipping_days_min=10,
                shipping_days_max=14,
                shipping_carrier="AliExpress Standard Shipping",
                has_fragile_material=False,
                has_sizing_requirements=False,
                demo_visual_speed_sec=4.5,
                pain_level_score=65.0,
                retail_availability_score=55.0,
                ad_active_days=25,
                competitor_ad_count=12,
                google_trends_momentum=14.2,
                source_url="https://www.aliexpress.com/item/1005005544332211.html",
                target_demographics={"age": "25-60", "gender": "all"},
            ),

            # 6. DISQUALIFIED: GlowPillow Velvet (KO-4 Zero WOW & Retail Commodity)
            RawCandidate(
                candidate_id="glowpillow-velvet",
                name="GlowPillow Velvet — Decorative Living Room Accent Cushion",
                category="Home Decor",
                description="Plain square velvet throw cushion for couch styling.",
                supplier_cost=7.00,
                shipping_cost=4.00,
                suggested_price=24.99,
                shipping_days_min=8,
                shipping_days_max=12,
                shipping_carrier="YunExpress",
                has_fragile_material=False,
                has_sizing_requirements=False,
                demo_visual_speed_sec=10.0,
                pain_level_score=10.0,
                retail_availability_score=15.0,
                ad_active_days=5,
                competitor_ad_count=2,
                google_trends_momentum=-8.5,
                source_url="https://www.aliexpress.com/item/1005001122334455.html",
                target_demographics={"age": "20-50", "gender": "female"},
            ),

            # 7. DISQUALIFIED: GlassAura Teapot (KO-1 Fragility Veto)
            RawCandidate(
                candidate_id="glassaura-teapot",
                name="GlassAura — Handblown Borosilicate Glass Infuser Teapot",
                category="Kitchen & Dining",
                description="Artisan ultra-thin transparent glass teapot with internal glass spiral filter.",
                supplier_cost=10.00,
                shipping_cost=5.00,
                suggested_price=49.99,
                shipping_days_min=8,
                shipping_days_max=12,
                shipping_carrier="YunExpress",
                has_fragile_material=True,
                has_sizing_requirements=False,
                demo_visual_speed_sec=2.5,
                pain_level_score=40.0,
                retail_availability_score=60.0,
                ad_active_days=4,
                competitor_ad_count=1,
                google_trends_momentum=-4.2,
                source_url="https://www.aliexpress.com/item/1005007788990011.html",
                target_demographics={"age": "25-60", "gender": "all"},
            ),

            # 8. DISQUALIFIED: SlimFit Silk Dress (KO-1 Sizing Veto)
            RawCandidate(
                candidate_id="slimfit-silk-dress",
                name="SlimFit Silk — Evening Bodycon Tailored Formal Dress",
                category="Women's Apparel",
                description="Fitted evening dress requiring precise bust, waist, and hip millimetric tailoring.",
                supplier_cost=12.00,
                shipping_cost=6.00,
                suggested_price=59.99,
                shipping_days_min=8,
                shipping_days_max=12,
                shipping_carrier="YunExpress",
                has_fragile_material=False,
                has_sizing_requirements=True,
                demo_visual_speed_sec=5.0,
                pain_level_score=35.0,
                retail_availability_score=45.0,
                ad_active_days=8,
                competitor_ad_count=5,
                google_trends_momentum=5.1,
                source_url="https://www.aliexpress.com/item/1005009988776655.html",
                target_demographics={"age": "20-40", "gender": "female"},
            ),

            # 9. DISQUALIFIED: HeavyDuty Garden Hose (KO-2 Margin Collapse Veto)
            RawCandidate(
                candidate_id="heavyduty-garden-hose",
                name="HeavyDuty Expandable — 50ft Flexible Latex Garden Hose",
                category="Gardening & Outdoor",
                description="Expandable fabric garden hose with brass fittings.",
                supplier_cost=8.50,
                shipping_cost=5.50,
                suggested_price=24.00,
                shipping_days_min=8,
                shipping_days_max=12,
                shipping_carrier="YunExpress",
                has_fragile_material=False,
                has_sizing_requirements=False,
                demo_visual_speed_sec=2.0,
                pain_level_score=65.0,
                retail_availability_score=40.0,
                ad_active_days=12,
                competitor_ad_count=8,
                google_trends_momentum=-15.4,
                source_url="https://www.aliexpress.com/item/1005004433221100.html",
                target_demographics={"age": "30-65", "gender": "all"},
            ),

            # 10. DISQUALIFIED: Vintage Leather Watch (KO-3 Logistics Blackout Veto)
            RawCandidate(
                candidate_id="vintage-leather-watch",
                name="Vintage Chrono — Classic Quartz Leather Strap Watch",
                category="Fashion Accessories",
                description="Retro style quartz wristwatch with synthetic leather strap.",
                supplier_cost=4.00,
                shipping_cost=1.20,
                suggested_price=29.99,
                shipping_days_min=25,
                shipping_days_max=45,
                shipping_carrier="China Post Ordinary Small Packet",
                has_fragile_material=False,
                has_sizing_requirements=False,
                demo_visual_speed_sec=6.0,
                pain_level_score=15.0,
                retail_availability_score=30.0,
                ad_active_days=6,
                competitor_ad_count=3,
                google_trends_momentum=-12.0,
                source_url="https://www.aliexpress.com/item/1005006655443322.html",
                target_demographics={"age": "18-50", "gender": "male"},
            ),
        ]

    def harvest(
        self,
        search_keywords: Optional[List[str]] = None,
        include_seeds: bool = True,
    ) -> List[RawCandidate]:
        """Execute prospecting workflow across all intelligence scrapers.
        
        Args:
            search_keywords: Optional list of niche keywords to query.
            include_seeds: If True, merges and validates canonical seed products.

        Returns:
            List of validated RawCandidate instances.
        """
        candidates_map: Dict[str, RawCandidate] = {}

        if include_seeds:
            for seed in self.get_seed_candidates():
                candidates_map[seed.candidate_id] = seed

        keywords = search_keywords or ["lumbar traction", "turbo jet fan", "dental calculus", "steamy pet brush"]

        logger.info(f"[{self.__class__.__name__}] Commencing candidate harvesting across {len(keywords)} keyword targets...")

        for kw in keywords:
            try:
                # 1. TikTok Top Ads signal
                tiktok_ads = self.tiktok_scraper.search_top_ads(keyword=kw, min_duration_days=21)
                ad_active_days = max([ad["duration_days"] for ad in tiktok_ads], default=25)

                # 2. Meta Ad Library scaling signal
                meta_res = self.meta_scraper.analyze_scaling_footprint(query=kw)
                competitor_ad_count = meta_res["active_ad_count"]

                # 3. Google Trends momentum signal
                trends_res = self.trends_scraper.get_trend_analysis(keyword=kw)
                momentum = trends_res["momentum_pct"]

                # 4. AliExpress Logistics & Landed Cost signal
                slug = kw.lower().replace(" ", "-")
                freight_res = self.freight_scraper.get_freight_options(product_id=slug, supplier_cost=10.0)

                # If existing in seed, update signals
                if slug in candidates_map:
                    candidate = candidates_map[slug]
                    candidate.ad_active_days = ad_active_days
                    candidate.competitor_ad_count = competitor_ad_count
                    candidate.google_trends_momentum = momentum
                    candidate.shipping_carrier = freight_res["selected_carrier"]
                    candidate.shipping_cost = freight_res["shipping_cost"]
                    candidate.shipping_days_min = freight_res["shipping_days_min"]
                    candidate.shipping_days_max = freight_res["shipping_days_max"]
                    logger.info(f"Updated live signals for existing candidate '{slug}'")

            except Exception as exc:
                logger.warning(f"Error during enrichment of keyword '{kw}': {exc}")

        result_list = list(candidates_map.values())
        logger.info(f"Harvest complete. Total candidates available: {len(result_list)}")
        return result_list

    def save_candidates(
        self,
        candidates: List[RawCandidate],
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Persist candidates list to JSON file atomically."""
        target_path = Path(output_path) if output_path else self.DEFAULT_OUTPUT_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Validate all candidates
        for c in candidates:
            errs = c.validate()
            if errs:
                logger.warning(f"Candidate {c.candidate_id} has validation warnings: {errs}")

        serialized = [c.to_dict() for c in candidates]

        # Atomic write: write to temp file then replace
        temp_path = target_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2, ensure_ascii=False)

        temp_path.replace(target_path)
        logger.info(f"Persisted {len(candidates)} candidates to {target_path}")
        return target_path

    @classmethod
    def load_candidates(cls, filepath: Optional[Union[str, Path]] = None) -> List[RawCandidate]:
        """Load and deserialize candidates from JSON file."""
        target_path = Path(filepath) if filepath else cls.DEFAULT_OUTPUT_PATH
        if not target_path.exists():
            raise FileNotFoundError(f"Candidates file not found at: {target_path}")

        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError(f"Expected list of candidate objects in JSON, got {type(data)}")

        return [RawCandidate.from_dict(item) for item in data]


def main():
    """CLI entrypoint for running the Hunter Prospecting Engine."""
    parser = argparse.ArgumentParser(description="Dropshipping Winner Intelligence & Prospecting Engine")
    parser.add_argument(
        "--offline",
        action="store_true",
        default=False,
        help="Run in 100%% deterministic offline mock mode without making live network calls.",
    )
    parser.add_argument(
        "--seed-only",
        action="store_true",
        default=False,
        help="Export canonical seed candidates directly without extra scraper queries.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Target output path for candidates.json (defaults to data/candidates.json).",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("  DROPSHIPPING WINNER INTELLIGENCE & PROSPECTING SYSTEM")
    print("  Milestone M1: Data Sources & Headless Hunter Engine")
    print("=" * 80)
    print(f"Mode: {'OFFLINE (Deterministic)' if args.offline else 'LIVE/HYBRID'}")

    engine = HunterEngine(offline_mode=args.offline)

    if args.seed_only:
        candidates = engine.get_seed_candidates()
    else:
        candidates = engine.harvest(include_seeds=True)

    target_file = engine.save_candidates(candidates, output_path=args.output)

    print("\n[+] Harvested Candidates Summary Table:")
    print("-" * 88)
    print(f"{'Candidate ID':<22} | {'Category':<20} | {'Landed':<8} | {'SRP':<8} | {'Markup':<6} | {'Status':<10}")
    print("-" * 88)
    for c in candidates:
        fin = c.compute_financials()
        landed_str = f"${fin.landed_cost:.2f}"
        srp_str = f"${fin.srp:.2f}"
        markup_str = f"{fin.markup_multiplier:.2f}x"
        status_hint = "WINNER" if fin.markup_multiplier >= 3.0 and fin.net_margin_pct >= 65.0 and not c.has_fragile_material and not c.has_sizing_requirements and c.shipping_days_max <= 14 else "TEST/CTRL"
        print(f"{c.candidate_id:<22} | {c.category[:20]:<20} | {landed_str:<8} | {srp_str:<8} | {markup_str:<6} | {status_hint:<10}")
    print("-" * 88)
    print(f"\n[SUCCESS] Extracted {len(candidates)} candidates successfully written to: {target_file}\n")


if __name__ == "__main__":
    main()
