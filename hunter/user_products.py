"""Operator-owned product inputs: data/user_products.json.

This file is the single source of truth for the products Andersson operates. The robot (local or
GitHub Actions) only READS it; nothing in the pipeline ever writes to it. Generated results go to
data/candidates.json, data/audit_results.json and data/dashboard_data.js.

Each product (see data/user_products.json for a full example):

    id, name, category, source_url, srp_usd, unit_cost_usd, shipping_cost_usd   (required)
    target_variant_name, verified_stock, verified_date (YYYY-MM-DD), notes       (stock check)
    trends_keyword                                                               (Google Trends)
    shipping {days_min, days_max, carrier}                                       (logistics)
    rule_inputs {demo_visual_speed_sec, pain_level_score, retail_availability_score,
                 has_fragile_material, has_sizing_requirements,
                 ad_active_days, competitor_ad_count, google_trends_momentum}    (7 Golden Rules)

Stock freshness: a verification older than STOCK_MAX_AGE_DAYS is EXPIRED; below MIN_STOCK is LOW.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from hunter.models import RawCandidate
from hunter.provenance import (
    MANUAL, STOCK_EXPIRED, STOCK_LOW, STOCK_OK, STOCK_UNVERIFIED, default_status,
)

MIN_STOCK = 100
STOCK_MAX_AGE_DAYS = 7

REQUIRED_FIELDS = ("id", "name", "category", "source_url", "srp_usd", "unit_cost_usd", "shipping_cost_usd")
REQUIRED_RULE_INPUTS = (
    "demo_visual_speed_sec", "pain_level_score", "retail_availability_score",
    "has_fragile_material", "has_sizing_requirements",
)


def stock_status(verified_stock: Optional[int], verified_date: Optional[str], today: Optional[date] = None) -> str:
    """Classify the operator's stock check. LOW wins over EXPIRED: thin stock blocks regardless of age."""
    if verified_stock is None or not verified_date:
        return STOCK_UNVERIFIED
    if verified_stock < MIN_STOCK:
        return STOCK_LOW
    checked = date.fromisoformat(str(verified_date))
    if ((today or date.today()) - checked).days > STOCK_MAX_AGE_DAYS:
        return STOCK_EXPIRED
    return STOCK_OK


def product_to_candidate(item: Dict[str, Any], today: Optional[date] = None) -> RawCandidate:
    """Map one user_products.json entry to a RawCandidate. Raises ValueError with a clear message."""
    missing = [f for f in REQUIRED_FIELDS if item.get(f) in (None, "")]
    rules = item.get("rule_inputs") or {}
    missing += [f"rule_inputs.{f}" for f in REQUIRED_RULE_INPUTS if f not in rules]
    if missing:
        raise ValueError(f"faltan campos: {', '.join(missing)}")

    stock = item.get("verified_stock")
    stock = int(stock) if stock is not None else None
    vdate = item.get("verified_date") or None
    try:
        status = stock_status(stock, vdate, today)
    except ValueError:
        raise ValueError(f"verified_date '{vdate}' no tiene formato AAAA-MM-DD")

    ship = item.get("shipping") or {}
    data_status = default_status()
    data_status["supplier"] = MANUAL  # cost + stock typed by the operator

    candidate = RawCandidate(
        candidate_id=str(item["id"]),
        name=str(item["name"]),
        category=str(item["category"]),
        description=str(item.get("description", "")),
        supplier_cost=float(item["unit_cost_usd"]),
        shipping_cost=float(item["shipping_cost_usd"]),
        suggested_price=float(item["srp_usd"]),
        shipping_days_min=int(ship.get("days_min", 7)),
        shipping_days_max=int(ship.get("days_max", 12)),
        shipping_carrier=str(ship.get("carrier", "AliExpress Choice")),
        has_fragile_material=bool(rules["has_fragile_material"]),
        has_sizing_requirements=bool(rules["has_sizing_requirements"]),
        demo_visual_speed_sec=float(rules["demo_visual_speed_sec"]),
        pain_level_score=float(rules["pain_level_score"]),
        retail_availability_score=float(rules["retail_availability_score"]),
        ad_active_days=int(rules.get("ad_active_days", 0)),
        competitor_ad_count=int(rules.get("competitor_ad_count", 0)),
        google_trends_momentum=float(rules.get("google_trends_momentum", 0.0)),
        source_url=str(item["source_url"]),
        target_demographics=dict(item.get("target_demographics") or {}),
        data_status=data_status,
        supplier_variant=item.get("target_variant_name"),
        supplier_stock=stock,
        stock_verified_date=vdate,
        stock_status=status,
        trends_keyword=item.get("trends_keyword"),
        notes=item.get("notes"),
    )
    errors = candidate.validate()
    if errors:
        raise ValueError("; ".join(errors))
    return candidate


def load_user_products(
    path: Union[str, Path], today: Optional[date] = None
) -> Tuple[List[RawCandidate], List[str]]:
    """Read the operator file. Returns (candidates, errors); one bad product never hides the others."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw.get("products") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError(f"{path}: se esperaba una lista 'products'")

    candidates: List[RawCandidate] = []
    errors: List[str] = []
    seen = set()
    for i, item in enumerate(items):
        label = (item or {}).get("id") or f"producto #{i + 1}"
        if label in seen:
            errors.append(f"{label}: id duplicado, se ignora la segunda entrada")
            continue
        try:
            candidates.append(product_to_candidate(item, today))
            seen.add(label)
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"{label}: {exc}")
    return candidates, errors
