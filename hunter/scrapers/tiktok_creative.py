"""TikTok Creative Center Top Ads scraper.

Targets:
- Endpoint: https://ads.tiktok.com/creative_radar_api/v1/top_ads/v2/list (POST)
- Objective: 2 (Web Conversions)
- Order by: "ctr" (Top Click-Through Rate)
- Longevity: >= 21 days continuously active
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from hunter.scrapers.base import BaseScraper

logger = logging.getLogger("hunter.scrapers.tiktok_creative")


class TikTokCreativeScraper(BaseScraper):
    """Headless scraper for TikTok Creative Center Inspiration > Top Ads."""

    API_ENDPOINT = "https://ads.tiktok.com/creative_radar_api/v1/top_ads/v2/list"
    REFERER_URL = "https://ads.tiktok.com/business/creativecenter/inspiration/top-ads/pc/en"

    def __init__(
        self,
        timeout: float = 12.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        offline_mode: bool = False,
    ):
        super().__init__(
            name="TikTokCreativeScraper",
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            offline_mode=offline_mode,
        )

    def search_top_ads(
        self,
        keyword: str = "",
        country_code: str = "US",
        period: int = 30,
        objective: int = 2,  # 2 = Web Conversions
        order_by: str = "ctr",
        min_duration_days: int = 21,
        page: int = 1,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Query TikTok Top Ads and filter by conversion objective and active duration >= 21d.
        
        Args:
            keyword: Optional search keyword or niche.
            country_code: Country code (e.g. 'US', 'GB', 'ES').
            period: Lookback period in days (7, 30, 180).
            objective: Optimization goal (2 = Web Conversions).
            order_by: Sorting criterion ('ctr', 'conversion_rate', 'likes').
            min_duration_days: Minimum active run time in days (default: 21).
            page: Results page index.
            limit: Page item limit.

        Returns:
            List of parsed winning ad dictionaries.
        """
        payload = {
            "page": page,
            "limit": limit,
            "period": period,
            "country_code": country_code,
            "objective": objective,
            "order_by": order_by,
            "industry": "",
            "search_keyword": keyword,
        }

        headers = {
            "Referer": self.REFERER_URL,
            "Origin": "https://ads.tiktok.com",
            "Content-Type": "application/json",
            "anonymous-open-id": str(uuid.uuid4()),
        }

        response_json = self.fetch_json(
            url=self.API_ENDPOINT,
            method="POST",
            headers=headers,
            json_data=payload,
            fallback_key=keyword.lower().strip() or "general_top_ads",
        )

        return self._parse_top_ads(response_json, min_duration_days=min_duration_days)

    def _parse_top_ads(
        self, response_json: Dict[str, Any], min_duration_days: int = 21
    ) -> List[Dict[str, Any]]:
        """Parse raw TikTok API materials and extract winning creative metrics."""
        winning_ads: List[Dict[str, Any]] = []
        materials = response_json.get("data", {}).get("materials", [])

        now_sec = time.time()
        for item in materials:
            first_pub = item.get("first_publish_time", 0)
            last_pub = item.get("last_publish_time", 0) or now_sec

            if first_pub > 0:
                duration_days = round((last_pub - first_pub) / 86400.0, 1)
            else:
                duration_days = float(item.get("duration_days", 0.0))

            ctr_percentile = item.get("ctr_rating", "top_20")

            # Apply the 21-day longevity filter
            if duration_days >= min_duration_days:
                winning_ads.append({
                    "ad_id": str(item.get("id", item.get("item_id", ""))),
                    "title": item.get("title", ""),
                    "brand": item.get("brand_name", ""),
                    "duration_days": int(duration_days),
                    "ctr_percentile": ctr_percentile,
                    "video_url": item.get("video_url", ""),
                    "cover_url": item.get("cover_url", ""),
                    "landing_page": item.get("landing_page_url", ""),
                    "likes": int(item.get("like_count", 0)),
                    "shares": int(item.get("share_count", 0)),
                    "industry": item.get("industry_key", "E-Commerce"),
                    "objective": "Web Conversions",
                })

        logger.info(
            f"[{self.name}] Parsed {len(winning_ads)} winning ads with duration >= {min_duration_days}d"
        )
        return winning_ads

    def _offline_fallback(
        self,
        fallback_key: Optional[str] = None,
        url: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Produce deterministic mock responses conforming to TikTok Top Ads JSON schema."""
        now_sec = int(time.time())
        day_sec = 86400

        # Verified fixture database corresponding to canonical Antigravity products
        all_materials = [
            {
                "id": "tt_ad_spinerelief_01",
                "title": "Stop lower back and sciatica pain with 7mm lumbar decompression in 30s",
                "brand_name": "SpineRelief",
                "first_publish_time": now_sec - (34 * day_sec),
                "last_publish_time": now_sec,
                "duration_days": 34,
                "ctr_rating": "top_1",
                "video_url": "https://v16-webapp-prime.tiktok.com/video/tos/useast2a/spinerelief_demo.mp4",
                "cover_url": "https://p16-sign.tiktokcdn-us.com/tos-useast2a-p/spinerelief_cover.jpeg",
                "landing_page_url": "https://tryspinerelief.com/products/lumbar-belt",
                "like_count": 84200,
                "share_count": 14500,
                "industry_key": "Health & Personal Care",
                "keywords": ["spine", "back pain", "lumbar", "traction", "sciatica"],
            },
            {
                "id": "tt_ad_aeroforce_02",
                "title": "130,000 RPM Pocket Violent Turbo Fan for car drying and detailing",
                "brand_name": "AeroForce Tech",
                "first_publish_time": now_sec - (28 * day_sec),
                "last_publish_time": now_sec,
                "duration_days": 28,
                "ctr_rating": "top_5",
                "video_url": "https://v16-webapp-prime.tiktok.com/video/tos/useast2a/aeroforce_demo.mp4",
                "cover_url": "https://p16-sign.tiktokcdn-us.com/tos-useast2a-p/aeroforce_cover.jpeg",
                "landing_page_url": "https://aeroforceturbofan.com/products/x3-duster",
                "like_count": 126000,
                "share_count": 31200,
                "industry_key": "Automotive & Tools",
                "keywords": ["turbo", "jet fan", "car drying", "detailing", "blower"],
            },
            {
                "id": "tt_ad_prosmile_03",
                "title": "Smart ultrasonic dental scaler that only vibrates on hard calculus and stops on gums",
                "brand_name": "ProSmile Oral",
                "first_publish_time": now_sec - (42 * day_sec),
                "last_publish_time": now_sec,
                "duration_days": 42,
                "ctr_rating": "top_1",
                "video_url": "https://v16-webapp-prime.tiktok.com/video/tos/useast2a/prosmile_demo.mp4",
                "cover_url": "https://p16-sign.tiktokcdn-us.com/tos-useast2a-p/prosmile_cover.jpeg",
                "landing_page_url": "https://getprosmile.com/products/ultrasonic-cleaner",
                "like_count": 210000,
                "share_count": 45800,
                "industry_key": "Beauty & Personal Care",
                "keywords": ["teeth", "dental", "calculus", "plaque", "ultrasonic", "oral"],
            },
            {
                "id": "tt_ad_steamfur_04",
                "title": "3-in-1 Steamy Pet Grooming Brush with cold ion mist for shedding removal",
                "brand_name": "SteamFur Official",
                "first_publish_time": now_sec - (38 * day_sec),
                "last_publish_time": now_sec,
                "duration_days": 38,
                "ctr_rating": "top_5",
                "video_url": "https://v16-webapp-prime.tiktok.com/video/tos/useast2a/steamfur_demo.mp4",
                "cover_url": "https://p16-sign.tiktokcdn-us.com/tos-useast2a-p/steamfur_cover.jpeg",
                "landing_page_url": "https://trysteamfur.com/products/pet-brush",
                "like_count": 178000,
                "share_count": 52000,
                "industry_key": "Pet Supplies",
                "keywords": ["pet", "cat", "dog", "fur", "grooming", "brush", "steam"],
            },
            {
                "id": "tt_ad_hydroclean_05",
                "title": "Dual chamber self-cleaning microfiber flat floor mop with squeeze squeegee",
                "brand_name": "HydroClean Home",
                "first_publish_time": now_sec - (25 * day_sec),
                "last_publish_time": now_sec,
                "duration_days": 25,
                "ctr_rating": "top_10",
                "video_url": "https://v16-webapp-prime.tiktok.com/video/tos/useast2a/hydroclean_demo.mp4",
                "cover_url": "https://p16-sign.tiktokcdn-us.com/tos-useast2a-p/hydroclean_cover.jpeg",
                "landing_page_url": "https://hydrocleanmop.com/products/mop-bucket-system",
                "like_count": 43000,
                "share_count": 8200,
                "industry_key": "Home Improvement",
                "keywords": ["mop", "cleaning", "floor", "bucket", "squeeze"],
            },
        ]

        key_lower = (fallback_key or "").lower()
        if key_lower and key_lower != "general_top_ads":
            filtered = [
                m for m in all_materials
                if any(kw in key_lower or key_lower in kw for kw in m.get("keywords", []))
                or key_lower in m.get("title", "").lower()
                or key_lower in m.get("brand_name", "").lower()
            ]
            if filtered:
                return {"code": 0, "msg": "success", "data": {"materials": filtered}}

        return {"code": 0, "msg": "success", "data": {"materials": all_materials}}
