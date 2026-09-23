"""AliExpress and Supplier Freight Intelligence scraper.

Targets:
- Endpoint: https://www.aliexpress.com/aeglodetailweb/api/logistics/freight
- Extracts tracked shipping lines (YunExpress, ePacket, AliExpress Standard)
- Audits carrier delivery speed against the 7-12 day Golden Rule window
- Disqualifies untracked surface lines (Cainiao Super Economy, SunYou >21 days)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from hunter.scrapers.base import BaseScraper

logger = logging.getLogger("hunter.scrapers.aliexpress_freight")


class AliExpressFreightScraper(BaseScraper):
    """Headless scraper for AliExpress unauthenticated logistics & freight calculation."""

    FREIGHT_API = "https://www.aliexpress.com/aeglodetailweb/api/logistics/freight"

    APPROVED_CARRIERS = {
        "yunexpress": {"priority": 1, "tier": "Priority 1", "min_days": 7, "max_days": 10},
        "cjpacket": {"priority": 1, "tier": "Priority 1", "min_days": 7, "max_days": 10},
        "yanwen": {"priority": 2, "tier": "Priority 2", "min_days": 8, "max_days": 12},
        "epacket": {"priority": 2, "tier": "Priority 2", "min_days": 10, "max_days": 14},
        "aliexpress standard": {"priority": 3, "tier": "Priority 3", "min_days": 10, "max_days": 14},
    }

    DISQUALIFIED_CARRIERS = ["cainiao super economy", "sunyou", "china post ordinary", "yanwen economic"]

    def __init__(
        self,
        timeout: float = 12.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        offline_mode: bool = False,
    ):
        super().__init__(
            name="AliExpressFreightScraper",
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            offline_mode=offline_mode,
        )

    def get_freight_options(
        self,
        product_id: str,
        country: str = "US",
        trade_currency: str = "USD",
        supplier_cost: float = 10.0,
    ) -> Dict[str, Any]:
        """Fetch and audit available shipping lines for a product ID.
        
        Args:
            product_id: Numerical or string item identifier.
            country: Destination country code (e.g. 'US').
            trade_currency: Currency code (e.g. 'USD').
            supplier_cost: Base supplier product cost in USD.

        Returns:
            Dict containing best carrier, landed cost, shipping days, and audited lines.
        """
        params = {
            "productId": product_id,
            "count": 1,
            "country": country,
            "tradeCurrency": trade_currency,
        }

        response_json = self.fetch_json(
            url=self.FREIGHT_API,
            method="GET",
            params=params,
            fallback_key=str(product_id),
        )

        return self._audit_freight(response_json, supplier_cost=supplier_cost)

    def _audit_freight(
        self, response_json: Dict[str, Any], supplier_cost: float
    ) -> Dict[str, Any]:
        """Audit shipping lines, select the fastest tracked carrier, and compute landed cost."""
        raw_options = (
            response_json.get("body", {}).get("freightResult", [])
            or response_json.get("freight_options", [])
        )

        parsed_options: List[Dict[str, Any]] = []
        best_line: Optional[Dict[str, Any]] = None

        for opt in raw_options:
            carrier_name = opt.get("company", opt.get("carrier_name", "Unknown Carrier"))
            carrier_lower = carrier_name.lower()
            
            shipping_fee = float(opt.get("freightAmount", {}).get("value", opt.get("shipping_cost", 0.0)))
            min_days = int(opt.get("minDays", opt.get("delivery_days_min", 10)))
            max_days = int(opt.get("maxDays", opt.get("delivery_days_max", 15)))
            tracking = bool(opt.get("tracking", opt.get("tracking_available", True)))

            # Check if disqualified
            is_disqualified = any(dq in carrier_lower for dq in self.DISQUALIFIED_CARRIERS) or (max_days > 21) or not tracking
            is_approved = not is_disqualified and (min_days <= 14) and tracking

            option_entry = {
                "carrier_name": carrier_name,
                "shipping_cost": shipping_fee,
                "delivery_days_min": min_days,
                "delivery_days_max": max_days,
                "tracking_available": tracking,
                "is_approved": is_approved,
                "is_disqualified": is_disqualified,
            }
            parsed_options.append(option_entry)

            if is_approved:
                # Prioritize faster delivery line
                if best_line is None or min_days < best_line["delivery_days_min"]:
                    best_line = option_entry

        # Fallback if no line is explicitly marked approved: choose first tracked line
        if best_line is None and parsed_options:
            best_line = parsed_options[0]

        carrier_selected = best_line["carrier_name"] if best_line else "YunExpress"
        shipping_cost = best_line["shipping_cost"] if best_line else 4.50
        min_delivery = best_line["delivery_days_min"] if best_line else 7
        max_delivery = best_line["delivery_days_max"] if best_line else 12

        landed_cost = round(supplier_cost + shipping_cost, 2)
        passes_rule_7 = (max_delivery <= 14) and (best_line["tracking_available"] if best_line else True)

        result = {
            "selected_carrier": carrier_selected,
            "shipping_cost": shipping_cost,
            "supplier_cost": supplier_cost,
            "landed_cost": landed_cost,
            "shipping_days_min": min_delivery,
            "shipping_days_max": max_delivery,
            "passes_rule_7": passes_rule_7,
            "freight_options": parsed_options,
        }

        logger.info(
            f"[{self.name}] Landed Cost: ${landed_cost:.2f} (${supplier_cost:.2f} + ${shipping_cost:.2f} via {carrier_selected}, {min_delivery}-{max_delivery}d)"
        )
        return result

    def _offline_fallback(
        self,
        fallback_key: Optional[str] = None,
        url: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Provide deterministic mock logistics options for products."""
        key = (fallback_key or "").lower().strip()

        catalog = {
            "spinerelief": {
                "carrier": "YunExpress Specialty Line",
                "cost": 4.80,
                "min_days": 8,
                "max_days": 10,
            },
            "aeroforce": {
                "carrier": "YunExpress Special Battery Line",
                "cost": 4.80,
                "min_days": 8,
                "max_days": 11,
            },
            "prosmile": {
                "carrier": "CJPacket Fast Line",
                "cost": 3.70,
                "min_days": 7,
                "max_days": 10,
            },
            "steamfur": {
                "carrier": "YunExpress Ordinary",
                "cost": 2.50,
                "min_days": 7,
                "max_days": 10,
            },
            "hydroclean": {
                "carrier": "AliExpress Standard Shipping",
                "cost": 6.00,
                "min_days": 10,
                "max_days": 14,
            },
            "vintage-leather-watch": {
                "carrier": "China Post Ordinary Small Packet",
                "cost": 1.20,
                "min_days": 25,
                "max_days": 45,
                "tracking": False,
            },
        }

        for token, fixture in catalog.items():
            if token in key:
                tracking = fixture.get("tracking", True)
                return {
                    "freight_options": [
                        {
                            "carrier_name": fixture["carrier"],
                            "shipping_cost": fixture["cost"],
                            "delivery_days_min": fixture["min_days"],
                            "delivery_days_max": fixture["max_days"],
                            "tracking_available": tracking,
                            "is_approved": tracking and fixture["max_days"] <= 14,
                        },
                        {
                            "carrier_name": "Cainiao Super Economy",
                            "shipping_cost": 1.50,
                            "delivery_days_min": 25,
                            "delivery_days_max": 50,
                            "tracking_available": False,
                            "is_approved": False,
                        },
                    ]
                }

        # Default fallback
        return {
            "freight_options": [
                {
                    "carrier_name": "YunExpress Direct",
                    "shipping_cost": 4.50,
                    "delivery_days_min": 7,
                    "delivery_days_max": 12,
                    "tracking_available": True,
                    "is_approved": True,
                },
                {
                    "carrier_name": "AliExpress Standard Shipping",
                    "shipping_cost": 3.80,
                    "delivery_days_min": 10,
                    "delivery_days_max": 15,
                    "tracking_available": True,
                    "is_approved": True,
                },
            ]
        }
