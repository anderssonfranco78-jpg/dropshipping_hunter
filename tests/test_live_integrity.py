"""Zero-mocks contract: no invented numbers, honest failure, and the healthy-stock variant filter."""

import json
import unittest
from unittest.mock import MagicMock, patch

from hunter.hunter_engine import HunterEngine
from hunter.models import RawCandidate
from hunter.provenance import MOCK, NO_LIVE_DATA, NoLiveDataError
from hunter.scrapers.google_trends import GoogleTrendsScraper
from hunter.scrapers.live_supplier_sync import (
    LiveSupplierSync,
    Variant,
    select_variant,
    variants_from_rows,
)


def row(name, price, stock):
    return {"name": name, "price": price, "stock": stock}


# Real values read from the rendered AliExpress page (steamfur-pro): the cheap "yellow" has 17 units,
# "green" has 994, the 2PCS/3PCS bundles are also healthy.
REAL_ROWS = [
    row("Dark blue", "$5.62", "128 available"),
    row("yellow", "$4.60", "17 available"),
    row("green", "$4.73", "994 available"),
    row("2PCS-Green", "$7.20", "995 available"),
    row("3PCS-Green", "$9.82", "999 available"),
]


class TestVariantFilter(unittest.TestCase):
    def test_rows_parse_name_price_stock(self):
        variants = {v.name: v for v in variants_from_rows(REAL_ROWS)}
        self.assertEqual((variants["green"].price_usd, variants["green"].stock), (4.73, 994))
        self.assertEqual(variants["yellow"].stock, 17)

    def test_spanish_stock_text_and_thousands_separator(self):
        v = variants_from_rows([row("x", "$1,234.50", "1.250 disponible(s)")])[0]
        self.assertEqual((v.price_usd, v.stock), (1234.5, 1250))

    def test_missing_stock_text_means_unknown_not_zero_or_guess(self):
        self.assertIsNone(variants_from_rows([row("x", "$3.41", None)])[0].stock)

    def test_cheap_low_stock_variant_is_rejected_cheapest_healthy_wins(self):
        decision = select_variant(variants_from_rows(REAL_ROWS), [], min_stock=100)
        self.assertEqual(decision.selected.name, "green")  # NOT yellow (17 units)
        rejected = {v.name: why for v, why in decision.rejected}
        self.assertEqual(rejected["yellow"], "stock bajo (17 < 100)")

    def test_target_uses_exact_name_so_green_does_not_match_2pcs_green(self):
        decision = select_variant(variants_from_rows(REAL_ROWS), ["green"], min_stock=100)
        self.assertTrue(decision.healthy)
        self.assertEqual((decision.selected.name, decision.selected.price_usd), ("green", 4.73))

    def test_target_with_thin_stock_is_not_silently_replaced(self):
        decision = select_variant(variants_from_rows(REAL_ROWS), ["yellow"], min_stock=100)
        self.assertIsNone(decision.selected)
        self.assertFalse(decision.healthy)
        self.assertIn("no tiene stock sano", decision.reason)
        self.assertIn("green", [v.name for v in decision.alternatives])

    def test_unknown_target_name_reports_clearly(self):
        decision = select_variant(variants_from_rows(REAL_ROWS), ["purple"], min_stock=100)
        self.assertIsNone(decision.selected)
        self.assertIn("purple", decision.reason)

    def test_unknown_stock_is_not_healthy(self):
        self.assertIsNone(select_variant([Variant("X", 5.0, None)], [], min_stock=100).selected)

    def test_exactly_min_stock_is_healthy(self):
        self.assertIsNotNone(select_variant([Variant("X", 5.0, 100)], [], min_stock=100).selected)

    def test_just_below_min_stock_is_rejected(self):
        self.assertIsNone(select_variant([Variant("X", 5.0, 99)], [], min_stock=100).selected)

    def test_non_usd_price_is_refused_not_converted(self):
        with self.assertRaises(NoLiveDataError) as ctx:
            variants_from_rows([row("green", "SVC61.59", "500 disponible(s)")])
        self.assertIn("USD", str(ctx.exception))

    def test_no_readable_rows_fails_honestly(self):
        with self.assertRaises(NoLiveDataError):
            variants_from_rows([])
        with self.assertRaises(NoLiveDataError):
            variants_from_rows([row("", None, None)])


class TestSupplierSyncHonesty(unittest.TestCase):
    def _seed(self):
        return next(c for c in HunterEngine.get_seed_candidates() if c.candidate_id == "steamfur-pro")

    def test_quote_from_rows_live_and_healthy(self):
        q = LiveSupplierSync().quote_from_rows("steamfur-pro", REAL_ROWS)
        self.assertTrue(q.is_live and q.variant_healthy)
        self.assertEqual((q.variant_name, q.product_price_usd, q.variant_stock), ("green", 4.73, 994))
        self.assertEqual(len(q.all_variants), 5)

    def test_fetch_failure_returns_no_live_data_not_fallback_price(self):
        sync = LiveSupplierSync()
        with patch.object(sync, "fetch_rows", side_effect=NoLiveDataError("LiveSupplierSync", "bloqueado")):
            q = sync.fetch_live_quote("steamfur-pro")
        self.assertEqual(q.status, NO_LIVE_DATA)
        self.assertIsNone(q.product_price_usd)
        self.assertFalse(q.is_live)

    def test_apply_quote_never_touches_candidate_without_healthy_live_quote(self):
        cand = self._seed()
        before = cand.to_dict()
        sync = LiveSupplierSync()
        with patch.object(sync, "fetch_rows", side_effect=NoLiveDataError("x", "down")):
            self.assertFalse(sync.apply_quote(cand, sync.fetch_live_quote("steamfur-pro")))
        self.assertEqual(cand.to_dict(), before)

    def test_apply_quote_adopts_cost_when_close_to_reference(self):
        cand = self._seed()  # on file: 8.27
        quote = LiveSupplierSync().quote_from_rows("steamfur-pro", [row("green", "$8.40", "700 available")])
        self.assertTrue(LiveSupplierSync.apply_quote(cand, quote))
        self.assertEqual((cand.supplier_cost, cand.supplier_variant, cand.supplier_stock), (8.40, "green", 700))
        self.assertIsNone(cand.cost_note)

    def test_apply_quote_keeps_cost_on_big_deviation_but_updates_stock_and_notes_it(self):
        cand = self._seed()  # on file: 8.27, live page says 4.73 (likely excludes shipping/coins)
        quote = LiveSupplierSync().quote_from_rows("steamfur-pro", REAL_ROWS)
        self.assertTrue(LiveSupplierSync.apply_quote(cand, quote))
        self.assertEqual(cand.supplier_cost, 8.27)  # margin NOT inflated silently
        self.assertEqual((cand.supplier_variant, cand.supplier_stock), ("green", 994))
        self.assertIn("costo NO sobrescrito", cand.cost_note)

    def test_seed_cost_is_the_healthy_variant_not_the_trap(self):
        self.assertEqual(self._seed().supplier_cost, 8.27)


class TestEngineProvenance(unittest.TestCase):
    def _blocked_engine(self):
        engine = HunterEngine(offline_mode=False)
        for scraper in (engine.tiktok_scraper, engine.meta_scraper, engine.trends_scraper, engine.freight_scraper):
            scraper.session.request = MagicMock(side_effect=NoLiveDataError("test", "403"))
        return engine

    def test_all_sources_blocked_marks_no_live_data_and_keeps_values_untouched(self):
        engine = self._blocked_engine()
        seeds = {c.candidate_id: c.to_dict() for c in HunterEngine.get_seed_candidates()}
        with patch("time.sleep"):
            result = {c.candidate_id: c for c in engine.harvest()}
        spine = result["spinerelief-pro"]
        for signal in ("trends", "tiktok", "meta", "freight"):
            self.assertEqual(spine.data_status[signal], NO_LIVE_DATA)
        self.assertEqual(spine.google_trends_momentum, seeds["spinerelief-pro"]["google_trends_momentum"])
        self.assertEqual(spine.ad_active_days, seeds["spinerelief-pro"]["ad_active_days"])

    def test_offline_mode_is_stamped_mock(self):
        result = {c.candidate_id: c for c in HunterEngine(offline_mode=True).harvest()}
        self.assertEqual(result["steamfur-pro"].data_status["trends"], MOCK)

    def test_keyword_maps_to_real_candidate_so_signals_apply(self):
        # Before the fix the slug "steamy-pet-brush" never matched "steamfur-pro": nothing was ever updated.
        result = {c.candidate_id: c for c in HunterEngine(offline_mode=True).harvest()}
        self.assertEqual(result["steamfur-pro"].data_status["tiktok"], MOCK)

    def test_data_status_and_variant_survive_roundtrip(self):
        cand = HunterEngine.get_seed_candidates()[0]
        cand.data_status["trends"] = NO_LIVE_DATA
        cand.supplier_stock = 994
        again = RawCandidate.from_dict(json.loads(cand.to_json()))
        self.assertEqual((again.data_status["trends"], again.supplier_stock), (NO_LIVE_DATA, 994))


class TestNoRandomNumbersInLivePath(unittest.TestCase):
    def test_trends_module_has_no_random_timeline_generation(self):
        import inspect

        import hunter.scrapers.google_trends as gt

        self.assertNotIn("randint", inspect.getsource(gt))

    def test_supplier_module_has_no_fallback_prices(self):
        import inspect

        import hunter.scrapers.live_supplier_sync as ls

        self.assertNotIn("fallback_price", inspect.getsource(ls))

    def test_live_http_block_raises_instead_of_falling_back(self):
        scraper = GoogleTrendsScraper(max_retries=1, offline_mode=False)
        scraper._cookie_primed = True
        with patch.object(scraper.session, "request", return_value=MagicMock(status_code=403)), patch("time.sleep"):
            with self.assertRaises(NoLiveDataError):
                scraper.get_trend_analysis("anything")


if __name__ == "__main__":
    unittest.main()
