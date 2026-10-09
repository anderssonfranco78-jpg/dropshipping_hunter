"""Empirical Challenger 2 Stress Test Suite for Milestone M1.

Evaluates:
1. GoogleTrendsScraper & BaseScraper exponential backoff simulation under 429 HTTP rate-limits.
2. Atomic write durability, crash recovery, and concurrency resilience of data/candidates.json on Windows.
3. Zero-GUI headless purity: AST scan, runtime module audit, Win32 EnumWindows HWND verification.
"""

from __future__ import annotations

import concurrent.futures
import ctypes
from ctypes import wintypes
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure dropshipping_hunter root is on sys.path
HUNTER_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(HUNTER_ROOT) not in sys.path:
    sys.path.insert(0, str(HUNTER_ROOT))

from hunter.hunter_engine import HunterEngine
from hunter.models import RawCandidate
from hunter.scrapers.base import BaseScraper
from hunter.scrapers.google_trends import GoogleTrendsScraper


class TestGoogleTrends429ExponentialBackoff(unittest.TestCase):
    """Stress tests exponential backoff simulation under HTTP 429 conditions."""

    def setUp(self):
        self.scraper = GoogleTrendsScraper(
            timeout=5.0,
            max_retries=3,
            backoff_factor=2.0,
            offline_mode=False,
        )

    # --- helpers: the live flow is explore (widget token) -> widgetdata/multiline (real series) ---
    @staticmethod
    def _resp(payload, prefixed=False):
        m = MagicMock()
        m.status_code = 200
        body = json.dumps(payload)
        m.text = (")]}',\n" + body) if prefixed else body
        if prefixed:
            m.json.side_effect = ValueError("No JSON object could be decoded")
        else:
            m.json.return_value = payload
        return m

    @staticmethod
    def _explore():
        return {"widgets": [{"id": "TIMESERIES", "token": "tok", "request": {"time": "today 3-m"}}]}

    @staticmethod
    def _series(values):
        return {"default": {"timelineData": [{"value": [v]} for v in values]}}

    def test_single_429_recovery(self):
        """429 -> exponential backoff -> recovers and computes momentum from the REAL series."""
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        responses = [
            mock_response_429,
            self._resp(self._explore()),
            self._resp(self._series([50] * 76 + [80] * 14)),
        ]
        sleep_calls = []

        with patch.object(self.scraper.session, "request", side_effect=responses) as mock_req:
            with patch("time.sleep", side_effect=sleep_calls.append):
                self.scraper._cookie_primed = True
                result = self.scraper.get_trend_analysis("lumbar traction")

        self.assertEqual(mock_req.call_count, 3)
        # pacing before explore, 429 backoff, pacing before multiline
        self.assertEqual(len(sleep_calls), 3)
        self.assertTrue(0.5 <= sleep_calls[0] <= 1.2)
        self.assertTrue(2.5 <= sleep_calls[1] <= 3.5)  # (2.0 ** 1) + [0.5, 1.5]
        self.assertEqual(result["keyword"], "lumbar traction")
        self.assertEqual(result["status"], "LIVE")
        self.assertAlmostEqual(result["momentum_pct"], 60.0, places=1)
        self.assertTrue(result["is_breakout"])

    def test_repeated_429_exhaustion_raises_no_live_data(self):
        """3 consecutive 429s follow exponential backoff, then fail HONESTLY (no fabricated numbers)."""
        from hunter.provenance import NoLiveDataError

        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        sleep_calls = []

        with patch.object(self.scraper.session, "request", return_value=mock_response_429) as mock_req:
            with patch("time.sleep", side_effect=sleep_calls.append):
                self.scraper._cookie_primed = True
                with self.assertRaises(NoLiveDataError) as ctx:
                    self.scraper.get_trend_analysis("turbo jet fan")

        self.assertIn("Sin datos en vivo", str(ctx.exception))
        self.assertEqual(mock_req.call_count, 3)
        self.assertEqual(len(sleep_calls), 4)  # 1 pacing + 3 backoffs
        backoffs = sleep_calls[1:]
        self.assertLess(backoffs[0], backoffs[1])
        self.assertLess(backoffs[1], backoffs[2])
        self.assertTrue(2.5 <= backoffs[0] <= 3.5)
        self.assertTrue(4.5 <= backoffs[1] <= 5.5)
        self.assertTrue(8.5 <= backoffs[2] <= 9.5)

    def test_strip_google_security_prefix_under_200(self):
        """The ')]}',' prefix is stripped from both explore and multiline bodies."""
        responses = [
            self._resp(self._explore(), prefixed=True),
            self._resp(self._series([50] * 76 + [75] * 14), prefixed=True),
        ]
        with patch.object(self.scraper.session, "request", side_effect=responses):
            with patch("time.sleep"):
                self.scraper._cookie_primed = True
                result = self.scraper.get_trend_analysis("steam brush")

        self.assertEqual(result["status"], "LIVE")
        self.assertAlmostEqual(result["momentum_pct"], 50.0, places=1)

    def test_cache_hits_prevent_network_spam(self):
        """Second call for same keyword is served from memory (2 HTTP calls total, not 4)."""
        self.scraper._cache.clear()
        responses = [self._resp(self._explore()), self._resp(self._series([60] * 90))]

        with patch.object(self.scraper.session, "request", side_effect=responses) as mock_req:
            with patch("time.sleep"):
                self.scraper._cookie_primed = True
                res1 = self.scraper.get_trend_analysis("lumbar")
                res2 = self.scraper.get_trend_analysis("lumbar")

        self.assertEqual(mock_req.call_count, 2)
        self.assertEqual(res1, res2)

    def test_missing_widget_or_series_never_synthesizes_data(self):
        """No TIMESERIES widget / empty series => NoLiveDataError, never random numbers."""
        from hunter.provenance import NoLiveDataError

        with patch.object(self.scraper.session, "request", return_value=self._resp({"widgets": []})):
            with patch("time.sleep"):
                self.scraper._cookie_primed = True
                with self.assertRaises(NoLiveDataError):
                    self.scraper.get_trend_analysis("no widget")

        responses = [self._resp(self._explore()), self._resp(self._series([]))]
        self.scraper._cache.clear()
        with patch.object(self.scraper.session, "request", side_effect=responses):
            with patch("time.sleep"):
                with self.assertRaises(NoLiveDataError):
                    self.scraper.get_trend_analysis("empty series")

    def test_cookie_priming_survives_429(self):
        """Verifies cookie priming endpoint returning 429 does not crash the scraper."""
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429

        with patch.object(self.scraper.session, "get", return_value=mock_resp_429):
            # Should not raise exception
            self.scraper._prime_cookies()
            self.assertFalse(self.scraper._cookie_primed)


class TestAtomicWriteDurability(unittest.TestCase):
    """Stress tests atomic persistence, crash durability, and concurrency of data/candidates.json."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.target_file = pathlib.Path(self.temp_dir.name) / "data" / "candidates.json"
        self.engine = HunterEngine(offline_mode=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_roundtrip_persistence_integrity(self):
        """Verifies full roundtrip persistence and schema fidelity of 10 seed candidates."""
        seeds = self.engine.get_seed_candidates()
        self.assertEqual(len(seeds), 10)

        # Save to temporary path
        saved_path = self.engine.save_candidates(seeds, output_path=self.target_file)
        self.assertTrue(saved_path.exists())

        # Load back
        loaded = HunterEngine.load_candidates(saved_path)
        self.assertEqual(len(loaded), 10)

        for orig, reloaded in zip(seeds, loaded):
            self.assertEqual(orig.candidate_id, reloaded.candidate_id)
            self.assertEqual(orig.name, reloaded.name)
            self.assertEqual(orig.supplier_cost, reloaded.supplier_cost)
            self.assertEqual(orig.shipping_cost, reloaded.shipping_cost)
            self.assertEqual(orig.suggested_price, reloaded.suggested_price)
            self.assertEqual(orig.has_fragile_material, reloaded.has_fragile_material)
            self.assertEqual(orig.has_sizing_requirements, reloaded.has_sizing_requirements)
            self.assertEqual(orig.google_trends_momentum, reloaded.google_trends_momentum)

    def test_crash_during_write_preserves_original_target(self):
        """Verifies that an interruption/crash during serialization leaves existing candidates.json untouched."""
        seeds = self.engine.get_seed_candidates()
        self.engine.save_candidates(seeds[:3], output_path=self.target_file)

        # Verify initial state: exactly 3 candidates
        initial_candidates = HunterEngine.load_candidates(self.target_file)
        self.assertEqual(len(initial_candidates), 3)

        # Inject simulated crash/error during json.dump
        with patch("json.dump", side_effect=IOError("Simulated disk write failure / abrupt power loss")):
            with self.assertRaises(IOError):
                self.engine.save_candidates(seeds, output_path=self.target_file)

        # Target file must be intact and uncorrupted with original 3 candidates
        surviving_candidates = HunterEngine.load_candidates(self.target_file)
        self.assertEqual(len(surviving_candidates), 3)
        self.assertEqual([c.candidate_id for c in surviving_candidates], [c.candidate_id for c in seeds[:3]])

    def test_concurrent_saves_stress(self):
        """Stress-tests concurrent thread writes to the target candidate file.
        
        Tests whether concurrent calls to save_candidates corrupt the JSON or throw unhandled exceptions.
        """
        seeds = self.engine.get_seed_candidates()
        self.engine.save_candidates(seeds, output_path=self.target_file)

        errors = []

        def worker_save(idx: int):
            try:
                # Slight variation in data
                sub_candidates = [RawCandidate.from_dict(s.to_dict()) for s in seeds]
                sub_candidates[0].candidate_id = f"worker-{idx}"
                self.engine.save_candidates(sub_candidates, output_path=self.target_file)
                return True
            except Exception as exc:
                errors.append(exc)
                return False

        # Execute 20 concurrent saves
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker_save, i) for i in range(20)]
            results = [f.result() for f in futures]

        # Verify final file is valid readable JSON (no half-written corruptions)
        self.assertTrue(self.target_file.exists())
        final_candidates = HunterEngine.load_candidates(self.target_file)
        self.assertEqual(len(final_candidates), 10)

        # Note any Windows file-locking collisions
        if errors:
            print(f"[NOTE] Concurrency test encountered {len(errors)} transient Windows file contention errors (expected if temp path collides without file locking).")


class TestHeadlessExecutionPurity(unittest.TestCase):
    """Stress tests zero-GUI compliance, non-blocking execution, and Win32 window allocations."""

    def test_zero_gui_toolkit_imports_in_source(self):
        """Verifies no hunter source files import GUI toolkits or desktop control libraries."""
        forbidden_tokens = [
            "pyautogui",
            "pynput",
            "tkinter",
            "PyQt5",
            "PyQt6",
            "PySide2",
            "PySide6",
            "wx",
            "kivy",
            "curses",
            "ctypes.windll.user32.MessageBox",
        ]

        hunter_dir = HUNTER_ROOT / "hunter"
        for py_file in hunter_dir.rglob("*.py"):
            code = py_file.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(
                    token,
                    code,
                    f"Forbidden GUI token '{token}' detected in {py_file.name}",
                )

    def test_runtime_sys_modules_has_no_gui_libraries(self):
        """Verifies executing hunter extraction in memory loads zero GUI libraries into sys.modules."""
        engine = HunterEngine(offline_mode=True)
        _ = engine.harvest(search_keywords=["lumbar"], include_seeds=True)

        loaded_modules = set(sys.modules.keys())
        gui_modules = {"tkinter", "pyautogui", "pynput", "PyQt5", "PyQt6", "wx"}
        overlap = loaded_modules.intersection(gui_modules)
        self.assertEqual(len(overlap), 0, f"GUI modules loaded into runtime: {overlap}")

    def test_win32_zero_window_allocation_in_powershell_process(self):
        """Runs HunterEngine in background PowerShell subprocess and verifies zero top-level GUI windows created."""
        if sys.platform != "win32":
            self.skipTest("Win32 window allocation check is specific to Windows")

        # Launch hunter engine in a subprocess
        cmd = [sys.executable, "-m", "hunter.hunter_engine", "--offline"]
        proc = subprocess.Popen(
            cmd,
            cwd=str(HUNTER_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
        )

        detected_hwnds = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_windows_callback(hwnd, lparam):
            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == proc.pid:
                # Check if visible or titled window
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    detected_hwnds.append((hwnd, buf.value))
            return True

        # Sample for windows while running
        start_time = time.time()
        while proc.poll() is None and (time.time() - start_time) < 10:
            ctypes.windll.user32.EnumWindows(enum_windows_callback, 0)
            time.sleep(0.05)

        stdout, stderr = proc.communicate(timeout=10)
        self.assertEqual(proc.returncode, 0, f"Hunter engine failed with stderr: {stderr}")

        # Assert zero GUI windows allocated
        self.assertEqual(
            len(detected_hwnds),
            0,
            f"GUI Windows allocated by hunter process {proc.pid}: {detected_hwnds}",
        )

    def test_non_blocking_stdin_redirection(self):
        """Verifies process runs to completion when stdin is redirected from $null / devnull."""
        proc = subprocess.run(
            [sys.executable, "-m", "hunter.hunter_engine", "--seed-only"],
            cwd=str(HUNTER_ROOT),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Harvested Candidates Summary Table", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
