"""
E2E Test Suite Package Initialization for dropshipping_hunter.
Sets up workspace path, imports environment, and provides fixture generators
and progressive testability hooks for all 4 test tiers.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure dropshipping_hunter is at the front of sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Windows console encoding safeguard
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


def is_module_available(module_path: str) -> bool:
    """Check if a module can be imported without raising an ImportError."""
    try:
        importlib.import_module(module_path)
        return True
    except (ImportError, ModuleNotFoundError):
        return False


# Progressive Milestone Status
HAS_MODELS = is_module_available("hunter.models")
HAS_BASE_SCRAPER = is_module_available("hunter.scrapers.base")
HAS_TIKTOK_SCRAPER = is_module_available("hunter.scrapers.tiktok_creative")
HAS_META_SCRAPER = is_module_available("hunter.scrapers.meta_ad_library")
HAS_TRENDS_SCRAPER = is_module_available("hunter.scrapers.google_trends")
HAS_ALIEXPRESS_SCRAPER = is_module_available("hunter.scrapers.aliexpress_freight")
HAS_HUNTER_ENGINE = is_module_available("hunter.hunter_engine")
HAS_AUDIT_ENGINE = is_module_available("hunter.audit_engine")
HAS_VISUALIZER = is_module_available("hunter.visualizer")
HAS_DOSSIER = is_module_available("hunter.dossier_generator")
HAS_MAIN_CLI = is_module_available("main") or os.path.isfile(os.path.join(PROJECT_ROOT, "main.py"))


# ---------------------------------------------------------------------------
# Canonical Standard Fixtures (Derived from Obsidian Manual & Spec Miner)
# ---------------------------------------------------------------------------

CANONICAL_FIXTURES: Dict[str, Dict[str, Any]] = {
    # 1. Canonical Winner 1: Ergonomic Gel Seat Cushion (SpineRelief Pro)
    "winner_spinerelief": {
        "candidate_id": "spinerelief-pro",
        "name": "SpineRelief Pro Ergonomic Gel Pad",
        "category": "Health & Ergonomics",
        "description": "High-density cellular gel seat cushion designed for immediate sciatic pressure relief.",
        "supplier_cost": 6.50,
        "shipping_cost": 4.50,
        "suggested_price": 39.99,
        "shipping_days_min": 8,
        "shipping_days_max": 11,
        "shipping_carrier": "YunExpress",
        "has_fragile_material": False,
        "has_sizing_requirements": False,
        "demo_visual_speed_sec": 1.5,
        "pain_level_score": 95.0,
        "retail_availability_score": 90.0,
        "ad_active_days": 28,
        "competitor_ad_count": 18,
        "google_trends_momentum": 42.0,
        "source_url": "https://www.aliexpress.com/item/1005006123456789.html",
        "target_demographics": {
            "primary_audience": "Long-distance drivers, desk workers, sciatica sufferers",
            "age_range": "28-60",
            "countries": ["US", "CA", "UK", "AU"],
        },
    },

    # 2. Canonical Winner 2: Electrostatic Pet Hair Removal Roller (PurePaws)
    "winner_purepaws": {
        "candidate_id": "purepaws-roller",
        "name": "PurePaws Electrostatic Hair Roller",
        "category": "Pet Care & Home",
        "description": "Self-cleaning electrostatic pet hair roller for furniture and car upholstery with zero sticky paper.",
        "supplier_cost": 3.80,
        "shipping_cost": 3.70,
        "suggested_price": 29.99,
        "shipping_days_min": 7,
        "shipping_days_max": 10,
        "shipping_carrier": "YunExpress",
        "has_fragile_material": False,
        "has_sizing_requirements": False,
        "demo_visual_speed_sec": 1.0,
        "pain_level_score": 90.0,
        "retail_availability_score": 85.0,
        "ad_active_days": 35,
        "competitor_ad_count": 22,
        "google_trends_momentum": 55.0,
        "source_url": "https://www.aliexpress.com/item/1005006234567890.html",
        "target_demographics": {
            "primary_audience": "Dog and cat owners, pet groomers, car detailers",
            "age_range": "22-55",
            "countries": ["US", "UK", "CA"],
        },
    },

    # 3. Canonical Winner 3: Ultrasonic Jewelry & Glasses Cleaner (SparkleWave)
    "winner_sparklewave": {
        "candidate_id": "sparklewave-cleaner",
        "name": "SparkleWave Ultrasonic Cleaner",
        "category": "Home Technology & Jewelry",
        "description": "45kHz ultrasonic cavitation cleaning bath removing grime from rings, watches, and glasses in 3 minutes.",
        "supplier_cost": 7.20,
        "shipping_cost": 4.80,
        "suggested_price": 44.99,
        "shipping_days_min": 8,
        "shipping_days_max": 12,
        "shipping_carrier": "YunExpress",
        "has_fragile_material": False,
        "has_sizing_requirements": False,
        "demo_visual_speed_sec": 2.0,
        "pain_level_score": 80.0,
        "retail_availability_score": 88.0,
        "ad_active_days": 24,
        "competitor_ad_count": 16,
        "google_trends_momentum": 38.0,
        "source_url": "https://www.aliexpress.com/item/1005006345678901.html",
        "target_demographics": {
            "primary_audience": "Jewelry wearers, watch collectors, eyeglass owners",
            "age_range": "25-65",
            "countries": ["US", "DE", "FR", "UK"],
        },
    },

    # 4. Disqualified: Fragile Glass Item (KO-1 Fragility)
    "disqualified_fragile_glass": {
        "candidate_id": "crystalglow-vase",
        "name": "CrystalGlow Blown Glass Ambient Vase",
        "category": "Home Decor",
        "description": "Ultra-thin handblown delicate borosilicate glass vase with led base.",
        "supplier_cost": 8.00,
        "shipping_cost": 5.00,
        "suggested_price": 45.00,
        "shipping_days_min": 9,
        "shipping_days_max": 12,
        "shipping_carrier": "YunExpress",
        "has_fragile_material": True,
        "has_sizing_requirements": False,
        "demo_visual_speed_sec": 5.0,
        "pain_level_score": 20.0,
        "retail_availability_score": 40.0,
        "ad_active_days": 12,
        "competitor_ad_count": 5,
        "google_trends_momentum": 5.0,
        "source_url": "https://www.aliexpress.com/item/1005006456789012.html",
        "target_demographics": {"primary_audience": "Interior decor enthusiasts"},
    },

    # 5. Disqualified: Millimetric Tailored Apparel (KO-1 Sizing)
    "disqualified_sizing_apparel": {
        "candidate_id": "silkelegance-dress",
        "name": "SilkElegance Tailored Evening Dress",
        "category": "Fashion & Apparel",
        "description": "Form-fitting silk evening gown requiring precise bust, waist, and hip sizing charts.",
        "supplier_cost": 15.00,
        "shipping_cost": 5.00,
        "suggested_price": 69.99,
        "shipping_days_min": 8,
        "shipping_days_max": 12,
        "shipping_carrier": "YunExpress",
        "has_fragile_material": False,
        "has_sizing_requirements": True,
        "demo_visual_speed_sec": 4.0,
        "pain_level_score": 30.0,
        "retail_availability_score": 50.0,
        "ad_active_days": 14,
        "competitor_ad_count": 8,
        "google_trends_momentum": 10.0,
        "source_url": "https://www.aliexpress.com/item/1005006567890123.html",
        "target_demographics": {"primary_audience": "Women 20-40 attending events"},
    },

    # 6. Disqualified: Insolvent Unit Economics & Retail Commodity (KO-2 & KO-4)
    "disqualified_commodity_cable": {
        "candidate_id": "cheap-usb-cable",
        "name": "Basic White USB-C Charging Cable",
        "category": "Electronics & Accessories",
        "description": "Standard 1-meter white USB charging cable available at every local convenience store.",
        "supplier_cost": 2.50,
        "shipping_cost": 2.00,
        "suggested_price": 7.99,
        "shipping_days_min": 7,
        "shipping_days_max": 12,
        "shipping_carrier": "ePacket",
        "has_fragile_material": False,
        "has_sizing_requirements": False,
        "demo_visual_speed_sec": 0.0,
        "pain_level_score": 10.0,
        "retail_availability_score": 5.0,
        "ad_active_days": 60,
        "competitor_ad_count": 80,
        "google_trends_momentum": -15.0,
        "source_url": "https://www.aliexpress.com/item/1005006678901234.html",
        "target_demographics": {"primary_audience": "General public"},
    },

    # 7. Disqualified: 35-Day Untracked Ocean Shipping (KO-3 Logistics)
    "disqualified_slow_shipping": {
        "candidate_id": "oceanbreeze-fan",
        "name": "OceanBreeze Heavy Metal Pedestal Fan",
        "category": "Home Appliances",
        "description": "Heavy industrial metal stand fan shipped via economy sea freight.",
        "supplier_cost": 18.00,
        "shipping_cost": 7.00,
        "suggested_price": 79.99,
        "shipping_days_min": 28,
        "shipping_days_max": 45,
        "shipping_carrier": "China Post Surface Mail (Untracked)",
        "has_fragile_material": False,
        "has_sizing_requirements": False,
        "demo_visual_speed_sec": 3.0,
        "pain_level_score": 60.0,
        "retail_availability_score": 60.0,
        "ad_active_days": 18,
        "competitor_ad_count": 4,
        "google_trends_momentum": 20.0,
        "source_url": "https://www.aliexpress.com/item/1005006789012345.html",
        "target_demographics": {"primary_audience": "Workshop and warehouse operators"},
    },

    # 8. Contender: Viable Product with Marginal Ticket / Fringe Markup
    "contender_mini_heater": {
        "candidate_id": "compact-nano-heater",
        "name": "Compact Desktop Ceramic Space Heater",
        "category": "Seasonal & Home",
        "description": "Plug-in fast-heating ceramic heater for cold home offices.",
        "supplier_cost": 12.00,
        "shipping_cost": 6.00,
        "suggested_price": 49.99,
        "shipping_days_min": 9,
        "shipping_days_max": 14,
        "shipping_carrier": "YunExpress",
        "has_fragile_material": False,
        "has_sizing_requirements": False,
        "demo_visual_speed_sec": 2.5,
        "pain_level_score": 75.0,
        "retail_availability_score": 70.0,
        "ad_active_days": 21,
        "competitor_ad_count": 14,
        "google_trends_momentum": 25.0,
        "source_url": "https://www.aliexpress.com/item/1005006890123456.html",
        "target_demographics": {"primary_audience": "Remote workers in cold climates"},
    },
}


def get_canonical_raw_candidate(key: str) -> Dict[str, Any]:
    """Retrieve raw candidate dictionary for testing."""
    return CANONICAL_FIXTURES[key].copy()
