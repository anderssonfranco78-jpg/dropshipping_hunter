"""Data provenance contract: every signal is LIVE, MANUAL, MOCK or NO_LIVE_DATA.

The hunter never invents numbers. When a live source fails, scrapers raise
``NoLiveDataError`` and the engine records ``NO_LIVE_DATA`` for that signal so the
dashboard can show a red "Sin datos en vivo" alert instead of a made-up value.
"""

from __future__ import annotations

from typing import Dict

LIVE = "LIVE"                    # Fetched from the real source in this run
MANUAL = "MANUAL"                # Hand-curated seed value (not measured by the bot)
MOCK = "MOCK"                    # Deterministic fixture, only via explicit --offline (dev/tests)
NO_LIVE_DATA = "NO_LIVE_DATA"    # Source failed; value NOT refreshed, shown as "Sin datos en vivo"
UNAVAILABLE = "UNAVAILABLE"      # Source known to be retired/blocked; not queried by default (grey, no alarm)

# Operator stock verification status (data/user_products.json)
STOCK_OK = "OK"                  # >= MIN stock, verified within the freshness window
STOCK_LOW = "LOW"                # < MIN stock -> KO-STOCK (hard disqualification)
STOCK_EXPIRED = "EXPIRED"        # verified more than N days ago -> re-verify
STOCK_UNVERIFIED = "UNVERIFIED"  # no stock or no date recorded yet

# Signals tracked per candidate
SIGNALS = ("trends", "tiktok", "meta", "freight", "supplier")


class NoLiveDataError(RuntimeError):
    """Raised when a live source cannot deliver real data. Never swallowed into a fake value."""

    def __init__(self, source: str, reason: str):
        self.source = source
        self.reason = reason
        super().__init__(f"[{source}] Sin datos en vivo: {reason}")


def default_status() -> Dict[str, str]:
    """Baseline status for a seed candidate: nothing has been measured live yet."""
    return {s: MANUAL for s in SIGNALS}
