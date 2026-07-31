from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from dao_runtime.bundle import validate_bundle
from dao_runtime.oanda import (
    _contains_placeholder,
    _copy_official_snapshot,
    _request_official,
    prepare_private_bundle,
)
from tests.test_features import synthetic_daily


class OandaPreparationTests(unittest.TestCase):
    def test_official_snapshot_missing_path_is_downloaded_from_allowlisted_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            private_dir = Path(temp)
            item = {
                "role": "macro_rates",
                "source_locator": "https://home.treasury.gov/official.xml",
                "observed_at": "2026-07-30T00:00:00Z",
                "source_timezone": "America/New_York",
                "timestamp_semantics": "publication_time",
                "freshness_max_seconds": 345600,
            }
            with (
                patch("dao_runtime.oanda._request_official", return_value=b"<feed/>"),
                patch(
                    "dao_runtime.oanda.utc_now",
                    return_value=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
                ),
            ):
                snapshot = _copy_official_snapshot(item, private_dir)
            self.assertEqual(snapshot["available_at"], "2026-07-30T12:00:00.000000Z")
            self.assertTrue((private_dir / "official-macro_rates.xml").is_file())
            self.assertEqual(snapshot["bytes"], 7)

    def test_official_snapshot_rejects_non_official_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            _request_official("https://example.org/snapshot.json")

    def test_placeholder_check_does_not_reject_ordinary_replace_text(self) -> None:
        self.assertFalse(
            _contains_placeholder(
                {"licence": {"locator": "https://legal.example.org/replace-policy"}}
            )
        )
        self.assertTrue(_contains_placeholder({"name": "REPLACE with agreement name"}))
        self.assertTrue(_contains_placeholder({"name": "REPLACE_ME"}))
        self.assertTrue(
            _contains_placeholder({"locator": "https://example.com/agreement"})
        )

    def test_config_with_credentials_is_rejected_before_network_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "run_id": "run-secret-test",
                        "environment": "practice",
                        "token": "must-not-be-here",
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "OANDA_API_TOKEN": "environment-token",
                    "OANDA_ACCOUNT_ID": "environment-account",
                },
                clear=False,
            ):
                with self.assertRaisesRegex(
                    ValueError, "credentials must not appear"
                ):
                    prepare_private_bundle(
                        config_path, root / "public", root / "private"
                    )

    def test_private_preparation_uses_environment_and_emits_valid_ready_run(self) -> None:
        daily = synthetic_daily()
        h4 = copy.deepcopy(daily)
        h4["granularity"] = "H4"
        h4["candles"] = h4["candles"][-300:]
        instrument = {"instruments": [{"name": "XAU_USD", "displayName": "Gold"}]}

        def fake_request(url: str, token: str):
            self.assertEqual(token, "test-token-not-written")
            if "/candles?" in url and "granularity=D" in url:
                payload = daily
            elif "/candles?" in url and "granularity=H4" in url:
                payload = h4
            elif "/accounts/" in url:
                payload = instrument
            else:
                self.fail(f"unexpected URL: {url}")
            return json.dumps(payload).encode(), payload, "request-fixture"

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            official = {}
            for role in ("macro_rates", "macro_usd", "event_clock"):
                path = root / f"{role}.json"
                path.write_text(json.dumps({"role": role}), encoding="utf-8")
                official[role] = path
            config = {
                "run_id": "run-preparation-test",
                "environment": "practice",
                "previous_frame": None,
                "licence": {
                    "name": "Regional OANDA API agreement",
                    "region_or_entity": "test entity",
                    "version_or_effective_date": "2026-01-01",
                    "locator": "https://legal.oanda.com/agreement",
                    "usage_scope": "internal_evaluation",
                    "accepted_by_account_holder": True,
                    "verified_at": "2026-07-30T00:00:00Z",
                },
                "official_snapshots": [
                    {
                        "role": role,
                        "path": str(official[role]),
                        "source_locator": f"https://agency.gov/{role}",
                        "captured_at": "2026-07-30T00:00:00Z",
                        "available_at": "2026-07-30T00:00:00Z",
                        "observed_at": "2026-07-30T00:00:00Z",
                        "source_timezone": "UTC",
                        "timestamp_semantics": (
                            "event_time" if role == "event_clock" else "publication_time"
                        ),
                        "record_count": 1,
                        "freshness_max_seconds": 345600,
                    }
                    for role in ("macro_rates", "macro_usd", "event_clock")
                ],
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            public_dir = root / "public"
            private_dir = root / "private"
            with (
                patch.dict(
                    os.environ,
                    {
                        "OANDA_API_TOKEN": "test-token-not-written",
                        "OANDA_ACCOUNT_ID": "test-account-not-written",
                    },
                    clear=False,
                ),
                patch("dao_runtime.oanda._request_json", side_effect=fake_request),
                patch(
                    "dao_runtime.oanda.utc_now",
                    return_value=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
                ),
            ):
                prepare_private_bundle(config_path, public_dir, private_dir)

            public_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in public_dir.glob("*")
                if path.is_file()
            )
            self.assertNotIn("test-token-not-written", public_text)
            self.assertNotIn("test-account-not-written", public_text)
            self.assertEqual(
                validate_bundle(
                    public_dir,
                    private_root=private_dir,
                    raise_on_error=False,
                ),
                [],
            )


if __name__ == "__main__":
    unittest.main()
