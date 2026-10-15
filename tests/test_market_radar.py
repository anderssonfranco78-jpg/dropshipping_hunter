"""Market score, verdicts (LANZAR / PROBAR / VIGILAR / DESCARTAR / MANTENER / RETIRAR), YouTube Shorts
parsing, the radar's 429 circuit breaker, run history and product edits from the panel."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hunter.history import load_runs, previous_bases, save_run
from hunter.market import market_score, trend_score, verdict, video_score
from hunter.provenance import LIVE, NO_LIVE_DATA, NoLiveDataError
from hunter.radar import radar_payload, run_radar
from hunter.scrapers.youtube_shorts import extract_shorts, parse_views, summarize

YT = {"median_views_top10": 100_000, "max_views": 3_800_000, "over_1m": 1, "over_100k": 6}


class TestMarketScore(unittest.TestCase):
    def test_video_score_is_log_scaled(self):
        self.assertEqual(video_score({"median_views_top10": 1_000}), 30)
        self.assertEqual(video_score({"median_views_top10": 100_000}), 80)
        self.assertEqual(video_score({"median_views_top10": 50_000_000}), 100)
        self.assertIsNone(video_score(None))

    def test_low_google_volume_is_ignored_not_punished(self):
        self.assertIsNone(trend_score({"momentum_pct": 3000.0, "low_volume": True}))
        m = market_score(YT, {"momentum_pct": 3000.0, "low_volume": True})
        self.assertEqual(m["score"], 80)
        self.assertTrue(m["partial"])
        self.assertTrue(any("casi no se busca" in r for r in m["reasons"]))

    def test_crowding_penalty_and_combination(self):
        crowded = dict(YT, over_1m=5)
        self.assertEqual(market_score(crowded, None)["score"], 65)  # 80 - 15
        both = market_score(YT, {"momentum_pct": 30.0, "low_volume": False})
        self.assertEqual(both["score"], 88)  # 0.6*80 + 0.4*100

    def test_no_measurement_means_no_score(self):
        m = market_score(None, None)
        self.assertIsNone(m["score"])
        self.assertIn("sin datos", " ".join(m["reasons"]))


class TestVerdict(unittest.TestCase):
    def test_base_verdicts(self):
        self.assertEqual(verdict("WINNER", 70)["code"], "LANZAR")
        self.assertEqual(verdict("WINNER", 50)["code"], "PROBAR")
        self.assertEqual(verdict("CONTENDER", 70)["code"], "PROBAR")
        self.assertEqual(verdict("CONTENDER", 50)["code"], "VIGILAR")
        self.assertEqual(verdict("DISQUALIFIED", 99)["code"], "DESCARTAR")

    def test_never_launch_without_market_data(self):
        self.assertEqual(verdict("WINNER", None)["code"], "VIGILAR")

    def test_in_store_retire_rule(self):
        self.assertEqual(verdict("WINNER", 70, in_store=True)["code"], "MANTENER")
        self.assertEqual(verdict("DISQUALIFIED", 70, in_store=True)["code"], "RETIRAR")
        cooling = verdict("WINNER", 30, in_store=True, recent_verdicts=["VIGILAR"])
        self.assertEqual(cooling["code"], "MANTENER")
        self.assertIn("1 corrida", cooling["why"])
        self.assertEqual(verdict("WINNER", 30, in_store=True, recent_verdicts=["VIGILAR", "VIGILAR"])["code"], "RETIRAR")
        # it bounced back once: the streak is broken
        self.assertEqual(verdict("WINNER", 30, in_store=True, recent_verdicts=["VIGILAR", "LANZAR"])["code"], "MANTENER")


class TestYouTubeParsing(unittest.TestCase):
    def test_parse_views(self):
        self.assertEqual(parse_views("68K views"), 68_000)
        self.assertEqual(parse_views("1.2M views"), 1_200_000)
        self.assertEqual(parse_views("2,306 views"), 2_306)
        self.assertEqual(parse_views("1 view"), 1)
        self.assertEqual(parse_views("No views"), 0)
        self.assertIsNone(parse_views("Streamed live"))

    def test_extract_and_summarize(self):
        def short(vid, title, views):
            return {"shortsLockupViewModel": {
                "overlayMetadata": {"primaryText": {"content": title}, "secondaryText": {"content": views}},
                "onTap": {"innertubeCommand": {"reelWatchEndpoint": {"videoId": vid}}}}}
        page = {"contents": [short("a", "A", "3.8M views"), {"x": [short("b", "B", "68K views")]},
                             short("a", "A dup", "3.8M views"), short("c", "C", "1,000 views")]}
        shorts = extract_shorts(page)
        self.assertEqual([s["url"][-1] for s in shorts], ["a", "b", "c"])
        s = summarize("kw", shorts)
        self.assertEqual((s["median_views_top10"], s["over_1m"], s["over_100k"], s["status"]), (68_000, 1, 1, LIVE))
        with self.assertRaises(NoLiveDataError):
            summarize("kw", [])


class TestTrendsFallback(unittest.TestCase):
    def test_google_refusal_uses_last_real_measurement_dated_and_never_too_old(self):
        import time as _time
        from hunter.hunter_engine import HunterEngine
        from hunter.provenance import CACHED
        from hunter.user_products import product_to_candidate
        from tests.test_user_products import TODAY, product

        engine = HunterEngine(offline_mode=False)
        live = {"momentum_pct": 12.0, "timeline_data": [40, 50, 60], "low_volume": False, "status": LIVE}
        with patch.object(engine.trends_scraper, "get_trend_analysis", return_value=live):
            engine.harvest_products([product_to_candidate(product(), today=TODAY)])
        self.assertIn("steamy pet brush", engine.trends_cache)

        refused = NoLiveDataError("GoogleTrendsScraper", "HTTP 429 (rate limit)")
        cand = product_to_candidate(product(), today=TODAY)
        with patch.object(engine.trends_scraper, "get_trend_analysis", side_effect=refused):
            engine.harvest_products([cand])
        self.assertEqual(cand.data_status["trends"], CACHED)
        self.assertEqual(cand.trends_series, [40, 50, 60])
        self.assertIn("measured_at", cand.trends_meta)

        engine.trends_cache["steamy pet brush"]["_measured_ts"] = _time.time() - 8 * 86400  # too old
        engine.google_paused = False
        cand = product_to_candidate(product(), today=TODAY)
        with patch.object(engine.trends_scraper, "get_trend_analysis", side_effect=refused):
            engine.harvest_products([cand])
        self.assertEqual(cand.data_status["trends"], NO_LIVE_DATA)
        self.assertIsNone(cand.trends_series)


class TestGoogleCourtesy(unittest.TestCase):
    """Google flags networks that ask too often (429 + CAPTCHA): ask once a day, pause after a block."""

    def engine(self):
        from hunter.hunter_engine import HunterEngine
        e = HunterEngine(offline_mode=False)
        e.GOOGLE_GAP_SEC = (0.0, 0.0)
        return e

    def test_fresh_measurement_is_reused_without_asking_google(self):
        e = self.engine()
        live = {"momentum_pct": 5.0, "timeline_data": [1, 2], "low_volume": False, "status": LIVE}
        with patch.object(e.trends_scraper, "get_trend_analysis", return_value=live) as g:
            e._trends("cat brush")
            again = e._trends("Cat Brush ")
        self.assertEqual(g.call_count, 1)
        self.assertEqual(again["_why"], "reciente")

    def test_block_pauses_google_on_the_pc_but_not_in_the_cloud(self):
        import os
        e = self.engine()
        refused = NoLiveDataError("GoogleTrendsScraper", "HTTP 429 (rate limit)")
        with patch.dict(os.environ, {"GITHUB_ACTIONS": ""}),              patch.object(e.trends_scraper, "get_trend_analysis", side_effect=refused) as g:
            for kw in ("a", "b", "c"):
                with self.assertRaises(NoLiveDataError):
                    e._trends(kw)
            self.assertEqual(g.call_count, 1)                 # circuit breaker: one refusal per run
            self.assertGreater(e.google_blocked_until(), 0)  # remembered for the next runs on this PC
        e.google_paused = False
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            self.assertEqual(e.google_blocked_until(), 0.0)   # the cloud gets a new IP every run


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestRadar(TempDir):
    def write_ideas(self, n=3):
        ideas = [{"id": f"i{k}", "name": f"Idea {k}", "video_keyword": f"video {k}", "trends_keyword": f"cat {k}"}
                 for k in range(n)]
        (self.tmp / "radar_ideas.json").write_text(json.dumps({"ideas": ideas}), encoding="utf-8")

    def test_measures_and_stops_asking_google_after_429(self):
        self.write_ideas(3)
        yt = MagicMock()
        yt.measure.return_value = dict(YT, shorts_found=20, top=[], status=LIVE)
        trends = MagicMock()
        trends.get_trend_analysis.side_effect = NoLiveDataError("GoogleTrendsScraper", "HTTP 429 (rate limit)")
        state = run_radar(self.tmp, trends, yt, batch=3)
        self.assertEqual(trends.get_trend_analysis.call_count, 1)  # circuit breaker
        self.assertEqual(yt.measure.call_count, 3)
        self.assertEqual({v["youtube_status"] for v in state["ideas"].values()}, {LIVE})
        rows = radar_payload(self.tmp, {"video 1"})
        self.assertEqual(rows[0]["market"]["score"], 80)
        self.assertTrue(next(r for r in rows if r["id"] == "i1")["evaluating"])

    def test_stalest_ideas_are_measured_first_and_failures_are_honest(self):
        self.write_ideas(3)
        yt = MagicMock()
        yt.measure.side_effect = NoLiveDataError("YouTubeShorts", "bloqueado")
        trends = MagicMock()
        trends.get_trend_analysis.return_value = {"momentum_pct": 12.0, "low_volume": False, "timeline_data": [1, 2]}
        trends.rising_queries.return_value = [{"query": "new thing", "growth": "Breakout"}]
        run_radar(self.tmp, trends, yt, batch=2)
        rows = {r["id"]: r for r in radar_payload(self.tmp)}
        self.assertIsNone(rows["i2"]["measured_at"])  # not reached yet
        self.assertIsNone(rows["i0"]["youtube"])       # failed -> nothing shown, never invented
        self.assertEqual(rows["i0"]["youtube_status"], NO_LIVE_DATA)
        self.assertEqual(rows["i0"]["market"]["score"], 85)  # Google only
        run_radar(self.tmp, trends, yt, batch=1)
        self.assertIsNotNone({r["id"]: r for r in radar_payload(self.tmp)}["i2"]["measured_at"])


class TestHistory(TempDir):
    def test_runs_are_unique_files_newest_first(self):
        save_run(self.tmp, "t1", {"p": {"base": "VIGILAR", "rank": 2}})
        with patch("hunter.history.time.strftime", return_value="29991231T000000Z"):
            save_run(self.tmp, "t2", {"p": {"base": "LANZAR", "rank": 1}})
        runs = load_runs(self.tmp)
        self.assertEqual([r["generated_at"] for r in runs], ["t2", "t1"])
        self.assertEqual(previous_bases(runs, "p"), ["LANZAR", "VIGILAR"])
        (self.tmp / "history" / "broken.json").write_text("{", encoding="utf-8")
        self.assertEqual(len(load_runs(self.tmp)), 2)  # unreadable file skipped, never fatal


class TestPanelProductEdits(TempDir):
    def setUp(self):
        super().setUp()
        import centinela_local
        from tests.test_user_products import product
        self.mod = centinela_local
        self.path = self.tmp / "user_products.json"
        self.path.write_text(json.dumps({"_instrucciones": ["x"], "products": [product()]}), encoding="utf-8")
        patcher = patch.object(centinela_local, "PRODUCTS", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def read(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_toggle_store_and_edit_cost_keep_everything_else(self):
        self.mod.save_product({"id": "steamfur-pro", "en_tienda": True, "unit_cost_usd": 5.1})
        data = self.read()
        p = data["products"][0]
        self.assertTrue(p["en_tienda"])
        self.assertEqual(p["unit_cost_usd"], 5.1)
        self.assertEqual(p["verified_stock"], 994)
        self.assertEqual(data["_instrucciones"], ["x"])

    def test_create_from_radar_idea_and_delete(self):
        out = self.mod.save_product({
            "name": "Cat water fountain", "category": "Mascotas", "video_keyword": "cat water fountain",
            "trends_keyword": "cat water fountain", "srp_usd": 34.99, "unit_cost_usd": 7.5, "shipping_cost_usd": 3.0,
            "shipping": {"days_min": 7, "days_max": 12, "carrier": "AliExpress Choice"},
            "rule_inputs": {"demo_visual_speed_sec": 2, "pain_level_score": 70, "retail_availability_score": 60,
                            "has_fragile_material": False, "has_sizing_requirements": False},
        })
        self.assertEqual(out["id"], "cat-water-fountain")
        created = self.read()["products"][1]
        self.assertIn("aliexpress.com/wholesale", created["source_url"])  # search link when no URL given
        self.mod.save_product({"id": "cat-water-fountain", "_delete": True})
        self.assertEqual(len(self.read()["products"]), 1)

    def test_invalid_edit_is_rejected_and_file_untouched(self):
        before = self.path.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            self.mod.save_product({"id": "steamfur-pro", "image_url": "javascript:alert(1)"})
        with self.assertRaises(ValueError):
            self.mod.save_product({"name": "x"})  # no prices / rule inputs
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)

    def test_sync_paths_includes_trends_cache_and_merges_newest_entries(self):
        self.assertIn("data/trends_cache.json", self.mod.SYNC_PATHS)
        data_dir = self.tmp / "data"
        data_dir.mkdir(exist_ok=True)
        cache_file = data_dir / "trends_cache.json"
        cache_file.write_text(json.dumps({
            "cat brush": {"keyword": "cat brush", "_measured_ts": 200.0},
            "local only": {"keyword": "local only", "_measured_ts": 150.0},
        }), encoding="utf-8")
        remote = json.dumps({
            "cat brush": {"keyword": "cat brush", "_measured_ts": 100.0},
            "cloud only": {"keyword": "cloud only", "_measured_ts": 300.0},
        })
        sync = self.mod.Sync(enabled=False)
        with patch.object(self.mod, "ROOT", self.tmp), \
             patch.object(sync, "_git", return_value=type("R", (), {"returncode": 0, "stdout": remote})()):
            sync._merge_trends_cache()
        merged = json.loads(cache_file.read_text(encoding="utf-8"))
        self.assertEqual(merged["cat brush"]["_measured_ts"], 200.0)
        self.assertEqual(merged["local only"]["_measured_ts"], 150.0)
        self.assertEqual(merged["cloud only"]["_measured_ts"], 300.0)


class TestN8nDsersBridge(TempDir):
    def setUp(self):
        super().setUp()
        from tests.test_user_products import product
        self.path = self.tmp / "user_products.json"
        self.path.write_text(json.dumps({"products": [product()]}), encoding="utf-8")

    def test_shopify_webhook_variants_and_ko_stock_alert(self):
        from hunter.n8n_bridge import bridge_status, sync_dsers_stock_payload

        res = sync_dsers_stock_payload({
            "handle": "steamfur-pro",
            "target_variant_name": "green",
            "variants": [
                {"title": "yellow", "inventory_quantity": 12, "price": "29.99"},
                {"title": "Green Mist", "inventory_quantity": 602, "price": "29.99"},
            ],
        }, products_path=self.path)
        self.assertTrue(res["ok"])
        self.assertFalse(res["has_alerts"])
        self.assertEqual(res["updated"][0]["verified_stock"], 602)
        self.assertTrue(res["updated"][0]["en_tienda"])

        # Drop stock below 100 -> KO-STOCK alert
        low = sync_dsers_stock_payload({"id": "steamfur-pro", "stock": 45}, products_path=self.path)
        self.assertTrue(low["has_alerts"])
        self.assertTrue(low["updated"][0]["ko_stock"])
        st = bridge_status(self.path)
        self.assertTrue(st["ok"])
        self.assertEqual(st["products"][0]["verified_stock"], 45)

    def test_invalid_or_unknown_product_leaves_file_untouched(self):
        from hunter.n8n_bridge import sync_dsers_stock_payload

        before = self.path.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            sync_dsers_stock_payload({"id": "unknown-id", "stock": 500}, products_path=self.path)
        with self.assertRaises(ValueError):
            sync_dsers_stock_payload({"id": "steamfur-pro", "stock": -5}, products_path=self.path)
        with self.assertRaises(ValueError):
            sync_dsers_stock_payload("not-a-dict", products_path=self.path)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            sync_dsers_stock_payload({"items": []}, products_path=self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)

    def test_boundary_stock_100_vs_99_and_supplier_cost_spike(self):
        from hunter.n8n_bridge import sync_dsers_stock_payload

        # Boundary: exactly 100 units -> OK (not ko_stock)
        ok_100 = sync_dsers_stock_payload({"id": "steamfur-pro", "stock": 100}, products_path=self.path)
        self.assertFalse(ok_100["updated"][0]["ko_stock"])
        self.assertFalse(ok_100["has_alerts"])

        # Boundary: 99 units -> KO-STOCK alert
        ko_99 = sync_dsers_stock_payload({"id": "steamfur-pro", "stock": 99}, products_path=self.path)
        self.assertTrue(ko_99["updated"][0]["ko_stock"])
        self.assertTrue(ko_99["has_alerts"])

        # Supplier cost spike -> margin & multiplier drop below 55% / 3.0x
        cost_spike = sync_dsers_stock_payload({
            "items": [{
                "id": "steamfur-pro",
                "stock": 500,
                "supplier_cost_usd": 12.50,
                "shipping_cost_usd": 4.50,
                "retail_price_usd": 29.99,
            }]
        }, products_path=self.path)
        u = cost_spike["updated"][0]
        self.assertFalse(u["ko_stock"])
        self.assertTrue(u["ko_margin"])
        self.assertTrue(u["ko_multiplier"])
        self.assertTrue(cost_spike["has_alerts"])

    def test_mobile_private_vault_gateway_cuentas_html(self):
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent
        cuentas = repo_root / "cuentas.html"
        index = repo_root / "index.html"
        self.assertTrue(cuentas.exists(), "cuentas.html must exist for mobile GitHub Pages gateway")
        html = cuentas.read_text(encoding="utf-8")
        # Ensure zero raw private credentials leak in public HTML
        self.assertNotIn("ops.steamfur@gmail.com", html)
        self.assertNotIn("proxy-pool.net", html)
        self.assertNotIn("Profile-Dolphin-", html)
        self.assertIn("🔒 Privado · Desbloquea con tu Token", html)
        # Ensure GitHub private repo API endpoint & WebP images are wired
        self.assertIn("anderssonfranco78-jpg/multi_account_hub", html)
        self.assertIn("/contents/data/negocios.json", html)
        self.assertIn("application/vnd.github.raw+json", html)
        self.assertIn("assets/images/steamfur.webp", html)
        # Ensure index.html points github.io to cuentas.html
        idx_html = index.read_text(encoding="utf-8")
        self.assertIn("? 'cuentas.html' :", idx_html)


if __name__ == "__main__":
    unittest.main()


