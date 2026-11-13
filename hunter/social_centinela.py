#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Centinela Social Multi-Cuentas (6:00 AM Daily Probe) — Dropshipping Hunter
==========================================================================
Visita y actualiza diariamente las 27 cuentas orgánicas (9 YouTube Shorts,
9 Instagram Reels, 9 Facebook Reels) enlazadas a los 9 productos ganadores
de Ralf & Co., generando `data/cuentas_metricas.json` para que
`https://anderssonfranco78-jpg.github.io/dropshipping_hunter/cuentas.html`
muestre los datos actualizados automáticamente cada día a las 6:00 AM.
"""

from __future__ import annotations

import concurrent.futures
import datetime
import json
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

CANONICAL_9_BUSINESSES: List[Dict[str, Any]] = [
    {
        "id": "steamfur-pro",
        "nombre": "SteamFur Pro™",
        "status": "activo",
        "warmup_day": 5,
        "enlace_tienda": "https://ralfandco.myshopify.com/products/steamfur-pro",
        "cluster_canales": {
            "youtube_shorts": {
                "handle": "@SteamFurPro",
                "canal_url": "https://www.youtube.com/@SteamFurPro",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "instagram_reels": {
                "handle": "@steamfurpro",
                "canal_url": "https://www.instagram.com/steamfurpro",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "facebook_reels": {
                "handle": "SteamFur Pro Official",
                "canal_url": "https://www.facebook.com/profile.php?id=61594892791830",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
        },
    },
    {
        "id": "prosmile-ultrasonic",
        "nombre": "UltraSmile Pro™",
        "status": "activo",
        "warmup_day": 5,
        "enlace_tienda": "https://ralfandco.myshopify.com/products/prosmile-ultrasonic",
        "cluster_canales": {
            "youtube_shorts": {
                "handle": "@UltraSmilePro",
                "canal_url": "https://www.youtube.com/channel/UCcdlJ3bL8cSGyB_6x_E3w8A",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "instagram_reels": {
                "handle": "@ultrasmilepro_us",
                "canal_url": "https://www.instagram.com/ultrasmilepro_us/",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "facebook_reels": {
                "handle": "UltraSmile Pro Official",
                "canal_url": "https://www.facebook.com/profile.php?id=61578028379184",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
        },
    },
    {
        "id": "spinerelief-pro",
        "nombre": "SpineRelief Pro™",
        "status": "activo",
        "warmup_day": 5,
        "enlace_tienda": "https://ralfandco.myshopify.com/products/spinerelief-pro",
        "cluster_canales": {
            "youtube_shorts": {
                "handle": "@SpineReliefPro",
                "canal_url": "https://www.youtube.com/channel/UC9H8gD_K4_E3j_x7B-v_c1w",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "instagram_reels": {
                "handle": "@spinereliefpro_us",
                "canal_url": "https://www.instagram.com/spinereliefpro_us/",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "facebook_reels": {
                "handle": "SpineRelief Pro Official",
                "canal_url": "https://www.facebook.com/profile.php?id=61586431073880",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
        },
    },
    {
        "id": "aeroforce-x3",
        "nombre": "AeroForce X3™",
        "status": "activo",
        "warmup_day": 5,
        "enlace_tienda": "https://ralfandco.myshopify.com/products/aeroforce-x3",
        "cluster_canales": {
            "youtube_shorts": {
                "handle": "@AeroForceX3",
                "canal_url": "https://www.youtube.com/channel/UCz-zB_j1I5u8R3G1tQ6iG9g",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "instagram_reels": {
                "handle": "@aeroforcex3_us",
                "canal_url": "https://www.instagram.com/aeroforcex3_us/",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "facebook_reels": {
                "handle": "AeroForce X3 Official",
                "canal_url": "https://www.facebook.com/profile.php?id=61588450750070",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
        },
    },
    {
        "id": "babyhalo-pro",
        "nombre": "BabyHalo Pro™",
        "status": "activo",
        "warmup_day": 5,
        "enlace_tienda": "https://ralfandco.myshopify.com/products/babyhalo-pro",
        "cluster_canales": {
            "youtube_shorts": {
                "handle": "@BabyHaloPro",
                "canal_url": "https://www.youtube.com/channel/UCJ-_wX1u0c6c1B5Q5aQ4X2A",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "instagram_reels": {
                "handle": "@babyhalopro_us",
                "canal_url": "https://www.instagram.com/babyhalopro_us/",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "facebook_reels": {
                "handle": "BabyHalo Pro Official",
                "canal_url": "https://www.facebook.com/profile.php?id=61587324041782",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
        },
    },
    {
        "id": "luxeweave-pro",
        "nombre": "LuxeWeave Pro™",
        "status": "activo",
        "warmup_day": 5,
        "enlace_tienda": "https://ralfandco.myshopify.com/products/luxeweave-pro",
        "cluster_canales": {
            "youtube_shorts": {
                "handle": "@LuxeWeavePro",
                "canal_url": "https://www.youtube.com/channel/UC2y-o1T-5pG4_9_2eW8o3lQ",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "instagram_reels": {
                "handle": "@luxeweavepro_us",
                "canal_url": "https://www.instagram.com/luxeweavepro_us/",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "facebook_reels": {
                "handle": "LuxeWeave Pro Official",
                "canal_url": "https://www.facebook.com/profile.php?id=61587202784880",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
        },
    },
    {
        "id": "solarfirefly-pro",
        "nombre": "SolarFirefly Pro™",
        "status": "activo",
        "warmup_day": 5,
        "enlace_tienda": "https://ralfandco.myshopify.com/products/solarfirefly-pro",
        "cluster_canales": {
            "youtube_shorts": {
                "handle": "@SolarFireflyPro",
                "canal_url": "https://www.youtube.com/channel/UCe-F2L7z4-7s5C0p-e0O7tQ",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "instagram_reels": {
                "handle": "@solarfireflypro_us",
                "canal_url": "https://www.instagram.com/solarfireflypro_us/",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "facebook_reels": {
                "handle": "SolarFirefly Pro Official",
                "canal_url": "https://www.facebook.com/profile.php?id=61587113030676",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
        },
    },
    {
        "id": "magneglide-pro",
        "nombre": "MagneGlide Pro™",
        "status": "activo",
        "warmup_day": 5,
        "enlace_tienda": "https://ralfandco.myshopify.com/products/magneglide-pro",
        "cluster_canales": {
            "youtube_shorts": {
                "handle": "@MagneGlidePro",
                "canal_url": "https://www.youtube.com/channel/UCpW1Y1d9c_o5h3p7R2A6n9Q",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "instagram_reels": {
                "handle": "@magneglidepro_us",
                "canal_url": "https://www.instagram.com/magneglidepro_us/",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "facebook_reels": {
                "handle": "MagneGlide Pro Official",
                "canal_url": "https://www.facebook.com/profile.php?id=61587113030676",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
        },
    },
    {
        "id": "rapiddice-pro",
        "nombre": "RapidDice Pro™",
        "status": "activo",
        "warmup_day": 5,
        "enlace_tienda": "https://ralfandco.myshopify.com/products/rapiddice-pro",
        "cluster_canales": {
            "youtube_shorts": {
                "handle": "@RapidDicePro",
                "canal_url": "https://www.youtube.com/channel/UC6g9A_q1u0X1t5g8V0P4r3w",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "instagram_reels": {
                "handle": "@rapiddicepro_us",
                "canal_url": "https://www.instagram.com/rapiddicepro_us/",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
            "facebook_reels": {
                "handle": "RapidDice Pro Official",
                "canal_url": "https://www.facebook.com/profile.php?id=61587091847291",
                "estado": "activo",
                "seguidores": 0,
                "reproducciones_totales": 0,
                "videos_publicados": 0,
                "ultimo_post": None,
            },
        },
    },
]


def _parse_compact_number(raw: str) -> Optional[int]:
    """Convierte cadenas como '1.2K', '450', '3,210' a entero."""
    if not raw:
        return None
    s = raw.strip().replace(",", "")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([KkMmBb])?$", s)
    if not m:
        return None
    val = float(m.group(1))
    suffix = (m.group(2) or "").upper()
    if suffix == "K":
        val *= 1_000
    elif suffix == "M":
        val *= 1_000_000
    elif suffix == "B":
        val *= 1_000_000_000
    return int(round(val))


def _http_get(url: str, timeout: float = 4.0) -> Optional[str]:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(250_000)
            return raw.decode("utf-8", errors="ignore")
    except Exception:
        return None


def probe_youtube_channel(canal_url: str, timeout: float = 4.0) -> Dict[str, Any]:
    """Sondea un canal de YouTube mediante su feed RSS oficial y/o HTML público."""
    out: Dict[str, Any] = {}
    channel_id = None
    m = re.search(r"/channel/(UC[a-zA-Z0-9_-]{16,30})", canal_url)
    if m:
        channel_id = m.group(1)
    else:
        html = _http_get(canal_url, timeout=timeout)
        if html:
            cm = re.search(r'"externalId"\s*:\s*"(UC[a-zA-Z0-9_-]{16,30})"', html)
            if cm:
                channel_id = cm.group(1)
            sub_m = re.search(
                r'"subscriberCountText"\s*:\s*\{[^}]*"simpleText"\s*:\s*"([\d.,KkMm]+)\s+subscriber',
                html,
            )
            if sub_m:
                subs = _parse_compact_number(sub_m.group(1))
                if subs is not None:
                    out["seguidores"] = subs

    if channel_id:
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        xml_text = _http_get(rss_url, timeout=timeout)
        if xml_text and "<feed" in xml_text:
            try:
                root = ET.fromstring(xml_text)
                ns = {
                    "atom": "http://www.w3.org/2005/Atom",
                    "media": "http://search.yahoo.com/mrss/",
                }
                entries = root.findall("atom:entry", ns)
                total_views = 0
                latest_pub = None
                for entry in entries:
                    pub_el = entry.find("atom:published", ns)
                    if pub_el is not None and pub_el.text and latest_pub is None:
                        latest_pub = pub_el.text.strip()[:10]
                    stats_el = entry.find(".//media:statistics", ns)
                    if stats_el is not None and stats_el.attrib.get("views"):
                        try:
                            total_views += int(stats_el.attrib["views"])
                        except ValueError:
                            pass
                out["videos_publicados"] = len(entries)
                out["reproducciones_totales"] = total_views
                if latest_pub:
                    out["ultimo_post"] = latest_pub
            except Exception:
                pass
    return out


def probe_instagram_or_facebook(canal_url: str, timeout: float = 4.0) -> Dict[str, Any]:
    """Extrae contadores públicos de metaetiquetas og:description si están disponibles."""
    out: Dict[str, Any] = {}
    html = _http_get(canal_url, timeout=timeout)
    if not html:
        return out
    m_desc = re.search(
        r'<meta\s+(?:property|name)=["\'](?:og:description|description)["\']\s+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if m_desc:
        desc = m_desc.group(1)
        f_m = re.search(r"([\d.,KkMm]+)\s+Followers", desc, re.IGNORECASE)
        p_m = re.search(r"([\d.,KkMm]+)\s+Posts", desc, re.IGNORECASE)
        if f_m:
            subs = _parse_compact_number(f_m.group(1))
            if subs is not None:
                out["seguidores"] = subs
        if p_m:
            posts = _parse_compact_number(p_m.group(1))
            if posts is not None:
                out["videos_publicados"] = posts
    return out


def probe_single_channel(platform: str, ch_data: Dict[str, Any], now_iso: str, probe_live: bool = True) -> Dict[str, Any]:
    """Actualiza un canal individual preservando sus métricas previas si el sondeo no expone más datos."""
    updated = dict(ch_data)
    updated["estado"] = "activo"
    updated["ultimo_sondeo"] = now_iso
    if not probe_live:
        return updated

    url = str(updated.get("canal_url") or "")
    if not url or not url.startswith("http"):
        return updated

    live_data: Dict[str, Any] = {}
    if platform == "youtube_shorts":
        live_data = probe_youtube_channel(url)
    elif platform in ("instagram_reels", "facebook_reels"):
        live_data = probe_instagram_or_facebook(url)

    for k in ("seguidores", "reproducciones_totales", "videos_publicados"):
        if k in live_data and isinstance(live_data[k], int):
            updated[k] = max(int(updated.get(k) or 0), live_data[k])
    if live_data.get("ultimo_post"):
        updated["ultimo_post"] = live_data["ultimo_post"]
    return updated


def compute_business_summary(biz: Dict[str, Any], now_iso: str) -> Dict[str, Any]:
    """Calcula metricas_resumen para un negocio activo a partir de sus 3 canales."""
    prev = dict(biz.get("metricas_resumen") or {})
    canales = biz.get("cluster_canales") or {}
    total_vids = sum(int((canales.get(p) or {}).get("videos_publicados") or 0) for p in ("youtube_shorts", "instagram_reels", "facebook_reels"))
    total_views = sum(int((canales.get(p) or {}).get("reproducciones_totales") or 0) for p in ("youtube_shorts", "instagram_reels", "facebook_reels"))

    videos_hoy = int(prev.get("videos_hoy") or 0)
    vistas_hoy = int(prev.get("vistas_hoy") or 0)
    vistas_7d = max(int(prev.get("vistas_ultimos_7_dias") or 0), total_views)
    clics_hoy = int(prev.get("clics_tienda_hoy") or 0)
    dias_sin = int(prev.get("dias_sin_publicar") or 0)

    if total_vids == 0 and videos_hoy == 0 and vistas_hoy == 0 and dias_sin == 0:
        score = 95.0
        status = "optimo"
    else:
        c_pts = min(35.0, round((videos_hoy / 2.0) * 35.0, 1))
        avg_daily = vistas_7d / 7.0
        if avg_daily > 50:
            ratio = vistas_hoy / avg_daily
            m_pts = 30.0 if ratio >= 1.0 else 24.0 if ratio >= 0.7 else 14.0 if ratio >= 0.35 else 5.0
        elif videos_hoy >= 2:
            m_pts = 28.0
        elif videos_hoy == 1:
            m_pts = 20.0
        else:
            m_pts = 10.0
        r_pts = 25.0 if (videos_hoy > 0 or dias_sin == 0) else 22.0 if dias_sin == 1 else 16.0 if dias_sin == 2 else 10.0
        ctr = (clics_hoy / vistas_hoy * 100.0) if vistas_hoy > 0 else float(prev.get("tasa_conversion_bio_pct") or 0.0)
        v_pts = 10.0 if ctr >= 0.8 else 7.5 if ctr >= 0.4 else 8.0 if videos_hoy > 0 else 2.5
        score = max(0.0, min(100.0, round(c_pts + m_pts + r_pts + v_pts, 1)))
        status = "optimo" if score >= 85 else "estable" if score >= 70 else "alerta" if score >= 50 else "critico"

    return {
        "videos_hoy": videos_hoy,
        "vistas_hoy": vistas_hoy,
        "clics_tienda_hoy": clics_hoy,
        "vistas_ultimos_7_dias": vistas_7d,
        "tasa_conversion_bio_pct": float(prev.get("tasa_conversion_bio_pct") or 0.0),
        "dias_sin_publicar": dias_sin,
        "account_health_score": score,
        "health_status": status,
        "alertas_activas": list(prev.get("alertas_activas") or []),
        "ultimo_sondeo": now_iso,
    }


def run_social_centinela(data_dir: str, probe_live: bool = True) -> Dict[str, Any]:
    """
    Sondea las 27 cuentas de los 9 productos activos y persiste `data/cuentas_metricas.json`.
    """
    out_path = os.path.join(data_dir, "cuentas_metricas.json")
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    existing_by_id: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for b in loaded.get("businesses", []):
                    if isinstance(b, dict) and b.get("id"):
                        existing_by_id[b["id"]] = b
        except Exception:
            pass

    businesses: List[Dict[str, Any]] = []
    for base_b in CANONICAL_9_BUSINESSES:
        bid = base_b["id"]
        prev_b = existing_by_id.get(bid, {})
        merged_b = json.loads(json.dumps(base_b))
        prev_canales = prev_b.get("cluster_canales") or {}
        for plat in ("youtube_shorts", "instagram_reels", "facebook_reels"):
            if plat in prev_canales and isinstance(prev_canales[plat], dict):
                for k in ("seguidores", "reproducciones_totales", "videos_publicados", "ultimo_post"):
                    if prev_canales[plat].get(k) not in (None, 0):
                        merged_b["cluster_canales"][plat][k] = prev_canales[plat][k]
        if prev_b.get("metricas_resumen"):
            merged_b["metricas_resumen"] = dict(prev_b["metricas_resumen"])
        if prev_b.get("historial_metricas"):
            merged_b["historial_metricas"] = list(prev_b["historial_metricas"])
        else:
            merged_b["historial_metricas"] = []
        businesses.append(merged_b)

    tasks: List[Tuple[int, str, Dict[str, Any]]] = []
    for idx, b in enumerate(businesses):
        for plat in ("youtube_shorts", "instagram_reels", "facebook_reels"):
            tasks.append((idx, plat, b["cluster_canales"][plat]))

    if probe_live:
        with concurrent.futures.ThreadPoolExecutor(max_workers=9) as pool:
            future_map = {
                pool.submit(probe_single_channel, plat, ch, now_iso, True): (idx, plat)
                for (idx, plat, ch) in tasks
            }
            for fut in concurrent.futures.as_completed(future_map):
                idx, plat = future_map[fut]
                try:
                    businesses[idx]["cluster_canales"][plat] = fut.result()
                except Exception:
                    businesses[idx]["cluster_canales"][plat]["ultimo_sondeo"] = now_iso
    else:
        for idx, plat, ch in tasks:
            businesses[idx]["cluster_canales"][plat] = probe_single_channel(plat, ch, now_iso, False)

    for b in businesses:
        b["metricas_resumen"] = compute_business_summary(b, now_iso)

    envelope = {
        "version": "2.0.0",
        "updated_at": now_iso,
        "schedule_info": "Centinela 06:00 AM El Salvador (12:00 UTC) + cada 6h",
        "total_businesses": len(businesses),
        "active_businesses": len(businesses),
        "total_channels": len(businesses) * 3,
        "active_channels": len(businesses) * 3,
        "businesses": businesses,
    }

    os.makedirs(data_dir, exist_ok=True)
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, out_path)
    return envelope
