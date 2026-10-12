"""YouTube Shorts demand probe: how much short-form video about a product is watched in the US.

The operator publishes organic YouTube Shorts / Instagram Reels / Facebook Reels, so the most relevant
"is anyone interested?" signal is what already happens in short video. This module reads YouTube's
public search page (no API key, no browser) and measures, for a product keyword:

- shorts_found      : Shorts returned by two merged searches (YouTube caps each page: it is a sample)
- median_views_top10: median views of the 10 most viewed Shorts  -> proven interest
- over_100k / over_1m: how many Shorts passed 100K / 1M views   -> crowding (big players)
- top               : the 5 most viewed Shorts (title, views, url) so the operator can study the hooks

Honesty contract: if YouTube blocks, changes its page or returns nothing, NoLiveDataError is raised
and the signal is shown as "Sin datos en vivo". Nothing is estimated or filled in.
"""

from __future__ import annotations

import json
import logging
import random
import re
import statistics
import time
from typing import Any, Dict, List, Optional

import requests

from hunter.provenance import LIVE, NoLiveDataError

logger = logging.getLogger("hunter.scrapers.youtube_shorts")

SEARCH_URL = "https://www.youtube.com/results"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
# Skip the EU/consent interstitial and ask for the US catalogue.
COOKIES = {"CONSENT": "YES+1", "SOCS": "CAI", "PREF": "gl=US&hl=en"}
_INITIAL_DATA = re.compile(r"var ytInitialData = (\{.*?\});</script>", re.S)
_VIEWS = re.compile(r"([\d.,]+)\s*([KMB]?)\s+views?", re.I)


def parse_views(text: Optional[str]) -> Optional[int]:
    """'68K views' -> 68000, '1.2M views' -> 1200000, '2,306 views' -> 2306, 'No views' -> 0."""
    if not text:
        return None
    if text.strip().lower().startswith("no views"):
        return 0
    m = _VIEWS.search(text)
    if not m:
        return None
    number = float(m.group(1).replace(",", ""))
    return int(round(number * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2).upper()]))


def extract_shorts(initial_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every Short in a search page, in page order, de-duplicated by video id."""
    found: List[Dict[str, Any]] = []
    seen = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            short = node.get("shortsLockupViewModel")
            if isinstance(short, dict):
                meta = short.get("overlayMetadata") or {}
                title = (meta.get("primaryText") or {}).get("content")
                views = parse_views((meta.get("secondaryText") or {}).get("content"))
                vid = (((short.get("onTap") or {}).get("innertubeCommand") or {})
                       .get("reelWatchEndpoint") or {}).get("videoId")
                if title and views is not None and vid and vid not in seen:
                    seen.add(vid)
                    found.append({"title": title, "views": views, "url": f"https://www.youtube.com/shorts/{vid}"})
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(initial_data)
    return found


def summarize(keyword: str, shorts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Turn the raw Shorts list into the demand metrics the panel and the market score use."""
    if not shorts:
        raise NoLiveDataError("YouTubeShorts", f"YouTube no devolvió Shorts para '{keyword}'")
    ranked = sorted(shorts, key=lambda s: s["views"], reverse=True)
    top10 = [s["views"] for s in ranked[:10]]
    return {
        "keyword": keyword,
        "shorts_found": len(shorts),
        "median_views_top10": int(statistics.median(top10)),
        "max_views": ranked[0]["views"],
        "over_100k": sum(1 for s in shorts if s["views"] >= 100_000),
        "over_1m": sum(1 for s in shorts if s["views"] >= 1_000_000),
        "top": ranked[:5],
        "status": LIVE,
    }


class YouTubeShortsScraper:
    """Reads the public YouTube search page. One request per keyword, cached for the run."""

    def __init__(self, timeout: float = 20.0, session: Optional[requests.Session] = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _search(self, query: str) -> List[Dict[str, Any]]:
        time.sleep(random.uniform(0.6, 1.4))  # polite pacing between requests
        try:
            resp = self.session.get(
                SEARCH_URL, params={"search_query": query, "gl": "US", "hl": "en"},
                headers=HEADERS, cookies=COOKIES, timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise NoLiveDataError("YouTubeShorts", f"sin conexión con YouTube: {exc}") from exc
        if resp.status_code != 200:
            raise NoLiveDataError("YouTubeShorts", f"YouTube respondió {resp.status_code}")
        match = _INITIAL_DATA.search(resp.text)
        if not match:
            raise NoLiveDataError("YouTubeShorts", "YouTube cambió su página o pidió verificación")
        try:
            return extract_shorts(json.loads(match.group(1)))
        except ValueError as exc:
            raise NoLiveDataError("YouTubeShorts", f"respuesta ilegible: {exc}") from exc

    def measure(self, keyword: str) -> Dict[str, Any]:
        """Two searches ("<kw> #shorts" and "<kw> shorts") merged by video id: YouTube shows a different
        sample on every request, and a bigger merged sample makes the median far more stable."""
        key = keyword.lower().strip()
        if key in self._cache:
            return self._cache[key]
        merged: Dict[str, Dict[str, Any]] = {}
        errors = []
        for query in (f"{keyword} #shorts", f"{keyword} shorts"):
            try:
                for short in self._search(query):
                    merged.setdefault(short["url"], short)
            except NoLiveDataError as exc:
                errors.append(exc)
        if not merged and errors:
            raise errors[0]
        result = summarize(keyword, list(merged.values()))
        logger.info("[YouTubeShorts] '%s': %d Shorts, mediana top10 %s vistas, %d > 1M",
                    keyword, result["shorts_found"], f"{result['median_views_top10']:,}", result["over_1m"])
        self._cache[key] = result
        return result
