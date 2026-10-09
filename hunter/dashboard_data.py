"""Builds the data files consumed by the static dashboard (index.html).

- data/data_health.json   : per-source status summary + red / yellow operational alerts
- data/dashboard_data.js  : ``window.HUNTER_DATA = {...}`` so index.html works from file://, the
                            local centinela and GitHub Pages without fetch() restrictions.

Alert policy (no alarm fatigue):
- RED    : real problems only -> KO-STOCK (< 100 units), stressed margin below the floor, a live
           source that SHOULD answer but failed (Google Trends, or the supplier when scraping was
           requested), and errors in data/user_products.json.
- YELLOW : stock verification expired (> 7 days) or never recorded.
- GREY   : retired sources (TikTok / Meta / Freight) -> UNAVAILABLE, never an alarm.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from hunter.models import AuditResult
from hunter.provenance import (
    LIVE, MANUAL, MOCK, NO_LIVE_DATA, SIGNALS, STOCK_EXPIRED, STOCK_LOW, STOCK_UNVERIFIED, UNAVAILABLE,
)
from hunter.stress import STRESSED_MARGIN_FLOOR_PCT

SIGNAL_LABELS = {
    "trends": "Google Trends",
    "tiktok": "TikTok Creative Center",
    "meta": "Meta Ad Library",
    "freight": "AliExpress Freight",
    "supplier": "Proveedor (precio + stock)",
}


def _short(name: str) -> str:
    return name.split("—")[0].strip()


def build_health(
    results: List[AuditResult], offline: bool, input_errors: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Aggregate provenance and operational alerts across audited products."""
    states = (LIVE, NO_LIVE_DATA, MANUAL, MOCK, UNAVAILABLE)
    sources: Dict[str, Dict[str, int]] = {s: {st: 0 for st in states} for s in SIGNALS}
    red: List[str] = [f"user_products.json — {e}" for e in (input_errors or [])]
    yellow: List[str] = []

    for r in results:
        c = r.candidate
        name = _short(c.name)
        for sig, state in (c.data_status or {}).items():
            if sig in sources and state in sources[sig]:
                sources[sig][state] += 1
            if state == NO_LIVE_DATA:
                red.append(f"{name}: {SIGNAL_LABELS.get(sig, sig)} — Sin datos en vivo")

        if c.stock_status == STOCK_LOW:
            red.append(f"{name}: KO-STOCK — solo {c.supplier_stock} uds en almacén (mínimo 100). Descalificado.")
        elif c.stock_status == STOCK_EXPIRED:
            yellow.append(f"{name}: stock verificado el {c.stock_verified_date} — vencido, re-verificar")
        elif c.stock_status == STOCK_UNVERIFIED:
            yellow.append(f"{name}: stock sin verificar — anota unidades y fecha")

        stressed = r.stressed or {}
        if stressed.get("below_floor") and r.tier != "DISQUALIFIED":
            red.append(
                f"{name}: margen estresado {stressed.get('stressed_margin_pct', 0):.1f}% "
                f"(< {STRESSED_MARGIN_FLOOR_PCT:.0f}%)"
            )

    return {
        "mode": MOCK if offline else "LIVE",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "sources": sources,
        "alerts_red": red,
        "alerts_yellow": yellow,
        "alerts": red + yellow,  # backwards compatible union
        "has_failures": bool(red),
        "is_mock": offline,
    }


def write_dashboard_files(
    results: List[AuditResult], data_dir: Path, offline: bool, input_errors: Optional[List[str]] = None
) -> Dict[str, Path]:
    health = build_health(results, offline, input_errors)
    health_path = data_dir / "data_health.json"
    health_path.write_text(json.dumps(health, indent=2, ensure_ascii=False), encoding="utf-8")

    payload = {
        "health": health,
        "signal_labels": SIGNAL_LABELS,
        "results": [r.to_dict() for r in results],
    }
    js_path = data_dir / "dashboard_data.js"
    js_path.write_text(
        "window.HUNTER_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8"
    )
    return {"health": health_path, "js": js_path}
