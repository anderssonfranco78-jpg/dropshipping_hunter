"""Stressed unit economics: the margin that survives real-world friction.

The base financials (RawCandidate.compute_financials) are the ideal case. The stressed view adds:

    landed      = unit_cost + shipping_cost
    gateway     = SRP * 3.49% + $0.49           (PayPal standard US commercial rate)
    breakage    = REPLACEMENT_RATE * landed      (expected cost of re-shipping damaged/defective units)
    chargeback  = SRP * 1%                       (dispute reserve)
    stressed_profit = SRP - landed - gateway - breakage - chargeback

REPLACEMENT_RATE = 15% reflects the bitácora finding that 15-20% of boxes arrive dented; each
replacement costs one extra landed unit. All constants live here so they can be tuned in one place.
"""

from __future__ import annotations

from typing import Any, Dict

GATEWAY_PCT = 0.0349
GATEWAY_FIXED = 0.49
REPLACEMENT_RATE = 0.15
CHARGEBACK_RESERVE_PCT = 0.01
# Below this stressed margin the dashboard raises a red alert (the tier is not changed).
STRESSED_MARGIN_FLOOR_PCT = 50.0


def compute_stressed(srp: float, unit_cost: float, shipping_cost: float) -> Dict[str, Any]:
    """Return gross and stressed margins for one unit. Pure function, rounded to cents."""
    landed = round(unit_cost + shipping_cost, 2)
    gateway = round(srp * GATEWAY_PCT + GATEWAY_FIXED, 2)
    breakage = round(landed * REPLACEMENT_RATE, 2)
    chargeback = round(srp * CHARGEBACK_RESERVE_PCT, 2)
    gross_profit = round(srp - landed, 2)
    stressed_profit = round(srp - landed - gateway - breakage - chargeback, 2)
    pct = (lambda v: round(v / srp * 100.0, 2) if srp > 0 else 0.0)
    return {
        "srp": round(srp, 2),
        "landed_cost": landed,
        "gateway_fee": gateway,
        "breakage_buffer": breakage,
        "chargeback_reserve": chargeback,
        "gross_profit": gross_profit,
        "gross_margin_pct": pct(gross_profit),
        "stressed_profit": stressed_profit,
        "stressed_margin_pct": pct(stressed_profit),
        "below_floor": pct(stressed_profit) < STRESSED_MARGIN_FLOOR_PCT,
    }
