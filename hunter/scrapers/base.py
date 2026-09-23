"""Base scraper class with retry logic, rate limit handling, and deterministic offline fallbacks.

Adheres strictly to the operational constraints:
- Zero Desktop GUI Control (pure headless HTTP/JSON)
- Deterministic offline fallback fixtures for air-gapped / rate-limited environments
"""

from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure module logger
logger = logging.getLogger("hunter.scrapers.base")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class BaseScraper(ABC):
    """Abstract base scraper providing robust headless HTTP requests with fallback."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        name: str,
        timeout: float = 6.0,
        max_retries: int = 2,
        backoff_factor: float = 1.0,
        offline_mode: bool = False,
    ):
        """Initialize the scraper.
        
        Args:
            name: Scraper identifier name.
            timeout: Network request timeout in seconds.
            max_retries: Maximum retry attempts for transient errors.
            backoff_factor: Multiplier for exponential backoff sleep.
            offline_mode: If True, bypasses network calls and uses deterministic fallbacks.
        """
        self.name = name
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.offline_mode = offline_mode
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create and configure a robust requests session with retries and realistic headers."""
        session = requests.Session()
        
        # Configure automatic retries on status codes 429, 500, 502, 503, 504
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "OPTIONS"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Realistic browser headers
        session.headers.update({
            "User-Agent": self.DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        })
        return session

    def fetch_json(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        fallback_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch JSON payload from an endpoint with automatic retry, backoff, and offline fallback.
        
        Args:
            url: Target URL.
            method: HTTP method ('GET' or 'POST').
            headers: Additional request headers.
            params: URL query parameters.
            json_data: JSON payload for POST.
            fallback_key: Identifier passed to _offline_fallback if network fails or offline.

        Returns:
            Dictionary containing parsed JSON data (from network or deterministic mock).
        """
        if self.offline_mode:
            logger.info(f"[{self.name}] Offline mode enabled. Using deterministic mock for key='{fallback_key}'.")
            return self._offline_fallback(fallback_key=fallback_key, url=url, params=params)

        for attempt in range(1, self.max_retries + 1):
            try:
                req_headers = dict(self.session.headers)
                if headers:
                    req_headers.update(headers)

                logger.debug(f"[{self.name}] Attempt {attempt}/{self.max_retries} -> {method} {url}")
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    headers=req_headers,
                    params=params,
                    json=json_data,
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError:
                        # Some endpoints (e.g. Google Trends) prepend security prefixes like ")]}',"
                        raw_text = response.text
                        if "{" in raw_text:
                            clean_text = raw_text[raw_text.find("{"):]
                            return requests.compat.json.loads(clean_text)
                        raise

                # Non-transient client errors: immediate fallback
                if response.status_code in (401, 403, 404):
                    logger.info(
                        f"[{self.name}] HTTP {response.status_code} received from {url}. Engaging deterministic offline fallback (key='{fallback_key}')."
                    )
                    return self._offline_fallback(fallback_key=fallback_key, url=url, params=params)

                if response.status_code == 429:
                    # Rate limited: apply exponential backoff with jitter
                    wait_time = (self.backoff_factor ** attempt) + random.uniform(0.5, 1.5)
                    logger.warning(
                        f"[{self.name}] HTTP 429 Rate Limit on {url}. Backing off for {wait_time:.2f}s..."
                    )
                    time.sleep(wait_time)
                    continue

                if response.status_code >= 500:
                    logger.warning(
                        f"[{self.name}] Server error {response.status_code} from {url} on attempt {attempt}"
                    )
                    time.sleep(self.backoff_factor * attempt)

            except (requests.RequestException, Exception) as exc:
                logger.warning(f"[{self.name}] Network error on attempt {attempt}/{self.max_retries}: {exc}")
                if attempt < self.max_retries:
                    time.sleep(self.backoff_factor * attempt)

        # All network attempts failed or timed out: fall back deterministically
        logger.info(
            f"[{self.name}] Network unavailable or blocked for {url}. Engaging deterministic offline fallback (key='{fallback_key}')."
        )
        return self._offline_fallback(fallback_key=fallback_key, url=url, params=params)

    @abstractmethod
    def _offline_fallback(
        self,
        fallback_key: Optional[str] = None,
        url: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Produce deterministic, realistic mock data conforming to the endpoint's schema.
        
        Subclasses MUST implement this method.
        """
        pass

    def health_check(self) -> Dict[str, Any]:
        """Perform a quick scraper status check."""
        return {
            "scraper": self.name,
            "offline_mode": self.offline_mode,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "status": "READY",
        }
