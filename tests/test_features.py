from __future__ import annotations

import math
import unittest
from datetime import datetime, timedelta, timezone

from dao_runtime.features import (
    atr_seed_mean_at,
    build_baseline_snapshot,
    build_feature_snapshot,
)


def synthetic_daily(count: int = 400) -> dict:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candles = []
    for index in range(count):
        close = 2000.0 + index * 0.08 + 18.0 * math.sin(index / 6.0)
        open_price = close - math.sin(index / 4.0)
        high = max(open_price, close) + 3.0
        low = min(open_price, close) - 3.0
        candles.append(
            {
                "time": (start + timedelta(days=index)).isoformat().replace("+00:00", "Z"),
                "mid": {
                    "o": f"{open_price:.6f}",
                    "h": f"{high:.6f}",
                    "l": f"{low:.6f}",
                    "c": f"{close:.6f}",
                },
                "volume": 100 + index,
                "complete": True,
            }
        )
    return {
        "instrument": "XAU_USD",
        "granularity": "D",
        "price_component": "M",
        "timestamp_semantics": "open_time",
        "candles": candles,
    }


class FeatureTests(unittest.TestCase):
    def test_atr_requires_previous_close_and_twenty_true_ranges(self) -> None:
        candles = synthetic_daily(21)["candles"]
        atr = atr_seed_mean_at(candles, 20)
        self.assertGreater(float(atr), 0)
        with self.assertRaisesRegex(ValueError, "requires 21 complete bars"):
            atr_seed_mean_at(candles, 19)

    def test_feature_and_baseline_freeze_reproducible_values(self) -> None:
        daily = synthetic_daily()
        created_at = datetime(2026, 7, 30, 12, 1, tzinfo=timezone.utc)
        feature = build_feature_snapshot(
            daily,
            manifest_id="manifest-test",
            data_cutoff="2026-07-30T12:00:00Z",
            source_snapshot_sha256="a" * 64,
            created_at=created_at,
            feature_snapshot_id="features-test",
        )
        baseline = build_baseline_snapshot(
            daily,
            data_cutoff="2026-07-30T12:00:00Z",
            source_snapshot_sha256="a" * 64,
            created_at=created_at,
            baseline_id="baseline-test",
        )
        self.assertEqual(feature["atr20"]["required_complete_bars"], 21)
        self.assertGreater(feature["atr20"]["value"], 0)
        self.assertEqual(
            sum(baseline["training"]["outcome_counts"].values()),
            baseline["training"]["sample_size"],
        )
        self.assertAlmostEqual(sum(baseline["probabilities"].values()), 1.0)
        self.assertGreaterEqual(baseline["training"]["sample_size"], 252)


if __name__ == "__main__":
    unittest.main()
