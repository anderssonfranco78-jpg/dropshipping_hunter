"""Radar: keeps looking for the NEXT products while the operator works the current ones.

- data/radar_ideas.json  : the universe of product ideas (operator-editable). An idea has no cost yet:
                           cost comes from DSers once the operator decides to evaluate it.
- data/radar.json        : what the robot measured for each idea (written by the robot only).

Every run measures a small batch of ideas (the ones measured longest ago first) on YouTube Shorts and
Google Trends, plus Google's "rising searches" for a few of them (real emerging product phrases).
Google rate-limits hard (HTTP 429): on the first Trends refusal the radar stops querying Google for the
rest of the run instead of hammering it, and those ideas keep their previous measurement with its date.
Nothing is estimated: an idea never measured shows "sin medir".
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from hunter.market import market_score
from hunter.provenance import LIVE, NO_LIVE_DATA, NoLiveDataError

logger = logging.getLogger("hunter.radar")

BATCH = 6          # ideas measured per run (Google Trends allows only a few dozen requests in a row)
RISING_PER_RUN = 2  # extra "rising searches" lookups per run


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())


def load_ideas(data_dir: Path) -> List[Dict[str, Any]]:
    path = Path(data_dir) / "radar_ideas.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    ideas = raw.get("ideas") if isinstance(raw, dict) else raw
    out, seen = [], set()
    for idea in ideas or []:
        if not isinstance(idea, dict) or not idea.get("id") or not idea.get("video_keyword") or idea["id"] in seen:
            continue
        seen.add(idea["id"])
        out.append(idea)
    return out


def load_state(data_dir: Path) -> Dict[str, Any]:
    path = Path(data_dir) / "radar.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) and isinstance(state.get("ideas"), dict) else {"ideas": {}}
    except (OSError, ValueError):
        return {"ideas": {}}


RADAR_TRENDS_FRESH_HOURS = 72  # a category's weekly curve barely moves in 3 days: spare Google


def run_radar(data_dir: Path, trends_scraper, youtube_scraper, batch: int = BATCH,
              rising_per_run: int = RISING_PER_RUN, google_paused: bool = False,
              trends_fn=None, rising_fn=None) -> Dict[str, Any]:
    """Measure the stalest ideas and persist data/radar.json. Never raises for a source failure.

    ``trends_fn(keyword, fresh_hours=...)`` / ``rising_fn(keyword)`` let the engine share its Google cache,
    circuit breaker and block pause with the radar (main.py passes HunterEngine._trends / .rising).
    """
    trends_fn = trends_fn or (lambda kw, fresh_hours=None: trends_scraper.get_trend_analysis(kw))
    rising_fn = rising_fn or trends_scraper.rising_queries
    ideas = load_ideas(data_dir)
    state = load_state(data_dir)
    measured = state["ideas"]
    order = sorted(ideas, key=lambda i: (measured.get(i["id"]) or {}).get("measured_at") or "")
    google_ok = not google_paused
    rising_left = rising_per_run
    for idea in order[:batch]:
        iid = idea["id"]
        entry: Dict[str, Any] = dict(measured.get(iid) or {})
        try:
            entry["youtube"] = youtube_scraper.measure(idea["video_keyword"])
            entry["youtube_status"] = LIVE
        except NoLiveDataError as exc:
            entry["youtube_status"] = NO_LIVE_DATA
            logger.warning("[radar] %s youtube: %s", iid, exc)
        except Exception as exc:  # page format change: never fabricate
            entry["youtube_status"] = NO_LIVE_DATA
            logger.warning("[radar] %s youtube: error inesperado: %s", iid, exc)

        tk = idea.get("trends_keyword")
        if tk and google_ok:
            try:
                t = trends_fn(tk, fresh_hours=RADAR_TRENDS_FRESH_HOURS)
                entry["trends"] = {k: t.get(k) for k in ("momentum_pct", "low_volume", "peak_ratio", "mean_recent")}
                entry["trends_series"] = (t.get("timeline_data") or [])[-26:]
                entry["trends_status"] = LIVE
                entry["trends_at"] = t.get("_measured_at") or _now()
                if rising_left > 0 and not t.get("_cached"):
                    rising_left -= 1
                    entry["rising"] = rising_fn(tk)
                    entry["rising_at"] = _now()
            except NoLiveDataError as exc:
                if not entry.get("trends"):  # an older real measurement stays visible with its date
                    entry["trends_status"] = NO_LIVE_DATA
                google_ok = "429" not in str(exc) and "bloque" not in str(exc)  # leave Google alone this run
                logger.warning("[radar] %s trends: %s", iid, exc)
            except Exception as exc:
                entry["trends_status"] = NO_LIVE_DATA
                logger.warning("[radar] %s trends: error inesperado: %s", iid, exc)
        elif tk and not entry.get("trends"):
            entry["trends_status"] = NO_LIVE_DATA  # never measured; an older measurement keeps its status

        entry["market"] = market_score(entry.get("youtube") if entry.get("youtube_status") == LIVE else None,
                                       entry.get("trends") if entry.get("trends_status") == LIVE else None)
        entry["measured_at"] = _now()
        measured[iid] = entry

    ids = {i["id"] for i in ideas}
    state = {"updated_at": _now(), "ideas": {k: v for k, v in measured.items() if k in ids}}
    (Path(data_dir) / "radar.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return state


def radar_payload(data_dir: Path, evaluated_keywords: Optional[set] = None) -> List[Dict[str, Any]]:
    """Ideas + their last measurement for the panel, best market first; unmeasured ideas last."""
    state = load_state(data_dir)
    evaluated_keywords = {k.lower() for k in (evaluated_keywords or set())}
    rows = []
    for idea in load_ideas(data_dir):
        m = state["ideas"].get(idea["id"]) or {}
        rows.append({
            **{k: idea.get(k) for k in ("id", "name", "niche", "video_keyword", "trends_keyword", "why")},
            "measured_at": m.get("measured_at"),
            "youtube": m.get("youtube") if m.get("youtube_status") == LIVE else None,
            "youtube_status": m.get("youtube_status"),
            "trends": m.get("trends") if m.get("trends_status") == LIVE else None,
            "trends_series": m.get("trends_series") if m.get("trends_status") == LIVE else None,
            "trends_status": m.get("trends_status"),
            "trends_at": m.get("trends_at"),
            "rising": m.get("rising") or [],
            "market": m.get("market"),
            "evaluating": idea["video_keyword"].lower() in evaluated_keywords,
        })
    rows.sort(key=lambda r: (-1 if (r["market"] or {}).get("score") is None else (r["market"] or {}).get("score")),
              reverse=True)
    return rows
