"""Operator inputs (data/user_products.json), 7-day stock expiry, KO-STOCK, stressed margin,
two-level alerts and the 'scraping off by default' contract."""

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from hunter.audit_engine import AuditEngine
from hunter.dashboard_data import build_health
from hunter.hunter_engine import HunterEngine
from hunter.provenance import (
    MANUAL, NO_LIVE_DATA, STOCK_EXPIRED, STOCK_LOW, STOCK_OK, STOCK_UNVERIFIED, UNAVAILABLE, NoLiveDataError,
)
from hunter.scrapers.live_supplier_sync import LiveSupplierSync
from hunter.stress import compute_stressed
from hunter.user_products import load_user_products, product_to_candidate, stock_status

PROJECT = Path(__file__).resolve().parent.parent
TODAY = date(2026, 10, 8)

BASE = {
    "id": "steamfur-pro",
    "name": "SteamFur Pro™ — 3-in-1 Ultrasonic Mist Pet Groomer",
    "category": "Pet Supplies & Home Care",
    "source_url": "https://www.aliexpress.com/item/1005007791672610.html",
    "srp_usd": 29.99,
    "unit_cost_usd": 4.73,
    "shipping_cost_usd": 3.54,
    "target_variant_name": "green",
    "verified_stock": 994,
    "verified_date": "2026-10-08",
    "trends_keyword": "steamy pet brush",
    "shipping": {"days_min": 7, "days_max": 12, "carrier": "AliExpress Choice (Free Shipping 7-12D)"},
    "rule_inputs": {
        "demo_visual_speed_sec": 2.0, "pain_level_score": 88.0, "retail_availability_score": 85.0,
        "has_fragile_material": False, "has_sizing_requirements": False,
        "ad_active_days": 38, "competitor_ad_count": 29, "google_trends_momentum": 55.8,
    },
}


def product(**over):
    p = copy.deepcopy(BASE)
    p.update(over)
    return p


def write_products(folder: Path, products) -> Path:
    path = folder / "user_products.json"
    path.write_text(json.dumps({"products": products}, ensure_ascii=False), encoding="utf-8")
    return path


class TestStockStatus(unittest.TestCase):
    def test_fresh_and_healthy_is_ok(self):
        self.assertEqual(stock_status(994, "2026-10-08", TODAY), STOCK_OK)

    def test_exactly_seven_days_is_still_ok_eight_is_expired(self):
        self.assertEqual(stock_status(994, "2026-10-01", TODAY), STOCK_OK)
        self.assertEqual(stock_status(994, "2026-09-30", TODAY), STOCK_EXPIRED)

    def test_below_100_is_low_even_if_fresh(self):
        self.assertEqual(stock_status(99, "2026-10-08", TODAY), STOCK_LOW)
        self.assertEqual(stock_status(100, "2026-10-08", TODAY), STOCK_OK)

    def test_low_wins_over_expired(self):
        self.assertEqual(stock_status(17, "2026-01-01", TODAY), STOCK_LOW)

    def test_missing_stock_or_date_is_unverified(self):
        self.assertEqual(stock_status(None, "2026-10-08", TODAY), STOCK_UNVERIFIED)
        self.assertEqual(stock_status(500, None, TODAY), STOCK_UNVERIFIED)


class TestLoadUserProducts(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_maps_fields_to_candidate(self):
        cands, errors = load_user_products(write_products(self.tmp, [product()]), today=TODAY)
        self.assertEqual(errors, [])
        c = cands[0]
        self.assertEqual((c.supplier_cost, c.shipping_cost, c.suggested_price), (4.73, 3.54, 29.99))
        self.assertEqual((c.supplier_variant, c.supplier_stock, c.stock_status), ("green", 994, STOCK_OK))
        self.assertEqual(c.trends_keyword, "steamy pet brush")
        self.assertEqual(c.data_status["supplier"], MANUAL)

    def test_one_bad_product_does_not_hide_the_others(self):
        bad = product(id="broken")
        del bad["unit_cost_usd"]
        cands, errors = load_user_products(write_products(self.tmp, [bad, product(id="ok")]), today=TODAY)
        self.assertEqual([c.candidate_id for c in cands], ["ok"])
        self.assertIn("broken", errors[0])
        self.assertIn("unit_cost_usd", errors[0])

    def test_missing_rule_inputs_are_reported(self):
        p = product()
        del p["rule_inputs"]["pain_level_score"]
        _, errors = load_user_products(write_products(self.tmp, [p]), today=TODAY)
        self.assertIn("rule_inputs.pain_level_score", errors[0])

    def test_bad_date_and_duplicate_ids_are_reported(self):
        cands, errors = load_user_products(
            write_products(self.tmp, [product(verified_date="08/10/2026"), product(id="a"), product(id="a")]),
            today=TODAY,
        )
        self.assertEqual([c.candidate_id for c in cands], ["a"])
        self.assertTrue(any("AAAA-MM-DD" in e for e in errors))
        self.assertTrue(any("duplicado" in e for e in errors))

    def test_plain_list_format_is_accepted(self):
        path = self.tmp / "user_products.json"
        path.write_text(json.dumps([product()]), encoding="utf-8")
        cands, errors = load_user_products(path, today=TODAY)
        self.assertEqual((len(cands), errors), (1, []))

    def test_shipped_user_products_file_is_valid(self):
        cands, errors = load_user_products(PROJECT / "data" / "user_products.json", today=TODAY)
        self.assertEqual(errors, [])
        ids = {c.candidate_id for c in cands}
        self.assertEqual(ids, {"steamfur-pro", "prosmile-ultrasonic", "spinerelief-pro", "aeroforce-x3"})


class TestStressedMargin(unittest.TestCase):
    def test_steamfur_numbers(self):
        s = compute_stressed(29.99, 4.73, 3.54)
        self.assertEqual(s["landed_cost"], 8.27)
        self.assertEqual(s["gateway_fee"], 1.54)        # 29.99 * 3.49% + 0.49
        self.assertEqual(s["breakage_buffer"], 1.24)    # 15% of landed
        self.assertEqual(s["chargeback_reserve"], 0.30) # 1% of SRP
        self.assertEqual(s["gross_profit"], 21.72)
        self.assertEqual(s["stressed_profit"], 18.64)
        self.assertAlmostEqual(s["gross_margin_pct"], 72.42, places=2)
        self.assertAlmostEqual(s["stressed_margin_pct"], 62.15, places=2)
        self.assertFalse(s["below_floor"])

    def test_stressed_is_always_below_gross(self):
        s = compute_stressed(54.99, 10.0, 4.8)
        self.assertLess(s["stressed_margin_pct"], s["gross_margin_pct"])

    def test_thin_product_goes_below_floor(self):
        self.assertTrue(compute_stressed(19.99, 9.0, 2.0)["below_floor"])

    def test_zero_price_does_not_crash(self):
        self.assertEqual(compute_stressed(0.0, 1.0, 1.0)["stressed_margin_pct"], 0.0)


class TestStockGateInAudit(unittest.TestCase):
    def audit(self, **over):
        return AuditEngine().audit_candidate(product_to_candidate(product(**over), today=TODAY))

    def test_healthy_fresh_product_can_win_and_carries_stressed_metrics(self):
        r = self.audit()
        self.assertEqual(r.tier, "WINNER")
        self.assertEqual(r.tier_reasons, [])
        self.assertEqual(r.stressed["stressed_profit"], 18.64)

    def test_low_stock_is_disqualified_whatever_the_score(self):
        r = self.audit(verified_stock=17)
        self.assertEqual(r.tier, "DISQUALIFIED")
        self.assertFalse(r.passed_audit)
        self.assertIn("KO-STOCK", r.ko_gates_tripped)
        self.assertIn("inventario frágil", r.tier_reasons[0])
        self.assertGreater(r.composite_score, 80)  # it WOULD have won: the gate is what blocks it

    def test_expired_stock_downgrades_winner_to_conditional_contender(self):
        r = self.audit(verified_date="2026-09-01")
        self.assertEqual(r.tier, "CONTENDER")
        self.assertIn("vencido", r.tier_reasons[0])
        self.assertIn("condicional", r.tier_reasons[0])

    def test_unverified_stock_cannot_be_winner(self):
        r = self.audit(verified_stock=None, verified_date=None)
        self.assertEqual(r.tier, "CONTENDER")
        self.assertIn("sin verificar", r.tier_reasons[0])

    def test_legacy_seed_candidates_are_unaffected(self):
        results = AuditEngine().audit_candidates(HunterEngine.get_seed_candidates())
        self.assertEqual(sum(r.tier == "WINNER" for r in results), 4)
        self.assertTrue(all(r.tier_reasons == [] for r in results))

    def test_audit_result_roundtrip_keeps_new_fields(self):
        from hunter.models import AuditResult

        r = self.audit(verified_stock=17)
        again = AuditResult.from_dict(json.loads(r.to_json()))
        self.assertEqual((again.tier_reasons, again.stressed), (r.tier_reasons, r.stressed))
        self.assertEqual(again.candidate.stock_status, STOCK_LOW)


class TestHealthAlerts(unittest.TestCase):
    def health(self, products, errors=None):
        results = [AuditEngine().audit_candidate(product_to_candidate(p, today=TODAY)) for p in products]
        for r in results:
            for s in ("tiktok", "meta", "freight"):
                r.candidate.data_status[s] = UNAVAILABLE
        return build_health(results, offline=False, input_errors=errors)

    def test_retired_sources_are_grey_not_red(self):
        h = self.health([product()])
        self.assertEqual(h["alerts_red"], [])
        self.assertEqual(h["sources"]["tiktok"][UNAVAILABLE], 1)
        self.assertFalse(h["has_failures"])

    def test_ko_stock_is_red_and_expired_is_yellow(self):
        h = self.health([product(id="a", verified_stock=17), product(id="b", verified_date="2026-09-01")])
        self.assertTrue(any("KO-STOCK" in a for a in h["alerts_red"]))
        self.assertTrue(any("vencido" in a for a in h["alerts_yellow"]))
        self.assertTrue(h["has_failures"])

    def test_trends_failure_and_input_errors_are_red(self):
        results = [AuditEngine().audit_candidate(product_to_candidate(product(), today=TODAY))]
        results[0].candidate.data_status["trends"] = NO_LIVE_DATA
        h = build_health(results, offline=False, input_errors=["x: faltan campos: srp_usd"])
        self.assertEqual(len(h["alerts_red"]), 2)

    def test_stressed_margin_below_floor_is_red_when_ideal_margin_passes(self):
        # landed $12 on $29.99: ideal net margin 55.1% passes KO-2, stressed margin is 47.8%.
        p = product(unit_cost_usd=8.5, shipping_cost_usd=3.5)
        r = AuditEngine().audit_candidate(product_to_candidate(p, today=TODAY))
        self.assertNotEqual(r.tier, "DISQUALIFIED")
        self.assertAlmostEqual(r.stressed["stressed_margin_pct"], 47.85, places=2)
        h = self.health([p])
        self.assertTrue(any("margen estresado" in a for a in h["alerts_red"]))

    def test_disqualified_product_does_not_get_a_duplicate_margin_alert(self):
        h = self.health([product(srp_usd=19.99, unit_cost_usd=9.0, shipping_cost_usd=2.0)])  # trips KO-2
        self.assertFalse(any("margen estresado" in a for a in h["alerts_red"]))


class TestHarvestProducts(unittest.TestCase):
    def test_only_trends_is_queried_by_default_and_costs_are_untouched(self):
        cand = product_to_candidate(product(), today=TODAY)
        engine = HunterEngine(offline_mode=False)
        with patch.object(engine.trends_scraper, "get_trend_analysis", return_value={"momentum_pct": 12.0}) as tr, \
             patch.object(engine.tiktok_scraper, "search_top_ads") as tk, \
             patch.object(engine.meta_scraper, "analyze_scaling_footprint") as mt, \
             patch.object(engine.freight_scraper, "get_freight_options") as fr:
            engine.harvest_products([cand])
        tr.assert_called_once_with(keyword="steamy pet brush")
        tk.assert_not_called(); mt.assert_not_called(); fr.assert_not_called()
        self.assertEqual(cand.data_status["trends"], "LIVE")
        self.assertEqual(cand.google_trends_momentum, 12.0)
        for s in ("tiktok", "meta", "freight"):
            self.assertEqual(cand.data_status[s], UNAVAILABLE)
        self.assertEqual((cand.supplier_cost, cand.shipping_cost, cand.supplier_stock), (4.73, 3.54, 994))

    def test_probe_all_never_overwrites_operator_shipping_cost(self):
        cand = product_to_candidate(product(), today=TODAY)
        engine = HunterEngine(offline_mode=False)
        freight = {"selected_carrier": "X", "shipping_cost": 9.99, "shipping_days_min": 8, "shipping_days_max": 15}
        with patch.object(engine.trends_scraper, "get_trend_analysis", side_effect=NoLiveDataError("t", "429")), \
             patch.object(engine.tiktok_scraper, "search_top_ads", return_value=[]), \
             patch.object(engine.meta_scraper, "analyze_scaling_footprint", return_value={"active_ad_count": 3}), \
             patch.object(engine.freight_scraper, "get_freight_options", return_value=freight):
            engine.harvest_products([cand], probe_all=True)
        self.assertEqual(cand.shipping_cost, 3.54)
        self.assertEqual(cand.data_status["trends"], NO_LIVE_DATA)
        self.assertEqual(cand.data_status["freight"], "LIVE")


class TestScrapingOffByDefault(unittest.TestCase):
    def test_fetch_rows_refuses_without_launching_chrome(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("SCRAPE_ALIEXPRESS", None)
            sync = LiveSupplierSync()
            self.assertFalse(sync.enabled)
            with patch("selenium.webdriver.Chrome") as chrome:
                with self.assertRaises(NoLiveDataError):
                    sync.fetch_rows("https://www.aliexpress.com/item/1.html")
                chrome.assert_not_called()

    def test_env_flag_enables(self):
        with patch.dict("os.environ", {"SCRAPE_ALIEXPRESS": "1"}):
            self.assertTrue(LiveSupplierSync().enabled)

    def test_chrome_is_always_headless(self):
        import inspect
        import hunter.scrapers.live_supplier_sync as ls

        src = inspect.getsource(ls.LiveSupplierSync.fetch_rows)
        self.assertIn('"--headless=new"', src)
        self.assertNotIn("HUNTER_HEADFUL", src)

    def test_centinela_never_requests_supplier_scraping(self):
        src = (PROJECT / "centinela_local.py").read_text(encoding="utf-8")
        self.assertIn('[sys.executable, "main.py"]', src)  # exact command: no extra flags
        self.assertNotIn('"--scrape-suppliers"', src)
        self.assertNotIn("SCRAPE_ALIEXPRESS", src)


class TestPipelineRespectsOperatorFile(unittest.TestCase):
    def test_full_offline_run_reads_but_never_writes_user_products(self):
        import main

        tmp = Path(tempfile.mkdtemp())
        try:
            data = tmp / "data"
            data.mkdir()
            path = write_products(data, [product(), product(id="thin", verified_stock=17)])
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            with patch.object(main, "PROJECT_ROOT", tmp), patch.object(main, "run_visualize_stage"), \
                 patch.object(main, "run_dossier_stage", return_value=tmp / "d.md"):
                code = main.main(["--offline", "--data-dir", "data", "--quiet"])
            self.assertEqual(code, 0)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
            audit = {r["candidate"]["candidate_id"]: r for r in json.loads((data / "audit_results.json").read_text("utf-8"))}
            self.assertEqual(set(audit), {"steamfur-pro", "thin"})
            self.assertEqual(audit["thin"]["tier"], "DISQUALIFIED")
            self.assertIn("KO-STOCK", audit["thin"]["ko_gates_tripped"])
            js = (data / "dashboard_data.js").read_text("utf-8")
            self.assertTrue(js.startswith("window.HUNTER_DATA = "))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
