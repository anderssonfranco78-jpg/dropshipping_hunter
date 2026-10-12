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
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from hunter.models import RawCandidate
from hunter.provenance import CACHED, LIVE, MOCK, NO_LIVE_DATA, UNAVAILABLE, NoLiveDataError
from hunter.scrapers.aliexpress_freight import AliExpressFreightScraper
from hunter.scrapers.google_trends import GoogleTrendsScraper
from hunter.scrapers.meta_ad_library import MetaAdLibraryScraper
from hunter.scrapers.tiktok_creative import TikTokCreativeScraper
from hunter.scrapers.youtube_shorts import YouTubeShortsScraper

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

    # Search keyword -> candidate_id (the old code derived a slug from the keyword that never matched
    # a real candidate id, so live signals were silently never applied).
    KEYWORD_TO_CANDIDATE = {
        "lumbar traction": "spinerelief-pro",
        "turbo jet fan": "aeroforce-x3",
        "dental calculus": "prosmile-ultrasonic",
        "steamy pet brush": "steamfur-pro",
    }

    DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "candidates.json"

    def __init__(self, offline_mode: bool = False, timeout: float = 12.0, youtube: bool = False):
        """Initialize HunterEngine with sub-scrapers.
        
        Args:
            offline_mode: DEV/TEST ONLY. Uses deterministic MOCK fixtures; results are stamped MOCK.
            timeout: Network timeout in seconds.
            youtube: also measure YouTube Shorts per product (main.py turns it on; tests leave it off
                so they never touch the network). Never queried in offline mode.
        """
        self.offline_mode = offline_mode
        self.youtube_enabled = youtube and not offline_mode
        self.youtube_scraper = YouTubeShortsScraper()
        self.google_paused = False  # set on the first HTTP 429: Google is not asked again this run
        # Last REAL Google measurement per keyword (data/trends_cache.json). Used, dated, when Google
        # refuses a run, so a rate limit does not reshuffle the ranking. Never older than 7 days.
        self.trends_cache: Dict[str, Dict[str, Any]] = {}
        self._last_google = 0.0
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
                source_url="https://www.aliexpress.com/item/1005006626002554.html",
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
                source_url="https://www.aliexpress.com/item/1005009719197258.html",
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
                source_url="https://www.aliexpress.com/item/1005005236582798.html",
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
                supplier_cost=8.27,  # Green Mango variant (994 units). The $7.70 variant has ~17 units: a trap.
                shipping_cost=0.00,
                suggested_price=29.99,
                shipping_days_min=7,
                shipping_days_max=12,
                shipping_carrier="AliExpress Choice (Free Shipping 7-12D)",
                has_fragile_material=False,
                has_sizing_requirements=False,
                demo_visual_speed_sec=2.0,
                pain_level_score=88.0,
                retail_availability_score=85.0,
                ad_active_days=38,
                competitor_ad_count=29,
                google_trends_momentum=55.8,
                source_url="https://www.aliexpress.com/item/1005007791672610.html",
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

        keywords = search_keywords or list(self.KEYWORD_TO_CANDIDATE)

        logger.info(f"[{self.__class__.__name__}] Commencing candidate harvesting across {len(keywords)} keyword targets...")

        for kw in keywords:
            cid = self.KEYWORD_TO_CANDIDATE.get(kw.lower().strip(), kw.lower().strip().replace(" ", "-"))
            candidate = candidates_map.get(cid)
            if candidate is None:
                logger.info(f"Keyword '{kw}' no corresponde a ningún candidato conocido; se omite.")
                continue
            self._enrich(candidate, kw, sources=("tiktok", "meta", "trends", "freight"), apply_freight_costs=True)
            logger.info(f"[{candidate.candidate_id}] señales: {candidate.data_status}")

        result_list = list(candidates_map.values())
        logger.info(f"Harvest complete. Total candidates available: {len(result_list)}")
        return result_list

    # Sources whose public endpoints are retired/blocked (404/403 as of Oct 2026). Not queried by
    # default: they are shown grey "No disponible" instead of a daily red alarm.
    RETIRED_SOURCES = ("tiktok", "meta", "freight")

    @staticmethod
    def _clean_series(series) -> Optional[List[int]]:
        """Real Trends points (0-100, last 14) or None. Malformed points are dropped, never invented."""
        if not isinstance(series, (list, tuple)):
            return None
        clean = [
            int(v) for v in series
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")
        ]
        return clean[-52:] if len(clean) >= 2 else None

    def _enrich(
        self,
        candidate: RawCandidate,
        kw: str,
        sources,
        apply_freight_costs: bool,
    ) -> None:
        """Query the requested sources for one candidate; mark every other tracked source UNAVAILABLE.

        Each signal is independent: one blocked source must not hide the others, and a failure is
        recorded as NO_LIVE_DATA instead of keeping/inventing a value.
        """
        cid = candidate.candidate_id
        ok_status = MOCK if self.offline_mode else LIVE

        def signal(name: str, fetch):
            if name not in sources:
                candidate.data_status[name] = UNAVAILABLE
                return None
            try:
                result = fetch()
                candidate.data_status[name] = ok_status
                return result
            except NoLiveDataError as exc:
                candidate.data_status[name] = NO_LIVE_DATA
                logger.warning(f"[{cid}] {name}: {exc}")
            except Exception as exc:  # parsing bug / unexpected payload: still never fabricate
                candidate.data_status[name] = NO_LIVE_DATA
                logger.warning(f"[{cid}] {name}: error inesperado: {exc}")
            return None

        tiktok_ads = signal("tiktok", lambda: self.tiktok_scraper.search_top_ads(keyword=kw, min_duration_days=21))
        if tiktok_ads:
            candidate.ad_active_days = max(ad["duration_days"] for ad in tiktok_ads)

        meta_res = signal("meta", lambda: self.meta_scraper.analyze_scaling_footprint(query=kw))
        if meta_res is not None:
            candidate.competitor_ad_count = meta_res["active_ad_count"]

        trends_res = signal("trends", lambda: self._trends(kw))
        if trends_res is not None and trends_res.get("_cached"):
            candidate.data_status["trends"] = CACHED
        if trends_res is not None:
            candidate.google_trends_momentum = trends_res["momentum_pct"]
            candidate.trends_series = self._clean_series(trends_res.get("timeline_data"))
            labels = trends_res.get("timeline_labels") or []
            candidate.trends_labels = (labels[-len(candidate.trends_series):]
                                       if candidate.trends_series and len(labels) >= len(candidate.trends_series) else None)
            candidate.trends_meta = {k: trends_res[k] for k in
                                     ("low_volume", "zero_share", "peak_ratio", "mean_recent", "mean_prior", "resolution")
                                     if k in trends_res}
            if trends_res.get("_cached"):
                candidate.trends_meta["measured_at"] = trends_res.get("_measured_at")
                candidate.trends_meta["cache"] = trends_res.get("_why", "respaldo")
        else:
            candidate.trends_series = None  # failed / not queried: never keep a stale series
            candidate.trends_labels = None
            candidate.trends_meta = None

        freight_res = signal(
            "freight",
            lambda: self.freight_scraper.get_freight_options(
                product_id=(re.search(r"/item/(\d+)", candidate.source_url) or [None, cid])[1],
                supplier_cost=candidate.supplier_cost,
            ),
        )
        if freight_res is not None:
            candidate.shipping_carrier = freight_res["selected_carrier"]
            candidate.shipping_days_min = freight_res["shipping_days_min"]
            candidate.shipping_days_max = freight_res["shipping_days_max"]
            if apply_freight_costs:  # operator-verified costs are never overwritten
                candidate.shipping_cost = freight_res["shipping_cost"]


    # Google Trends is WEEKLY data: asking more than once a day per term adds nothing and gets the network
    # flagged ("unusual traffic" + CAPTCHA). The cache (data/trends_cache.json) is shared by the PC and the
    # cloud robot through git, so whoever runs first measures and the other reuses it.
    TRENDS_CACHE_DAYS = 7        # dated fallback when Google refuses
    TRENDS_FRESH_HOURS = 20      # younger than this: reuse, do not ask Google again
    BLOCK_PAUSE_HOURS = 6        # after a 429/CAPTCHA on the PC, leave Google alone this long
    GOOGLE_GAP_SEC = (4.0, 7.0)  # spacing between two real Google lookups

    @staticmethod
    def _in_cloud() -> bool:
        return os.environ.get("GITHUB_ACTIONS") == "true"

    def _block_key(self) -> str:
        return "__bloqueo_nube__" if self._in_cloud() else "__bloqueo_pc__"

    def google_blocked_until(self) -> float:
        if self._in_cloud():  # cloud runners get a new IP every run: a past block does not apply
            return 0.0
        return float((self.trends_cache.get(self._block_key()) or {}).get("until_ts", 0.0))

    def _trends(self, keyword: str, fresh_hours: Optional[float] = None) -> Dict[str, Any]:
        """Google Trends: fresh cache first, then ONE careful request, then a dated fallback.

        Never retries a refusal in the same run (circuit breaker) and, on the PC, pauses Google for
        BLOCK_PAUSE_HOURS after a 429/CAPTCHA so the block can expire instead of getting longer.
        """
        key = keyword.lower().strip()
        cached = self.trends_cache.get(key)
        age = time.time() - (cached or {}).get("_measured_ts", 0)
        fresh = (fresh_hours if fresh_hours is not None else self.TRENDS_FRESH_HOURS) * 3600
        if not self.offline_mode and cached and age <= fresh:
            return dict(cached, _cached=True, _why="reciente")
        try:
            if self.google_paused:
                raise NoLiveDataError("GoogleTrendsScraper", "Google pidió una pausa (HTTP 429): no se insiste en esta corrida")
            if self.google_blocked_until() > time.time():
                raise NoLiveDataError("GoogleTrendsScraper", "Google bloqueó temporalmente esta red (CAPTCHA): se respeta la pausa")
            if not self.offline_mode:
                wait = random.uniform(*self.GOOGLE_GAP_SEC) - (time.time() - self._last_google)
                if wait > 0:
                    time.sleep(wait)
                self._last_google = time.time()
            result = self.trends_scraper.get_trend_analysis(keyword=keyword)
        except NoLiveDataError as exc:
            if "429" in str(exc):
                self.google_paused = True
                if not self._in_cloud() and not self.offline_mode:
                    self.trends_cache[self._block_key()] = {
                        "until_ts": time.time() + self.BLOCK_PAUSE_HOURS * 3600,
                        "at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
            if not self.offline_mode and cached and age <= self.TRENDS_CACHE_DAYS * 86400:
                logger.warning(f"Google no respondió para '{keyword}': se usa su medición real del {cached.get('_measured_at')}")
                return dict(cached, _cached=True, _why="respaldo")
            raise
        if not self.offline_mode and result.get("status") == LIVE:
            self.trends_cache[key] = dict(result, _measured_ts=time.time(),
                                          _measured_at=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()))
        return result

    def rising(self, keyword: str) -> List[Dict[str, str]]:
        """Google's rising searches, only when Google is answering in this run (one extra request)."""
        if self.google_paused or self.google_blocked_until() > time.time() or self.offline_mode:
            return []
        try:
            return self.trends_scraper.rising_queries(keyword)
        except NoLiveDataError as exc:
            if "429" in str(exc):
                self.google_paused = True
            return []

    def load_trends_cache(self, path: Union[str, Path]) -> None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.trends_cache = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            self.trends_cache = {}

    def save_trends_cache(self, path: Union[str, Path]) -> None:
        cutoff, now = time.time() - self.TRENDS_CACHE_DAYS * 86400, time.time()
        keep = {k: v for k, v in self.trends_cache.items()
                if v.get("_measured_ts", 0) >= cutoff or v.get("until_ts", 0) > now}
        Path(path).write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding="utf-8")

    def _measure_youtube(self, candidate: RawCandidate) -> None:
        """YouTube Shorts interest for the product phrase. Off (UNAVAILABLE) unless enabled."""
        kw = candidate.video_keyword or candidate.trends_keyword
        candidate.youtube = None
        if not self.youtube_enabled or not kw:
            candidate.data_status["youtube"] = UNAVAILABLE
            return
        try:
            candidate.youtube = self.youtube_scraper.measure(kw)
            candidate.data_status["youtube"] = LIVE
        except NoLiveDataError as exc:
            candidate.data_status["youtube"] = NO_LIVE_DATA
            logger.warning(f"[{candidate.candidate_id}] youtube: {exc}")
        except Exception as exc:  # parsing bug: still never fabricate
            candidate.data_status["youtube"] = NO_LIVE_DATA
            logger.warning(f"[{candidate.candidate_id}] youtube: error inesperado: {exc}")

    def harvest_products(self, candidates: List[RawCandidate], probe_all: bool = False) -> List[RawCandidate]:
        """Enrich operator products (data/user_products.json) with live signals.

        By default only Google Trends is queried (the one source that answers). ``probe_all`` also tries
        the retired TikTok/Meta/Freight endpoints. Operator costs and stock are never modified here.
        """
        sources = ("trends",) + (self.RETIRED_SOURCES if probe_all else ())
        for candidate in candidates:
            if candidate.trends_keyword:
                self._enrich(candidate, candidate.trends_keyword, sources=sources, apply_freight_costs=False)
            else:
                for name in ("tiktok", "meta", "freight"):
                    candidate.data_status[name] = UNAVAILABLE
                logger.info(f"[{candidate.candidate_id}] sin trends_keyword: Google Trends no consultado")
            self._measure_youtube(candidate)
            logger.info(f"[{candidate.candidate_id}] señales: {candidate.data_status}")
        logger.info(f"Harvest (productos del operador) completo: {len(candidates)} productos")
        return candidates

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
        help="DEV/TEST ONLY: deterministic MOCK fixtures, no network. Results are stamped MOCK and must not be published.",
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
