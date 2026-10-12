"""Run history: one small JSON file per live run in data/history/.

Why one file per run: the cloud robot (GitHub Actions) and the local PC both run the Hunter and both
push to the same repository. Unique file names never conflict in git, so no run is ever lost.

Each snapshot stores, per product: final verdict, base verdict, product score (7 rules), market score,
overall score, rank and stressed profit. The panel uses it for ▲▼ rank movement, the score sparkline and
the RETIRAR rule (a product in the store that stays VIGILAR for several runs).
MOCK runs (--offline) are never written: fixtures must not pollute the real history.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

KEEP_RUNS = 120


def history_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "history"


def load_runs(data_dir: Path, limit: int = KEEP_RUNS) -> List[Dict[str, Any]]:
    """Previous runs, newest first. Unreadable files are skipped (never fatal)."""
    folder = history_dir(data_dir)
    if not folder.is_dir():
        return []
    runs = []
    for path in sorted(folder.glob("*.json"), reverse=True)[:limit]:
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(run, dict) and isinstance(run.get("products"), dict):
            runs.append(run)
    return runs


def save_run(data_dir: Path, generated_at: str, products: Dict[str, Dict[str, Any]]) -> Path:
    folder = history_dir(data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    source = "nube" if os.environ.get("GITHUB_ACTIONS") == "true" else "pc"
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = folder / f"{stamp}-{source}.json"
    path.write_text(json.dumps({"generated_at": generated_at, "source": source, "products": products},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    for old in sorted(folder.glob("*.json"), reverse=True)[KEEP_RUNS:]:
        try:
            old.unlink()
        except OSError:
            pass
    return path


def product_history(runs: List[Dict[str, Any]], product_id: str, points: int = 30) -> List[Dict[str, Any]]:
    """Oldest -> newest list of {t, overall, market, score, base, rank} for one product."""
    out = []
    for run in runs[:points]:
        p = run["products"].get(product_id)
        if p:
            out.append({"t": run.get("generated_at"), "overall": p.get("overall"), "market": p.get("market"),
                        "score": p.get("score"), "base": p.get("base"), "rank": p.get("rank")})
    return list(reversed(out))


def previous_bases(runs: List[Dict[str, Any]], product_id: str) -> List[str]:
    """Base verdicts of earlier runs, newest first (feeds market.verdict for RETIRAR)."""
    return [run["products"][product_id]["base"] for run in runs
            if product_id in run["products"] and run["products"][product_id].get("base")]
