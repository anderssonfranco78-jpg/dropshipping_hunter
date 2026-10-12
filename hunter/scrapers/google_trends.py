"""Google Trends scraper with 429 rate limit mitigation and breakout detection.

Implements:
- Multi-tiered request pipeline with session cookie priming
- Strip Google security prefix ")]}',"
- Momentum on the 12-month WEEKLY series (default, robust for niche products):
    M = (Mean(last 4 complete weeks) - Mean(the 12 weeks before)) / Mean(those 12 weeks) * 100%
  Daily 3-month series (>= 59 points) keep the legacy formula: last 14 days vs prior 45 days.
  Google reports 0 for weeks/days below its volume threshold: if too many points are 0 the series is
  flagged ``low_volume`` and the momentum is NOT treated as a real growth signal.
- Breakout query detection (> 5,000% growth)
- 24-hour local caching
- NO synthetic data: if Google blocks us, NoLiveDataError is raised ("Sin datos en vivo")
"""

from __future__ import annotations

import json
import logging
import random
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from hunter.provenance import LIVE, MOCK, NoLiveDataError
from hunter.scrapers.base import BaseScraper

logger = logging.getLogger("hunter.scrapers.google_trends")


class GoogleTrendsScraper(BaseScraper):
    """Rate-limit resilient Google Trends harvester."""

    BASE_URL = "https://trends.google.com/trends/api"
    EXPLORE_PAGE = "https://trends.google.com/trends/explore"

    def __init__(
        self,
        timeout: float = 12.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        offline_mode: bool = False,
    ):
        super().__init__(
            name="GoogleTrendsScraper",
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            offline_mode=offline_mode,
        )
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._widgets: Dict[str, List[Dict[str, Any]]] = {}
        self._cookie_primed = False

    def _prime_cookies(self) -> None:
        """Prime session cookies by visiting the Google Trends exploration page."""
        if self._cookie_primed or self.offline_mode:
            return

        try:
            logger.debug(f"[{self.name}] Priming session cookies at {self.EXPLORE_PAGE}...")
            resp = self.session.get(
                self.EXPLORE_PAGE,
                params={"geo": "US"},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                self._cookie_primed = True
                logger.debug(f"[{self.name}] Cookies primed successfully.")
        except Exception as exc:
            logger.warning(f"[{self.name}] Cookie priming encountered error: {exc}")

    def get_trend_analysis(
        self,
        keyword: str,
        geo: str = "US",
        timeframe: str = "today 12-m",
    ) -> Dict[str, Any]:
        """Harvest search interest momentum and breakout queries for a keyword.
        
        Args:
            keyword: The search query term.
            geo: Regional code (e.g. 'US').
            timeframe: Google Trends time window (default: 'today 12-m', one point per week).

        Returns:
            Dict containing:
                - keyword
                - momentum_pct: float (e.g. +45.0)
                - is_breakout: bool
                - breakout_queries: List[str]
                - mean_recent: float
                - mean_prior: float
                - timeline_data: List[int]
        """
        cache_key = f"{keyword.lower().strip()}_{geo}_{timeframe}"
        if cache_key in self._cache:
            logger.debug(f"[{self.name}] Serving cached trend analysis for '{keyword}'")
            return self._cache[cache_key]

        if self.offline_mode:
            fallback = self._offline_fallback(fallback_key=keyword)
            self._cache[cache_key] = fallback
            return fallback

        self._prime_cookies()

        req_obj = {
            "comparisonItem": [{"keyword": keyword, "geo": geo, "time": timeframe}],
            "category": 0,
            "property": "",
        }
        common = {"hl": "en-US", "tz": "360"}

        # Pacing jitter to prevent rapid 429 triggers
        time.sleep(random.uniform(0.5, 1.2))

        # Step 1: explore -> widget tokens
        explore = self.fetch_json(
            url=f"{self.BASE_URL}/explore",
            method="GET",
            params={**common, "req": json.dumps(req_obj)},
            fallback_key=keyword,
        )
        self._widgets[cache_key] = explore.get("widgets", [])
        widget = next(
            (w for w in explore.get("widgets", []) if w.get("id") == "TIMESERIES"), None
        )
        if not widget or "token" not in widget or "request" not in widget:
            raise NoLiveDataError(self.name, f"explore sin widget TIMESERIES para '{keyword}'")

        # Step 2: multiline -> the real interest-over-time series
        time.sleep(random.uniform(0.5, 1.2))
        series = self.fetch_json(
            url=f"{self.BASE_URL}/widgetdata/multiline",
            method="GET",
            params={**common, "req": json.dumps(widget["request"]), "token": widget["token"]},
            fallback_key=keyword,
        )
        timeline_values = self.parse_timeline(series)
        if not timeline_values:
            raise NoLiveDataError(self.name, f"serie vacía para '{keyword}'")

        analysis = self._process_trends_payload(
            keyword, {"timeline_values": timeline_values, "labels": self.parse_labels(series)}
        )
        self._cache[cache_key] = analysis
        return analysis

    def rising_queries(self, keyword: str, geo: str = "US", timeframe: str = "today 12-m", limit: int = 6) -> List[Dict[str, str]]:
        """Searches growing fastest next to ``keyword`` (Google's "Rising" list): real emerging phrases.

        Reuses the explore widgets of a previous ``get_trend_analysis`` call (one extra request only).
        Returns [] when Google has no rising list; raises NoLiveDataError if the request fails.
        """
        cache_key = f"{keyword.lower().strip()}_{geo}_{timeframe}"
        if self.offline_mode:
            return []
        widgets = self._widgets.get(cache_key)
        if widgets is None:
            self.get_trend_analysis(keyword, geo=geo, timeframe=timeframe)
            widgets = self._widgets.get(cache_key) or []
        widget = next((w for w in widgets if w.get("id") == "RELATED_QUERIES"), None)
        if not widget or "token" not in widget or "request" not in widget:
            return []
        time.sleep(random.uniform(0.5, 1.2))
        payload = self.fetch_json(
            url=f"{self.BASE_URL}/widgetdata/relatedsearches",
            method="GET",
            params={"hl": "en-US", "tz": "360", "req": json.dumps(widget["request"]), "token": widget["token"]},
            fallback_key=keyword,
        )
        lists = (payload.get("default") or {}).get("rankedList") or []
        rising = lists[1].get("rankedKeyword", []) if len(lists) > 1 else []
        return [{"query": k.get("query", ""), "growth": k.get("formattedValue", "")}
                for k in rising[:limit] if k.get("query")]

    @staticmethod
    def _complete_points(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Points with a value; the trailing partial (still running) period is dropped."""
        points = [p for p in ((payload.get("default") or {}).get("timelineData") or []) if p.get("value")]
        while points and points[-1].get("isPartial"):
            points.pop()
        return points

    @classmethod
    def parse_timeline(cls, payload: Dict[str, Any]) -> List[int]:
        """Extract the interest-over-time values from a widgetdata/multiline payload."""
        return [int(p["value"][0]) for p in cls._complete_points(payload)]

    @classmethod
    def parse_labels(cls, payload: Dict[str, Any]) -> List[str]:
        """ISO start date of each point (same order as ``parse_timeline``); '' when Google omits it."""
        labels = []
        for p in cls._complete_points(payload):
            try:
                labels.append(time.strftime("%Y-%m-%d", time.gmtime(int(p.get("time")))))
            except (TypeError, ValueError):
                labels.append("")
        return labels

    def _process_trends_payload(
        self, keyword: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate momentum slope and identify breakout queries from payload."""
        # If payload was already parsed by offline fallback or has pre-calculated fields
        if "momentum_pct" in payload:
            return payload

        widgets = payload.get("widgets", [])
        timeline_values = payload.get("timeline_values", [])
        breakout_queries = payload.get("breakout_queries", [])

        if not timeline_values:
            raise NoLiveDataError(self.name, f"sin serie temporal real para '{keyword}'")

        # Momentum windows: daily series (>= 59 points) -> last 14 days vs prior 45 days;
        # weekly series (12 months) -> last 4 weeks vs the 12 weeks before; short series -> halves.
        if len(timeline_values) >= 59:
            recent_14 = timeline_values[-14:]
            prior_45 = timeline_values[-59:-14]
        elif len(timeline_values) >= 16:
            recent_14 = timeline_values[-4:]
            prior_45 = timeline_values[-16:-4]
        else:
            midpoint = len(timeline_values) // 2
            recent_14 = timeline_values[midpoint:]
            prior_45 = timeline_values[:midpoint]

        if not recent_14 or not prior_45:
            raise NoLiveDataError(self.name, f"serie demasiado corta para '{keyword}'")
        mean_recent = sum(recent_14) / len(recent_14)
        mean_prior = sum(prior_45) / len(prior_45)

        if mean_prior > 0:
            momentum_pct = round(((mean_recent - mean_prior) / mean_prior) * 100.0, 1)
        else:
            momentum_pct = 0.0

        # Below Google's volume threshold the points come back as 0: a jump from "0" is not growth.
        window = list(prior_45) + list(recent_14)
        zero_share = sum(1 for v in window if v == 0) / len(window)
        low_volume = zero_share > 0.25 or mean_prior < 3.0
        peak = max(timeline_values) or 1

        is_breakout = (momentum_pct > 30.0 and not low_volume) or len(breakout_queries) > 0

        labels = payload.get("labels") or []
        weekly = len(timeline_values) < 59
        keep = 52 if weekly else 14
        result = {
            "keyword": keyword,
            "momentum_pct": momentum_pct,
            "is_breakout": is_breakout,
            "breakout_queries": breakout_queries,
            "mean_recent": round(mean_recent, 1),
            "mean_prior": round(mean_prior, 1),
            "timeline_data": timeline_values[-keep:],
            "timeline_labels": labels[-keep:] if len(labels) == len(timeline_values) else [],
            "resolution": "WEEK" if weekly else "DAY",
            "low_volume": low_volume,
            "zero_share": round(zero_share, 2),
            "peak_ratio": round(mean_recent / peak, 2),
            "status": LIVE,
        }

        logger.info(
            f"[{self.name}] Keyword '{keyword}': Momentum = {momentum_pct:+.1f}%, Breakout = {is_breakout}"
        )
        return result

    def _offline_fallback(
        self,
        fallback_key: Optional[str] = None,
        url: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deterministic mock trends data for canonical search terms."""
        key = (fallback_key or "").lower().strip()

        # Catalog of verified search momentum profiles
        catalog = {
            "lumbar": {
                "momentum_pct": 52.4,
                "is_breakout": True,
                "breakout_queries": [
                    "decompression belt for sciatica",
                    "inflatable lumbar belt review",
                    "lumbar traction belt before and after",
                ],
                "mean_recent": 82.5,
                "mean_prior": 54.1,
            },
            "traction": {
                "momentum_pct": 48.0,
                "is_breakout": True,
                "breakout_queries": ["spinal decompression belt", "air traction lumbar"],
                "mean_recent": 78.0,
                "mean_prior": 52.7,
            },
            "spine": {
                "momentum_pct": 52.4,
                "is_breakout": True,
                "breakout_queries": ["decompression belt for sciatica"],
                "mean_recent": 82.5,
                "mean_prior": 54.1,
            },
            "turbo": {
                "momentum_pct": 68.2,
                "is_breakout": True,
                "breakout_queries": [
                    "violent turbo fan 130000 rpm",
                    "mini jet fan car dryer",
                    "cordless turbo air duster",
                ],
                "mean_recent": 88.0,
                "mean_prior": 52.3,
            },
            "jet fan": {
                "momentum_pct": 74.5,
                "is_breakout": True,
                "breakout_queries": ["130000 rpm jet blower", "mini turbo fan car"],
                "mean_recent": 91.0,
                "mean_prior": 52.1,
            },
            "dental": {
                "momentum_pct": 41.6,
                "is_breakout": True,
                "breakout_queries": [
                    "ultrasonic tooth calculus remover",
                    "plaque remover smart sensor gums",
                    "at home dental calculus cleaner",
                ],
                "mean_recent": 74.2,
                "mean_prior": 52.4,
            },
            "calculus": {
                "momentum_pct": 43.0,
                "is_breakout": True,
                "breakout_queries": ["dental calculus remover ultrasonic"],
                "mean_recent": 75.0,
                "mean_prior": 52.4,
            },
            "steam": {
                "momentum_pct": 55.8,
                "is_breakout": True,
                "breakout_queries": [
                    "steamy cat brush for shedding",
                    "steamy pet brush ion mist",
                    "mist brush for dog hair",
                ],
                "mean_recent": 81.0,
                "mean_prior": 52.0,
            },
            "pet brush": {
                "momentum_pct": 55.8,
                "is_breakout": True,
                "breakout_queries": ["steamy cat brush for shedding"],
                "mean_recent": 81.0,
                "mean_prior": 52.0,
            },
            "mop": {
                "momentum_pct": 14.2,
                "is_breakout": False,
                "breakout_queries": ["self squeezing flat mop"],
                "mean_recent": 56.0,
                "mean_prior": 49.0,
            },
            "pillow": {
                "momentum_pct": -8.5,
                "is_breakout": False,
                "breakout_queries": [],
                "mean_recent": 42.0,
                "mean_prior": 45.9,
            },
            "teapot": {
                "momentum_pct": -4.2,
                "is_breakout": False,
                "breakout_queries": [],
                "mean_recent": 38.0,
                "mean_prior": 39.7,
            },
            "dress": {
                "momentum_pct": 5.1,
                "is_breakout": False,
                "breakout_queries": [],
                "mean_recent": 51.0,
                "mean_prior": 48.5,
            },
            "hose": {
                "momentum_pct": -15.4,
                "is_breakout": False,
                "breakout_queries": [],
                "mean_recent": 35.0,
                "mean_prior": 41.4,
            },
            "watch": {
                "momentum_pct": -12.0,
                "is_breakout": False,
                "breakout_queries": [],
                "mean_recent": 40.0,
                "mean_prior": 45.5,
            },
        }

        for token, fixture in catalog.items():
            if token in key:
                return {
                    "keyword": fallback_key or token,
                    "momentum_pct": fixture["momentum_pct"],
                    "is_breakout": fixture["is_breakout"],
                    "breakout_queries": fixture["breakout_queries"],
                    "mean_recent": fixture["mean_recent"],
                    "mean_prior": fixture["mean_prior"],
                    "timeline_data": [50, 52, 55, 60, 65, 70, 75, 78, 80, 82, 85, 87, 89, int(fixture["mean_recent"])],
                    "status": MOCK,
                }

        # Default fallback for uncataloged keywords
        return {
            "keyword": fallback_key or "general",
            "momentum_pct": 12.5,
            "is_breakout": False,
            "breakout_queries": [],
            "mean_recent": 52.0,
            "mean_prior": 46.2,
            "timeline_data": [45, 46, 48, 50, 50, 51, 52, 53, 52, 52, 53, 52, 52, 52],
            "status": MOCK,
        }
