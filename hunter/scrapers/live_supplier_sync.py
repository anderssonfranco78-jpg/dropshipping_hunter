"""Live Supplier Sync: real AliExpress price + stock per variant, with a healthy-stock filter.

Honesty contract (no fallbacks):
- Prices and stock come ONLY from the rendered supplier page. If the page cannot be read, the quote
  is returned with ``status = NO_LIVE_DATA`` and a reason; no "verified checkpoint" is invented.
- A cheap variant with thin stock is a trap (it sells out and the listing silently flips to a
  pricier SKU). The selector therefore requires the TARGET variant (e.g. "green") to hold at
  least ``MIN_HEALTHY_STOCK`` units in the Choice warehouse. If it does not, nothing is substituted
  silently: the quote is flagged ``variant_healthy = False`` and the alternatives are listed.

How the data is read: the current AliExpress item page is client-side rendered and exposes no SKU
JSON, so each variant thumbnail is clicked in a headless Chrome and its price ("$4.73") and stock
("994 available") are read from the DOM. The US storefront (USD) is requested via cookie; any
non-USD price is refused instead of being converted with an invented exchange rate.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from hunter.models import RawCandidate
from hunter.provenance import LIVE, NO_LIVE_DATA, NoLiveDataError

logger = logging.getLogger("hunter.live_sync")

MIN_HEALTHY_STOCK = 100

# If the live page price differs from the cost already on file by more than this fraction, the cost
# is NOT overwritten (the page price may exclude shipping/taxes/coins) and a note is raised instead.
PRICE_DEVIATION_LIMIT = 0.25

# Canonical registry. ``target_variant_names`` lists the exact variant label(s) the store actually
# sells (same colour/bundle as the product media), compared case-insensitively and EXACTLY, so that
# "green" does not also match "2PCS-Green". Empty list = no preference, cheapest healthy wins.
VERIFIED_SUPPLIERS: Dict[str, Dict[str, Any]] = {
    "steamfur-pro": {
        "url": "https://www.aliexpress.com/item/1005007791672610.html",
        "target_variant_names": ["green"],
        "min_stock": MIN_HEALTHY_STOCK,
        "carrier": "AliExpress Choice (Free Shipping 7-12D)",
    },
    "prosmile-ultrasonic": {
        "url": "https://www.aliexpress.com/item/1005005236582798.html",
        "target_variant_names": [],
        "min_stock": MIN_HEALTHY_STOCK,
        "carrier": "AliExpress Choice (Free Shipping 7-12D)",
    },
    "spinerelief-pro": {
        "url": "https://www.aliexpress.com/item/1005006626002554.html",
        "target_variant_names": [],
        "min_stock": MIN_HEALTHY_STOCK,
        "carrier": "AliExpress Choice (Free Shipping 7-12D)",
    },
    "aeroforce-x3": {
        "url": "https://www.aliexpress.com/item/1005009719197258.html",
        "target_variant_names": [],
        "min_stock": MIN_HEALTHY_STOCK,
        "carrier": "AliExpress Choice (Free Shipping 7-12D)",
    },
}


# ---------------------------------------------------------------------------
# Variant model + parsing + selection (pure functions, unit-testable offline)
# ---------------------------------------------------------------------------

@dataclass
class Variant:
    name: str
    price_usd: float
    stock: Optional[int]  # None = the page did not expose stock for this SKU

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VariantDecision:
    selected: Optional[Variant]
    healthy: bool
    reason: str
    rejected: List[Tuple[Variant, str]] = field(default_factory=list)
    alternatives: List[Variant] = field(default_factory=list)


_PRICE_RE = re.compile(r"^(?:US\s?)?\$\s?([\d.,]+)")
_STOCK_RE = re.compile(r"(\d[\d.,]*)\s*(?:disponible|available)", re.IGNORECASE)


def variants_from_rows(rows: Sequence[Dict[str, Any]]) -> List[Variant]:
    """Turn rows read from the rendered page (name, price text, stock text) into Variants."""
    variants: List[Variant] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        price_text = str(row.get("price") or "").strip()
        if not name or not price_text:
            continue  # unreadable row: skip, never guess
        m = _PRICE_RE.match(price_text)
        if not m:
            raise NoLiveDataError(
                "LiveSupplierSync",
                f"precio '{price_text}' no está en USD (se exige USD, sin tipo de cambio inventado)",
            )
        price = round(float(m.group(1).replace(",", "")), 2)
        sm = _STOCK_RE.search(str(row.get("stock") or ""))
        stock = int(re.sub(r"[.,]", "", sm.group(1))) if sm else None
        variants.append(Variant(name=name, price_usd=price, stock=stock))
    if not variants:
        raise NoLiveDataError("LiveSupplierSync", "no se pudo leer ninguna variante de la página")
    return variants


def select_variant(
    variants: Sequence[Variant],
    names: Sequence[str] = (),
    min_stock: int = MIN_HEALTHY_STOCK,
) -> VariantDecision:
    """Pick the variant to quote, rejecting thin-stock traps.

    - With ``names`` (exact variant labels): the target must have ``stock >= min_stock``. The target
      is NOT replaced silently if it is thin; the healthy alternatives are only listed.
    - Without ``names``: the cheapest variant with healthy stock wins.
    """
    rejected: List[Tuple[Variant, str]] = []
    healthy: List[Variant] = []
    for v in variants:
        if v.stock is None:
            rejected.append((v, "stock desconocido"))
        elif v.stock < min_stock:
            rejected.append((v, f"stock bajo ({v.stock} < {min_stock})"))
        else:
            healthy.append(v)

    wanted = [n.strip().lower() for n in names]
    if wanted:
        def matches(v: Variant) -> bool:
            return v.name.strip().lower() in wanted

        targets = [v for v in variants if matches(v)]
        healthy_targets = [v for v in healthy if matches(v)]
        if healthy_targets:
            best = min(healthy_targets, key=lambda v: v.price_usd)
            return VariantDecision(
                best, True, f"variante objetivo '{best.name}' con stock sano ({best.stock})", rejected=rejected
            )
        alternatives = sorted(healthy, key=lambda v: v.price_usd)
        if targets:
            reason = "la variante objetivo no tiene stock sano: " + "; ".join(
                f"'{v.name}' {('?' if v.stock is None else v.stock)} uds" for v in targets
            )
        else:
            reason = "no se encontró ninguna variante llamada " + ", ".join(wanted)
        return VariantDecision(None, False, reason, rejected=rejected, alternatives=alternatives)

    if healthy:
        best = min(healthy, key=lambda v: v.price_usd)
        return VariantDecision(
            best, True, f"variante más barata con stock sano: '{best.name}' ({best.stock})", rejected=rejected
        )
    return VariantDecision(None, False, f"ninguna variante supera {min_stock} unidades", rejected=rejected)


# ---------------------------------------------------------------------------
# Quote + live fetch
# ---------------------------------------------------------------------------

@dataclass
class LivePriceQuote:
    candidate_id: str
    status: str                         # LIVE | NO_LIVE_DATA
    reason: str
    source_url: str
    carrier: str
    verified_at: str
    product_price_usd: Optional[float] = None
    variant_name: Optional[str] = None
    variant_stock: Optional[int] = None
    variant_healthy: bool = False
    rejected_variants: List[Dict[str, Any]] = field(default_factory=list)
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    all_variants: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_live(self) -> bool:
        return self.status == LIVE and self.product_price_usd is not None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Runs inside the rendered page: click every variant, read its price + stock from the DOM.
_DOM_SCRIPT = r"""
const done = arguments[arguments.length - 1];
(async () => {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const SEL = '[class*="sku-item--image"], [class*="sku-item--text"]';
  for (let i = 0; i < 40 && !document.querySelector(SEL); i++) await wait(500);
  const readStock = () => {
    const el = [...document.querySelectorAll('*')].find(e => e.children.length === 0 &&
      /\d\s*(disponible|available)/i.test(e.textContent || '') && e.textContent.length < 60);
    return el ? el.textContent.trim() : null;
  };
  const rows = [];
  const items = document.querySelectorAll(SEL);
  if (!items.length) {
    // Single-variant listing: no selector on the page, read the one price/stock shown.
    await wait(1500);
    const price = document.querySelector('[class*="price-default--current"]');
    if (!price) {
      // Nothing readable: report WHAT the page showed so the failure is diagnosable from the log.
      done({ error: 'sin variantes ni precio visibles (posible bloqueo anti-bot). título="' +
        document.title.slice(0, 60) + '" texto="' + document.body.innerText.slice(0, 90).replace(/\s+/g, ' ') + '"' });
      return;
    }
    rows.push({ name: 'default', price: price.innerText.trim(), stock: readStock() });
    done(rows);
    return;
  }
  for (const el of items) {
    el.click(); await wait(1300);
    let stock = readStock();
    if (!stock) { await wait(900); stock = readStock(); }
    const price = document.querySelector('[class*="price-default--current"]');
    rows.push({
      name: el.getAttribute('title') || (el.querySelector('img') || {}).alt || el.innerText.trim(),
      price: price ? price.innerText.trim() : null,
      stock: stock,
    });
  }
  done(rows);
})();
"""


def scraping_enabled() -> bool:
    """Supplier scraping is opt-in: SCRAPE_ALIEXPRESS=1 (main.py --scrape-suppliers sets it)."""
    return os.environ.get("SCRAPE_ALIEXPRESS") == "1"


class LiveSupplierSync:
    """Reads real variant prices/stock from the supplier page (Selenium, headless)."""

    def __init__(self, timeout: int = 30, settle_seconds: float = 4.0, enabled: Optional[bool] = None):
        self.timeout = timeout
        self.settle_seconds = settle_seconds
        # OFF by default. Enabled only with `main.py --scrape-suppliers` or SCRAPE_ALIEXPRESS=1.
        self.enabled = scraping_enabled() if enabled is None else enabled

    def fetch_rows(self, url: str) -> List[Dict[str, Any]]:
        """Open the item page headless (US/USD storefront) and read every variant."""
        if not self.enabled:
            raise NoLiveDataError("LiveSupplierSync", "scraping de AliExpress desactivado (usa --scrape-suppliers)")
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError as exc:
            raise NoLiveDataError("LiveSupplierSync", f"selenium no instalado ({exc})")

        options = Options()
        # Always headless: this tool must never open a visible browser window on the operator's PC.
        # AliExpress often serves an empty product page to headless Chrome (bot protection); the
        # supplier signal is then reported "Sin datos en vivo" and the operator's manual data is kept.
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1400,1000")
        options.add_argument("--lang=en-US")
        # Persistent profile: keeps cookies/session between runs (like a returning visitor). If AliExpress
        # ever shows a captcha, solve it once in the visible window; the session is then reused.
        profile = os.environ.get("HUNTER_CHROME_PROFILE") or str(Path(__file__).resolve().parents[2] / ".chrome_profile")
        options.add_argument(f"--user-data-dir={profile}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as exc:
            raise NoLiveDataError("LiveSupplierSync", f"no se pudo iniciar Chrome: {exc}")
        try:
            driver.set_page_load_timeout(self.timeout)
            driver.set_script_timeout(180)
            # Request the US storefront / USD (the item redirects to aliexpress.us).
            driver.get("https://www.aliexpress.com/")
            try:  # the cookie can only be set while on an aliexpress.com host (a redirect may land elsewhere)
                if "aliexpress.com" in driver.current_url:
                    driver.add_cookie({
                        "name": "aep_usuc_f",
                        "value": "site=glo&c_tp=USD&region=US&b_locale=en_US",
                        "domain": ".aliexpress.com",
                    })
            except Exception as exc:
                logger.warning("No se pudo fijar la cookie USD: %s", exc)
            driver.get(url)
            time.sleep(self.settle_seconds)
            result = driver.execute_async_script(_DOM_SCRIPT)
            if isinstance(result, dict) and result.get("error"):
                raise NoLiveDataError("LiveSupplierSync", result["error"])
            return result
        except NoLiveDataError:
            raise
        except Exception as exc:
            raise NoLiveDataError("LiveSupplierSync", f"error leyendo {url}: {str(exc)[:160]}")
        finally:
            driver.quit()

    def quote_from_rows(self, candidate_id: str, rows: Sequence[Dict[str, Any]]) -> LivePriceQuote:
        """Build a quote from DOM rows (separated from fetching so it can be tested offline)."""
        info = VERIFIED_SUPPLIERS[candidate_id]
        now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        base = dict(candidate_id=candidate_id, source_url=info["url"], carrier=info["carrier"], verified_at=now)

        variants = variants_from_rows(rows)
        decision = select_variant(variants, info["target_variant_names"], info["min_stock"])
        common = dict(
            reason=decision.reason,
            rejected_variants=[dict(v.to_dict(), reason=why) for v, why in decision.rejected],
            alternatives=[v.to_dict() for v in decision.alternatives],
            all_variants=[v.to_dict() for v in variants],
            **base,
        )
        if decision.selected is None:
            return LivePriceQuote(status=LIVE, variant_healthy=False, **common)
        sel = decision.selected
        return LivePriceQuote(
            status=LIVE, product_price_usd=sel.price_usd, variant_name=sel.name,
            variant_stock=sel.stock, variant_healthy=True, **common,
        )

    def fetch_live_quote(self, candidate_id: str) -> LivePriceQuote:
        """Live quote for one candidate. Never raises for source failures: returns NO_LIVE_DATA."""
        info = VERIFIED_SUPPLIERS.get(candidate_id)
        if not info:
            raise ValueError(f"Unknown candidate_id: {candidate_id}")
        try:
            return self.quote_from_rows(candidate_id, self.fetch_rows(info["url"]))
        except NoLiveDataError as exc:
            logger.error("Sin datos en vivo para %s: %s", candidate_id, exc.reason)
            return LivePriceQuote(
                candidate_id=candidate_id, status=NO_LIVE_DATA, reason=exc.reason,
                source_url=info["url"], carrier=info["carrier"],
                verified_at=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            )

    @staticmethod
    def apply_quote(candidate: RawCandidate, quote: LivePriceQuote) -> bool:
        """Apply a live quote to the candidate. Returns True when variant/stock were refreshed.

        Variant + stock are written whenever the quote is live and healthy. The COST is only
        overwritten when the live page price is within PRICE_DEVIATION_LIMIT of the cost on file:
        a big gap usually means the page price excludes shipping/taxes/coins, and silently
        adopting it would inflate the margin. In that case ``cost_note`` explains why.
        """
        if not (quote.is_live and quote.variant_healthy):
            return False
        candidate.supplier_variant = quote.variant_name
        candidate.supplier_stock = quote.variant_stock
        candidate.shipping_carrier = quote.carrier
        candidate.source_url = quote.source_url
        reference = candidate.supplier_cost
        if reference > 0 and abs(quote.product_price_usd - reference) / reference > PRICE_DEVIATION_LIMIT:
            candidate.cost_note = (
                f"Precio en vivo ${quote.product_price_usd:.2f} difiere de ${reference:.2f} en archivo "
                f"(>{int(PRICE_DEVIATION_LIMIT * 100)}%): costo NO sobrescrito, confirmar costo real con envío/impuestos"
            )
            return True
        candidate.supplier_cost = quote.product_price_usd
        candidate.cost_note = None
        return True

    def sync_all(self, data_dir: Path) -> Dict[str, LivePriceQuote]:
        """Quote every registered supplier and persist the quotes to data/supplier_quotes.json."""
        quotes = {cid: self.fetch_live_quote(cid) for cid in VERIFIED_SUPPLIERS}
        out = data_dir / "supplier_quotes.json"
        out.write_text(
            json.dumps({cid: q.to_dict() for cid, q in quotes.items()}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Quotes written to %s", out)
        return quotes


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    for cid, q in LiveSupplierSync().sync_all(data_dir).items():
        if q.is_live and q.variant_healthy:
            print(f"  {cid}: {q.variant_name} ${q.product_price_usd:.2f} stock={q.variant_stock}")
        else:
            print(f"  {cid}: SIN DATOS EN VIVO / variante no sana -> {q.reason}")
