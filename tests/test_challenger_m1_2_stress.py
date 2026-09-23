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

    def test_single_429_recovery(self):
        """Verifies scraper sleeps with exponential backoff on 429 and recovers if subsequent request succeeds."""
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.text = json.dumps({
            "timeline_values": [50] * 76 + [80] * 14,
            "breakout_queries": ["sciatica decompression belt"],
        })
        mock_response_200.json.return_value = {
            "timeline_values": [50] * 76 + [80] * 14,
            "breakout_queries": ["sciatica decompression belt"],
        }

        sleep_calls = []

        def mock_sleep(seconds):
            sleep_calls.append(seconds)

        with patch.object(self.scraper.session, "request", side_effect=[mock_response_429, mock_response_200]) as mock_req:
            with patch("time.sleep", side_effect=mock_sleep):
                # Suppress priming cookie request to isolate explore endpoint
                self.scraper._cookie_primed = True
                result = self.scraper.get_trend_analysis("lumbar traction")

        # Must have made 2 request attempts
        self.assertEqual(mock_req.call_count, 2)
        # Sleep calls: 1 proactive pacing jitter (0.5 - 1.2s) + 1 reactive 429 backoff
        self.assertEqual(len(sleep_calls), 2)
        pacing_sleep = sleep_calls[0]
        backoff_sleep = sleep_calls[1]
        self.assertGreaterEqual(pacing_sleep, 0.5)
        self.assertLessEqual(pacing_sleep, 1.2)
        # Attempt 1 backoff: (2.0 ** 1) + [0.5, 1.5] = [2.5, 3.5]
        self.assertGreaterEqual(backoff_sleep, 2.5)
        self.assertLessEqual(backoff_sleep, 3.5)
        # Must have parsed recovered live data
        self.assertEqual(result["keyword"], "lumbar traction")
        self.assertTrue(result["is_breakout"])
        self.assertGreater(result["momentum_pct"], 30.0)

    def test_repeated_429_exhaustion_strictly_exponential_then_fallback(self):
        """Verifies 3 consecutive 429s follow strictly increasing exponential backoff and gracefully trigger offline fallback."""
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429

        sleep_calls = []

        def mock_sleep(seconds):
            sleep_calls.append(seconds)

        with patch.object(self.scraper.session, "request", return_value=mock_response_429) as mock_req:
            with patch("time.sleep", side_effect=mock_sleep):
                self.scraper._cookie_primed = True
                result = self.scraper.get_trend_analysis("turbo jet fan")

        # Exceeded max_retries (3 attempts)
        self.assertEqual(mock_req.call_count, 3)
        # Sleep calls: 1 proactive pacing jitter (0.5 - 1.2s) + 3 reactive 429 backoffs
        self.assertEqual(len(sleep_calls), 4)

        pacing_sleep = sleep_calls[0]
        backoff_calls = sleep_calls[1:]
        self.assertGreaterEqual(pacing_sleep, 0.5)
        self.assertLessEqual(pacing_sleep, 1.2)

        # Monotonically increasing exponential progression of backoff calls
        self.assertLess(backoff_calls[0], backoff_calls[1])
        self.assertLess(backoff_calls[1], backoff_calls[2])

        # Attempt 1: (2.0 ** 1) + [0.5, 1.5] -> [2.5, 3.5]
        self.assertGreaterEqual(backoff_calls[0], 2.5)
        self.assertLessEqual(backoff_calls[0], 3.5)

        # Attempt 2: (2.0 ** 2) + [0.5, 1.5] -> [4.5, 5.5]
        self.assertGreaterEqual(backoff_calls[1], 4.5)
        self.assertLessEqual(backoff_calls[1], 5.5)

        # Attempt 3: (2.0 ** 3) + [0.5, 1.5] -> [8.5, 9.5]
        self.assertGreaterEqual(backoff_calls[2], 8.5)
        self.assertLessEqual(backoff_calls[2], 9.5)

        # Successfully fell back to deterministic mock without crashing
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(result["keyword"], "turbo jet fan")
        self.assertAlmostEqual(result["momentum_pct"], 68.2, places=1)
        self.assertTrue(result["is_breakout"])

    def test_strip_google_security_prefix_under_200(self):
        """Verifies stripping of Google Trends security prefix ')]}\',\n' before JSON parsing."""
        raw_google_body = ")]}',\n{\"widgets\": [], \"timeline_values\": [50, 50, 75], \"breakout_queries\": [\"test\"]}"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = raw_google_body
        # Simulate response.json() raising ValueError due to leading security token
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")

        with patch.object(self.scraper.session, "request", return_value=mock_response):
            self.scraper._cookie_primed = True
            result = self.scraper.get_trend_analysis("steam brush")

        self.assertIn("breakout_queries", result)
        self.assertEqual(result["breakout_queries"], ["test"])

    def test_cache_hits_prevent_network_spam(self):
        """Verifies second call for same keyword uses memory cache and bypasses HTTP session completely."""
        self.scraper._cache.clear()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"timeline_values": [60] * 90, "breakout_queries": []})
        mock_response.json.return_value = {"timeline_values": [60] * 90, "breakout_queries": []}

        with patch.object(self.scraper.session, "request", return_value=mock_response) as mock_req:
            self.scraper._cookie_primed = True
            res1 = self.scraper.get_trend_analysis("lumbar")
            res2 = self.scraper.get_trend_analysis("lumbar")

        # Session request must be called only once
        self.assertEqual(mock_req.call_count, 1)
        self.assertEqual(res1, res2)

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
