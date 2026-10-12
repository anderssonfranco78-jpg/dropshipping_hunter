"""Builds the data files consumed by the static dashboard (index.html).

- data/data_health.json   : per-source status summary + red / yellow operational alerts
- data/dashboard_data.js  : ``window.HUNTER_DATA = {...}`` so index.html works from file://, the
                            local centinela and GitHub Pages without fetch() restrictions.

Alert policy (no alarm fatigue):
- RED    : real problems only -> KO-STOCK (< 100 units), stressed margin below the floor, a live
           source that SHOULD answer but failed (Google Trends, or the supplier when scraping was
           requested), and errors in data/user_products.json.
- YELLOW : YouTube Shorts could not be read this run (it can block datacenter IPs).
           Stock never recorded / older than 7 days is NOT an alert: DSers checks it at import.
- GREY   : retired sources (TikTok / Meta / Freight) -> UNAVAILABLE, never an alarm.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hunter.history import load_runs, previous_bases, product_history, save_run
from hunter.market import market_score, verdict
from hunter.models import AuditResult
from hunter.radar import load_state, radar_payload
from hunter.provenance import (
    LIVE, MANUAL, MOCK, NO_LIVE_DATA, SIGNALS, STOCK_LOW, UNAVAILABLE,
)
from hunter.stress import STRESSED_MARGIN_FLOOR_PCT

SIGNAL_LABELS = {
    "trends": "Google Trends",
    "youtube": "YouTube Shorts",
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
                (yellow if sig == "youtube" else red).append(f"{name}: {SIGNAL_LABELS.get(sig, sig)} — Sin datos en vivo")

        if c.stock_status == STOCK_LOW:
            red.append(f"{name}: KO-STOCK — solo {c.supplier_stock} uds en almacén (mínimo 100). Descalificado.")

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


BASE_ORDER = {"LANZAR": 0, "PROBAR": 1, "VIGILAR": 2, "DESCARTAR": 3}


def market_inputs(c) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Only measurements taken live in THIS run feed the market score (MOCK/failed -> None)."""
    status = c.data_status or {}
    yt = c.youtube if status.get("youtube") == LIVE else None
    tr = {"momentum_pct": c.google_trends_momentum, **(c.trends_meta or {})} if status.get("trends") == LIVE else None
    return yt, tr


def hooks_for(result: AuditResult) -> List[Dict[str, str]]:
    """The 4 scripted hooks of the dossier, reduced to what the content plan card shows."""
    try:
        from hunter.dossier_generator import DossierGenerator
        hooks = DossierGenerator().generate_hooks(result)
    except Exception:  # the panel must render even if the dossier library changes
        return []
    out = []
    for key, h in (hooks or {}).items():
        script = h.get("dialogue_script") or {}
        out.append({"type": key, "headline": h.get("headline", ""),
                    "client": script.get("client_neural2_c", ""), "creator": script.get("creator_neural2_b", "")})
    return out


def rank_results(results: List[AuditResult], data_dir: Path, offline: bool, generated_at: str) -> List[Dict[str, Any]]:
    """Results as dicts + market score, verdict, overall score, rank, ▲▼ vs last run and history.

    Order (trader-style asset list): verdict (LANZAR, PROBAR, VIGILAR, DESCARTAR), then overall score
    (half product rules, half market), then product score.
    """
    runs = load_runs(data_dir)
    rows = []
    for r in results:
        c = r.candidate
        cid = c.candidate_id
        market = market_score(*market_inputs(c))
        decision = verdict(r.tier, market["score"], c.in_store, previous_bases(runs, cid))
        overall = (round(0.5 * r.composite_score + 0.5 * market["score"])
                   if market["score"] is not None and r.tier != "DISQUALIFIED" else None)
        row = r.to_dict()
        row.update({"market": market, "verdict": decision, "overall": overall, "hooks": hooks_for(r)})
        rows.append(row)
    rows.sort(key=lambda x: (BASE_ORDER.get(x["verdict"]["base"], 9),
                             -(x["overall"] if x["overall"] is not None else -1),
                             -(x.get("composite_score") or 0)))
    last = runs[0]["products"] if runs else {}
    for i, row in enumerate(rows, 1):
        cid = row["candidate"]["candidate_id"]
        row["rank"] = i
        row["rank_prev"] = (last.get(cid) or {}).get("rank")
        row["history"] = product_history(runs, cid)
    if not offline:  # MOCK runs never enter the real history
        save_run(data_dir, generated_at, {
            row["candidate"]["candidate_id"]: {
                "rank": row["rank"], "base": row["verdict"]["base"], "code": row["verdict"]["code"],
                "score": row.get("composite_score"), "market": row["market"]["score"], "overall": row["overall"],
                "profit": (row.get("stressed") or {}).get("stressed_profit"), "tier": row.get("tier"),
            } for row in rows
        })
        for row in rows:  # include this run in the sparkline
            row["history"] = (row["history"] + [{"t": generated_at, "overall": row["overall"],
                                                 "market": row["market"]["score"], "score": row.get("composite_score"),
                                                 "base": row["verdict"]["base"], "rank": row["rank"]}])[-30:]
    return rows


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    count = lambda key, val: sum(1 for r in rows if r["verdict"][key] == val)
    return {
        "total": len(rows),
        "launch": count("base", "LANZAR"), "try": count("base", "PROBAR"),
        "watch": count("base", "VIGILAR"), "discard": count("base", "DESCARTAR"),
        "in_store": sum(1 for r in rows if r["candidate"].get("in_store")),
        "retire": count("code", "RETIRAR"),
    }


def write_dashboard_files(
    results: List[AuditResult], data_dir: Path, offline: bool, input_errors: Optional[List[str]] = None
) -> Dict[str, Path]:
    health = build_health(results, offline, input_errors)
    health_path = data_dir / "data_health.json"
    health_path.write_text(json.dumps(health, indent=2, ensure_ascii=False), encoding="utf-8")

    rows = rank_results(results, data_dir, offline, health["generated_at"])
    evaluated = {r.candidate.video_keyword or r.candidate.trends_keyword or "" for r in results} - {""}
    radar = radar_payload(data_dir, evaluated)
    payload = {
        "health": health,
        "signal_labels": SIGNAL_LABELS,
        "results": rows,
        "summary": summarize(rows),
        "radar": radar,
        "radar_updated_at": load_state(data_dir).get("updated_at"),
        "runs": len(load_runs(data_dir)),
    }
    js_path = data_dir / "dashboard_data.js"
    js_path.write_text(
        "window.HUNTER_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8"
    )
    return {"health": health_path, "js": js_path}
