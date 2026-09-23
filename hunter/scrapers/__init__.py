"""Scrapers package for Dropshipping Winner Intelligence & Prospecting System."""

from hunter.scrapers.base import BaseScraper
from hunter.scrapers.tiktok_creative import TikTokCreativeScraper
from hunter.scrapers.meta_ad_library import MetaAdLibraryScraper
from hunter.scrapers.google_trends import GoogleTrendsScraper
from hunter.scrapers.aliexpress_freight import AliExpressFreightScraper

__all__ = [
    "BaseScraper",
    "TikTokCreativeScraper",
    "MetaAdLibraryScraper",
    "GoogleTrendsScraper",
    "AliExpressFreightScraper",
]
