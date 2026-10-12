"""Market score (is anyone interested *now*?) and the final, plain-language verdict per product.

The 7 Golden Rules score the PRODUCT (economics, WOW, pain, logistics). They say nothing about whether
people in the US want it right now. This module adds the MARKET side from real measurements only:

- Video interest (YouTube Shorts, the operator's own channel type): median views of the 10 most viewed
  Shorts for the product. Log scale: 1K -> 30, 10K -> 55, 100K -> 80, 1M+ -> 100.
- Crowding: Shorts above 1M views. Many mega-videos = big players already own the topic.
- Google Trends (weekly, 12 months): last 4 weeks vs the 12 before. Ignored when Google's volume is too
  low to measure (niche gadgets are found in short video, not on Google).

Verdict (what to do with the product), shown in the panel:
    LANZAR      product passes the 7 rules (WINNER) and the market score is >= 65
    PROBAR      WINNER with a medium market (45-64), or CONTENDER with a strong market (>= 65)
    VIGILAR     everything else that is not disqualified (weak/unknown market, or conditional product)
    DESCARTAR   disqualified by the rules / KO gates
For products the operator already sells (``in_store``):
    RETIRAR     DESCARTAR now, or VIGILAR in each of the last RETIRE_AFTER_RUNS measured runs
    MANTENER    otherwise
No measurement -> no market score (None) -> never LANZAR on a guess.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

LAUNCH_AT = 65
TRY_AT = 45
RETIRE_AFTER_RUNS = 3

VERDICTS = ("LANZAR", "PROBAR", "VIGILAR", "DESCARTAR", "MANTENER", "RETIRAR")


def _fmt_views(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def video_score(youtube: Optional[Dict[str, Any]]) -> Optional[int]:
    if not youtube or youtube.get("median_views_top10") is None:
        return None
    v = max(1, int(youtube["median_views_top10"]))
    return int(max(0, min(100, round(25 * math.log10(v) - 45))))


def crowding(youtube: Optional[Dict[str, Any]]) -> Optional[str]:
    if not youtube or youtube.get("over_1m") is None:
        return None
    n = youtube["over_1m"]
    return "alta" if n >= 4 else "media" if n >= 2 else "baja"


def trend_score(trends: Optional[Dict[str, Any]]) -> Optional[int]:
    """None when Google has no usable volume for the keyword (not a failure: it is just not searched)."""
    if not trends or trends.get("low_volume") or trends.get("momentum_pct") is None:
        return None
    m = trends["momentum_pct"]
    if m >= 25:
        return 100
    if m >= 10:
        return 85
    if m >= -10:
        return 65
    if m >= -25:
        return 40
    return 20


def market_score(youtube: Optional[Dict[str, Any]], trends: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Combine the live signals. Every reason is a sentence the operator can read as-is."""
    vs, ts, crowd = video_score(youtube), trend_score(trends), crowding(youtube)
    reasons: List[str] = []
    if vs is not None:
        reasons.append(
            f"Shorts: los 10 más vistos tienen una mediana de {_fmt_views(youtube['median_views_top10'])} vistas "
            f"(el mayor, {_fmt_views(youtube['max_views'])})"
        )
        reasons.append({
            "alta": f"Competencia alta: {youtube['over_1m']} Shorts pasan el millón de vistas",
            "media": f"Competencia media: {youtube['over_1m']} Shorts pasan el millón de vistas",
            "baja": "Competencia baja: casi nadie pasa el millón de vistas todavía",
        }[crowd])
    else:
        reasons.append("Shorts: sin datos en vivo en esta corrida")
    if ts is not None:
        m = trends["momentum_pct"]
        when = f" (medido el {trends['measured_at']}: hoy Google pidió una pausa)" if trends.get("measured_at") else ""
        reasons.append(f"Google (EE. UU.): {'sube' if m > 10 else 'baja' if m < -10 else 'estable'} "
                       f"{m:+.0f}% en las últimas 4 semanas vs las 12 anteriores{when}")
    elif trends and trends.get("low_volume"):
        reasons.append("Google: casi no se busca por nombre (normal en gadgets que se descubren en video)")
    else:
        reasons.append("Google: sin datos en vivo en esta corrida")

    if vs is None and ts is None:
        score = None
    else:
        penalty = {"alta": 15, "media": 5}.get(crowd or "", 0)
        base = vs if ts is None else ts if vs is None else 0.6 * vs + 0.4 * ts
        score = int(max(0, min(100, round(base - penalty))))
    return {
        "score": score,
        "video_score": vs,
        "trend_score": ts,
        "crowding": crowd,
        "partial": score is not None and (vs is None or ts is None),
        "reasons": reasons,
    }


def verdict(tier: str, score: Optional[int], in_store: bool = False,
            recent_verdicts: Optional[List[str]] = None) -> Dict[str, str]:
    """Final call. ``recent_verdicts`` = previous runs' base verdicts, newest first (for RETIRAR)."""
    if tier == "DISQUALIFIED":
        base, why = "DESCARTAR", "No pasa las reglas del producto (margen, logística, fragilidad o WOW)"
    elif score is None:
        base, why = "VIGILAR", "Sin datos de mercado en esta corrida: no se recomienda lanzar a ciegas"
    elif tier == "WINNER" and score >= LAUNCH_AT:
        base, why = "LANZAR", "Producto ganador y la gente ya mira y busca este tipo de producto"
    elif (tier == "WINNER" and score >= TRY_AT) or (tier == "CONTENDER" and score >= LAUNCH_AT):
        base, why = "PROBAR", "Buen candidato: lánzalo con pocos videos y mide la respuesta"
    else:
        base, why = "VIGILAR", "El mercado todavía no responde lo suficiente"

    if not in_store:
        return {"code": base, "base": base, "why": why}
    history = [base] + list(recent_verdicts or [])
    if base == "DESCARTAR" or (len(history) >= RETIRE_AFTER_RUNS
                               and all(v in ("VIGILAR", "DESCARTAR") for v in history[:RETIRE_AFTER_RUNS])):
        return {"code": "RETIRAR", "base": base,
                "why": "Está en tu tienda pero sus números ya no son buenos: quítalo (puede volver si sube)"}
    if base == "VIGILAR":
        left = RETIRE_AFTER_RUNS - next((i for i, v in enumerate(history) if v not in ("VIGILAR", "DESCARTAR")), len(history))
        return {"code": "MANTENER", "base": base,
                "why": f"Está en tu tienda pero se enfrió: si sigue así {left} corrida(s) más, toca retirarlo"}
    return {"code": "MANTENER", "base": base, "why": "Está en tu tienda y sigue rindiendo: " + why[0].lower() + why[1:]}
