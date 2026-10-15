"""Puente gratuito DSers / Shopify <-> n8n <-> Dropshipping Hunter (hunter/n8n_bridge.py).

Cómo funciona el flujo real y gratuito (2026):
1. DSers (Plan Gratuito hasta 3,000 productos) se instala desde la Shopify App Store y se vincula a
   AliExpress. Cuando el proveedor cambia stock o precio en AliExpress, DSers actualiza automáticamente
   el inventario del producto en tu tienda Shopify ("Ralf & Co.").
2. Shopify dispara gratis un Webhook nativo (`inventory_levels/update` o `products/update`) cada vez
   que DSers modifica las unidades o el precio.
3. n8n (100% gratis auto-alojado con Docker/npx en tu PC, o con límite de ejecuciones mensuales en nube)
   recibe ese Webhook o consulta Shopify de forma espaciada (ej. 1 vez cada 6-12 horas para no gastar
   cuota gratuita) y se lo envía al Hunter por:
   - Endpoint local: `POST http://127.0.0.1:8765/api/n8n/sync-stock`
   - O CLI directo: `python -m hunter.n8n_bridge --product-id steamfur-pro --stock 602`
4. Este módulo valida los datos con las mismas reglas estrictas del Hunter (`product_to_candidate`),
   actualiza `data/user_products.json` de forma atómica y devuelve si el producto cayó en `KO-STOCK`
   (< 100 unidades) o si su margen estresado bajó del piso seguro (50%).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from hunter.provenance import STOCK_LOW
from hunter.stress import compute_stressed
from hunter.user_products import MIN_STOCK, product_to_candidate, stock_status

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PRODUCTS_PATH = ROOT / "data" / "user_products.json"
DEFAULT_WORKFLOW_PATH = ROOT / "automations_n8n" / "flujo_dsers_shopify_hunter_gratis.json"
_BRIDGE_LOCK = threading.Lock()


def _today_iso() -> str:
    return dt.date.today().isoformat()


def normalize_n8n_item(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convierte un payload de n8n o un Webhook crudo de Shopify/DSers en actualizaciones normalizadas.

    Formatos soportados:
    1. Directo Hunter/n8n:
       {"id": "steamfur-pro", "verified_stock": 602, "unit_cost_usd": 4.73, "shipping_cost_usd": 3.54}
    2. Lote n8n:
       {"updates": [{"id": "steamfur-pro", "stock": 602}, ...]}
    3. Webhook Shopify `products/update` (sincronizado por DSers):
       {"handle": "steamfur-pro", "variants": [{"title": "green", "inventory_quantity": 602, "price": "29.99"}]}
    4. Webhook Shopify `inventory_levels/update` enriquecido en n8n:
       {"product_id": "steamfur-pro", "available": 602}
    """
    if not isinstance(raw, dict):
        raise ValueError("El payload de n8n debe ser un objeto JSON")

    batch_list = raw.get("updates") if isinstance(raw.get("updates"), list) else raw.get("items")
    if isinstance(batch_list, list):
        out: List[Dict[str, Any]] = []
        for entry in batch_list:
            if isinstance(entry, dict):
                out.extend(normalize_n8n_item(entry))
        return out

    # Caso Webhook Shopify `products/update` con variantes
    if isinstance(raw.get("variants"), list) and raw["variants"]:
        pid = str(raw.get("id_hunter") or raw.get("handle") or raw.get("product_slug") or "").strip()
        if not pid:
            raise ValueError("Falta 'handle' o 'id_hunter' en el webhook de producto de Shopify")
        target_var = str(raw.get("target_variant_name") or "").strip().lower()
        variants = [v for v in raw["variants"] if isinstance(v, dict)]
        chosen = variants[0]
        if target_var:
            for v in variants:
                title = str(v.get("title") or v.get("option1") or "").strip().lower()
                if target_var in title:
                    chosen = v
                    break
        stock_val = chosen.get("inventory_quantity", chosen.get("available"))
        item: Dict[str, Any] = {"id": pid, "en_tienda": True}
        if stock_val is not None:
            item["verified_stock"] = int(stock_val)
        if chosen.get("price") is not None:
            try:
                price_f = float(chosen["price"])
                if price_f > 0:
                    item["srp_usd"] = price_f
            except (TypeError, ValueError):
                pass
        if chosen.get("title") and chosen.get("title") != "Default Title":
            item["target_variant_name"] = str(chosen["title"])
        return [item]

    # Caso directo n8n / `inventory_levels/update`
    pid = str(
        raw.get("id")
        or raw.get("product_id")
        or raw.get("candidate_id")
        or raw.get("handle")
        or raw.get("shopify_handle")
        or raw.get("sku")
        or raw.get("aliexpress_item_id")
        or ""
    ).strip()
    if not pid:
        raise ValueError("Falta identificador de producto ('id', 'product_id', 'aliexpress_item_id' o 'handle')")

    normalized: Dict[str, Any] = {"id": pid}
    if raw.get("aliexpress_item_id") is not None:
        normalized["aliexpress_item_id"] = str(raw["aliexpress_item_id"]).strip()
    raw_stock = (
        raw["verified_stock"]
        if "verified_stock" in raw
        else raw.get("stock", raw.get("available", raw.get("inventory_quantity")))
    )
    if raw_stock is not None:
        stock_int = int(raw_stock)
        if stock_int < 0:
            raise ValueError("El stock no puede ser negativo")
        normalized["verified_stock"] = stock_int
        normalized["verified_date"] = str(raw.get("verified_date") or _today_iso())

    for num_field, aliases in (
        ("unit_cost_usd", ("unit_cost_usd", "supplier_cost_usd", "supplier_cost", "cost_usd")),
        ("shipping_cost_usd", ("shipping_cost_usd", "shipping_cost", "shipping_usd")),
        ("srp_usd", ("srp_usd", "retail_price_usd", "suggested_price", "price_usd")),
    ):
        for alias in aliases:
            if raw.get(alias) is not None:
                val = float(raw[alias])
                if val < 0:
                    raise ValueError(f"{num_field} no puede ser negativo")
                normalized[num_field] = val
                break

    if "en_tienda" in raw or "in_store" in raw:
        normalized["en_tienda"] = bool(raw.get("en_tienda") if "en_tienda" in raw else raw.get("in_store"))
    if raw.get("target_variant_name") is not None:
        normalized["target_variant_name"] = str(raw["target_variant_name"]).strip() or None
    if raw.get("notes") is not None:
        normalized["notes"] = str(raw["notes"]).strip()

    return [normalized]


def _resolve_product_index(pid: str, ali_id: Optional[str], items: List[Dict[str, Any]]) -> Optional[int]:
    """Busca un producto por su id exacto o por su aliexpress_item_id dentro de source_url."""
    for idx, p in enumerate(items):
        if str(p.get("id") or "").strip() == pid:
            return idx
    lookup_ali = ali_id or (pid if pid.isdigit() else None)
    if lookup_ali:
        for idx, p in enumerate(items):
            src_url = str(p.get("source_url") or "")
            if f"/item/{lookup_ali}" in src_url or str(p.get("aliexpress_item_id") or "") == lookup_ali:
                return idx
    return None


def sync_dsers_stock_payload(
    payload: Dict[str, Any],
    products_path: Optional[Union[str, Path]] = None,
    today: Optional[dt.date] = None,
) -> Dict[str, Any]:
    """Aplica actualizaciones de stock/costo provenientes de DSers/Shopify vía n8n a user_products.json."""
    target_path = Path(products_path) if products_path else DEFAULT_PRODUCTS_PATH
    if not target_path.exists():
        raise ValueError(f"No existe el archivo de productos: {target_path}")

    updates = normalize_n8n_item(payload)
    if not updates:
        raise ValueError("No se encontraron actualizaciones válidas en el payload")

    with _BRIDGE_LOCK:
        raw_doc = json.loads(target_path.read_text(encoding="utf-8"))
        items = raw_doc["products"] if isinstance(raw_doc, dict) else raw_doc
        if not isinstance(items, list):
            raise ValueError("Formato inválido en user_products.json: falta lista 'products'")

        results: List[Dict[str, Any]] = []

        for upd in updates:
            pid = upd["id"]
            ali_id = upd.get("aliexpress_item_id")
            idx = _resolve_product_index(pid, ali_id, items)
            if idx is None:
                raise ValueError(f"El producto '{pid}' no existe en user_products.json")
            merged = dict(items[idx])
            for k, v in upd.items():
                if k not in ("id", "aliexpress_item_id"):
                    merged[k] = v
            if "verified_stock" in upd and not merged.get("verified_date"):
                merged["verified_date"] = (today or dt.date.today()).isoformat()

            # Validar con las mismas reglas estrictas del robot antes de tocar el archivo
            cand = product_to_candidate(merged, today=today)
            stressed = compute_stressed(cand.suggested_price, cand.supplier_cost, cand.shipping_cost)
            st_status = stock_status(cand.supplier_stock, cand.stock_verified_date, today=today)
            ko_stock = st_status == STOCK_LOW
            landed = stressed["landed_cost"]
            markup = (cand.suggested_price / landed) if landed > 0 else 0.0
            ko_margin = bool(stressed["below_floor"])
            ko_multiplier = markup < 3.0

            items[idx] = merged
            results.append({
                "id": cand.candidate_id,
                "name": cand.name,
                "verified_stock": cand.supplier_stock,
                "verified_date": cand.stock_verified_date,
                "stock_status": st_status,
                "ko_stock": ko_stock,
                "ko_margin": ko_margin,
                "ko_multiplier": ko_multiplier,
                "min_stock_required": MIN_STOCK,
                "en_tienda": cand.in_store,
                "srp_usd": cand.suggested_price,
                "landed_cost_usd": landed,
                "stressed_profit_usd": stressed["stressed_profit"],
                "stressed_margin_pct": stressed["stressed_margin_pct"],
                "margin_below_floor": ko_margin,
                "alert": (
                    f"KO-STOCK en {cand.name}: quedan {cand.supplier_stock} uds (< {MIN_STOCK})"
                    if ko_stock
                    else (
                        f"Margen estresado bajo en {cand.name}: {stressed['stressed_margin_pct']:.1f}%"
                        if ko_margin or ko_multiplier
                        else None
                    )
                ),
            })

        tmp = target_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, target_path)

        alerts = [r["alert"] for r in results if r.get("alert")]
        summary_out = {
            "ok": True,
            "source": "n8n_dsers_shopify_bridge",
            "synced_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "updated_count": len(results),
            "updated": results,
            "has_alerts": bool(alerts),
            "alerts": alerts,
        }
        try:
            last_sync_path = target_path.parent / "n8n_last_sync.json"
            last_sync_path.write_text(json.dumps(summary_out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError:
            pass

    return summary_out


def bridge_status(products_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Devuelve el resumen actual de inventario y costos para consulta rápida desde n8n."""
    target_path = Path(products_path) if products_path else DEFAULT_PRODUCTS_PATH
    if not target_path.exists():
        return {"ok": False, "products": [], "error": "user_products.json no encontrado"}
    raw_doc = json.loads(target_path.read_text(encoding="utf-8"))
    items = raw_doc.get("products", []) if isinstance(raw_doc, dict) else raw_doc
    summary = []
    for p in items:
        if not isinstance(p, dict):
            continue
        stock = p.get("verified_stock")
        vdate = p.get("verified_date")
        st = stock_status(int(stock) if stock is not None else None, vdate)
        stressed = compute_stressed(
            float(p.get("srp_usd") or 0),
            float(p.get("unit_cost_usd") or 0),
            float(p.get("shipping_cost_usd") or 0),
        )
        summary.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "en_tienda": bool(p.get("en_tienda", False)),
            "verified_stock": stock,
            "verified_date": vdate,
            "stock_status": st,
            "ko_stock": st == STOCK_LOW,
            "srp_usd": p.get("srp_usd"),
            "landed_cost_usd": stressed["landed_cost"],
            "stressed_profit_usd": stressed["stressed_profit"],
            "stressed_margin_pct": stressed["stressed_margin_pct"],
        })
    return {
        "ok": True,
        "bridge": "DSers <-> Shopify <-> n8n <-> Dropshipping Hunter",
        "endpoints": {
            "status_get": "http://127.0.0.1:8765/api/n8n/status",
            "sync_stock_post": "http://127.0.0.1:8765/api/n8n/sync-stock",
        },
        "products": summary,
    }


get_n8n_bridge_status = bridge_status


def build_n8n_workflow_template() -> Dict[str, Any]:
    """Genera el workflow JSON importable en n8n (Community Edition gratis o Cloud con ahorro de cuota)."""
    return {
        "name": "Ralf & Co — DSers + Shopify -> Dropshipping Hunter (Sincronizador Gratuito de Stock)",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "shopify-dsers-inventory",
                    "responseMode": "lastNode",
                    "options": {},
                },
                "id": "node-shopify-webhook",
                "name": "1. Webhook Shopify (DSers Stock Update)",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [220, 220],
            },
            {
                "parameters": {
                    "rule": {
                        "interval": [{"field": "hours", "hoursInterval": 6}],
                    }
                },
                "id": "node-schedule-6h",
                "name": "1b. Consulta Espaciada (Cada 6h - Ahorro Cuota Gratis)",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.2,
                "position": [220, 420],
            },
            {
                "parameters": {
                    "method": "GET",
                    "url": "https://ralfandco.myshopify.com/products.json?limit=50",
                    "options": {},
                },
                "id": "node-shopify-poll",
                "name": "2a. Leer Catálogo Shopify (Sincronizado por DSers)",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [480, 420],
            },
            {
                "parameters": {
                    "jsCode": (
                        "const raw = $input.first().json;\n"
                        "if (Array.isArray(raw.products)) {\n"
                        "  return [{ json: { updates: raw.products.map(p => ({ handle: p.handle, variants: p.variants })) } }];\n"
                        "}\n"
                        "return [{ json: raw }];"
                    ),
                },
                "id": "node-normalize-payload",
                "name": "2b. Normalizar SKU / Stock / Costo DSers",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [740, 320],
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": "http://127.0.0.1:8765/api/n8n/sync-stock",
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {"name": "X-Hunter", "value": "1"},
                            {"name": "Content-Type", "value": "application/json"},
                        ]
                    },
                    "sendBody": True,
                    "specifyBody": "json",
                    "jsonBody": "={{ JSON.stringify($json) }}",
                    "options": {},
                },
                "id": "node-hunter-sync",
                "name": "3. Actualizar Dropshipping Hunter Local",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [1000, 320],
            },
            {
                "parameters": {
                    "conditions": {
                        "boolean": [
                            {
                                "value1": "={{ Boolean($json.has_alerts) }}",
                                "value2": True,
                            }
                        ]
                    }
                },
                "id": "node-ko-router",
                "name": "4. Detector de Alerta KO-STOCK (< 100 uds)",
                "type": "n8n-nodes-base.if",
                "typeVersion": 2,
                "position": [1260, 320],
            },
        ],
        "connections": {
            "1. Webhook Shopify (DSers Stock Update)": {
                "main": [[{"node": "2b. Normalizar SKU / Stock / Costo DSers", "type": "main", "index": 0}]]
            },
            "1b. Consulta Espaciada (Cada 6h - Ahorro Cuota Gratis)": {
                "main": [[{"node": "2a. Leer Catálogo Shopify (Sincronizado por DSers)", "type": "main", "index": 0}]]
            },
            "2a. Leer Catálogo Shopify (Sincronizado por DSers)": {
                "main": [[{"node": "2b. Normalizar SKU / Stock / Costo DSers", "type": "main", "index": 0}]]
            },
            "2b. Normalizar SKU / Stock / Costo DSers": {
                "main": [[{"node": "3. Actualizar Dropshipping Hunter Local", "type": "main", "index": 0}]]
            },
            "3. Actualizar Dropshipping Hunter Local": {
                "main": [[{"node": "4. Detector de Alerta KO-STOCK (< 100 uds)", "type": "main", "index": 0}]]
            },
        },
        "settings": {"executionOrder": "v1"},
    }


def export_n8n_workflow(output_path: Optional[Union[str, Path]] = None) -> Path:
    path = Path(output_path) if output_path else DEFAULT_WORKFLOW_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_n8n_workflow_template(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Puente DSers / Shopify <-> n8n <-> Dropshipping Hunter")
    parser.add_argument("--status", action="store_true", help="Mostrar resumen de stock y margen actual en JSON")
    parser.add_argument("--product-id", type=str, help="ID del producto a sincronizar (ej. steamfur-pro)")
    parser.add_argument("--stock", type=int, help="Unidades disponibles reportadas por DSers/Shopify")
    parser.add_argument("--unit-cost", type=float, default=None, help="Costo unitario en USD (opcional)")
    parser.add_argument("--shipping-cost", type=float, default=None, help="Costo de envío en USD (opcional)")
    parser.add_argument("--srp", type=float, default=None, help="Precio de venta en Shopify en USD (opcional)")
    parser.add_argument("--payload-json", type=str, default=None, help="Payload JSON crudo desde n8n/Shopify")
    parser.add_argument("--export-workflow", action="store_true", help="Exportar plantilla JSON para n8n")
    parser.add_argument("--products-path", type=str, default=str(DEFAULT_PRODUCTS_PATH))
    args = parser.parse_args(argv)

    if args.export_workflow:
        out = export_n8n_workflow()
        print(json.dumps({"ok": True, "workflow_path": str(out)}, ensure_ascii=False))
        return 0

    if args.status:
        print(json.dumps(bridge_status(args.products_path), indent=2, ensure_ascii=False))
        return 0

    if args.payload_json:
        payload = json.loads(args.payload_json)
    elif args.product_id:
        payload = {"id": args.product_id}
        if args.stock is not None:
            payload["verified_stock"] = args.stock
        if args.unit_cost is not None:
            payload["unit_cost_usd"] = args.unit_cost
        if args.shipping_cost is not None:
            payload["shipping_cost_usd"] = args.shipping_cost
        if args.srp is not None:
            payload["srp_usd"] = args.srp
    else:
        print(json.dumps(bridge_status(args.products_path), indent=2, ensure_ascii=False))
        return 0

    res = sync_dsers_stock_payload(payload, products_path=args.products_path)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
