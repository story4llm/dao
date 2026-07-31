from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dao_runtime.bundle import validate_bundle
from dao_runtime.contracts import (
    canonical_payload_sha256,
    schema_errors,
    write_json,
)
from dao_runtime.futures import _validate_contract_spec, prepare_gc_bundle


CONTRACT_CODE = "GCZ26"
CUTOFF = "2025-10-28T22:00:00Z"
AS_OF = "2025-10-28T22:05:00Z"
CAPTURED = "2025-10-28T21:59:00Z"
RESOLUTION_SESSIONS = [
    f"2025-11-{day:02d}T18:30:00Z" for day in (3, 4, 5, 6, 7)
]


def _contract_spec(**overrides: object) -> dict:
    payload = {
        "product_code": "GC",
        "contract_code": CONTRACT_CODE,
        "venue": "COMEX",
        "contract_month": "2026-12",
        "first_position_date": "2026-11-30",
        "last_trade_date": "2026-12-29",
        "contract_size_oz": 100,
        "tick_size": 0.1,
        "currency": "USD",
        "price_unit": "troy_ounce",
        "continuous": False,
        "roll_policy": "none",
    }
    payload.update(overrides)
    return payload


def _daily_source() -> dict:
    start = datetime(2025, 1, 1, 18, 30, tzinfo=timezone.utc)
    records = []
    for index in range(300):
        center = 2600 + index * 0.7 + ((index % 11) - 5) * 0.35
        records.append(
            {
                "time": (start + timedelta(days=index)).isoformat().replace(
                    "+00:00", "Z"
                ),
                "available_at": (
                    start + timedelta(days=index, hours=1)
                ).isoformat().replace("+00:00", "Z"),
                "o": f"{center - 0.2:.2f}",
                "h": f"{center + 1.4:.2f}",
                "l": f"{center - 1.3:.2f}",
                "settlement": f"{center:.2f}",
                "volume": 1000 + index,
                "open_interest": 5000 + index,
                "complete": True,
            }
        )
    return {"contract_code": CONTRACT_CODE, "records": records}


def _h4_source() -> dict:
    start = datetime(2025, 10, 20, 0, 0, tzinfo=timezone.utc)
    records = []
    for index in range(40):
        center = 2800 + index * 0.2
        records.append(
            {
                "time": (start + timedelta(hours=4 * index))
                .isoformat()
                .replace("+00:00", "Z"),
                "available_at": (start + timedelta(hours=4 * index + 4))
                .isoformat()
                .replace("+00:00", "Z"),
                "o": f"{center - 0.1:.2f}",
                "h": f"{center + 0.8:.2f}",
                "l": f"{center - 0.7:.2f}",
                "c": f"{center:.2f}",
                "volume": 100 + index,
                "complete": True,
            }
        )
    return {"contract_code": CONTRACT_CODE, "records": records}


def _write_gc_config(root: Path) -> Path:
    spec_path = root / "instrument-spec.json"
    daily_path = root / "daily.json"
    h4_path = root / "h4.json"
    calendar_path = root / "calendar.json"
    write_json(spec_path, _contract_spec())
    write_json(daily_path, _daily_source())
    write_json(h4_path, _h4_source())
    write_json(
        calendar_path,
        {
            "contract_code": CONTRACT_CODE,
            "calendar_id": "cme-gc-settlement",
            "calendar_version": "0.1.0",
            "resolution_sessions": RESOLUTION_SESSIONS,
        },
    )
    source_files = {}
    for role, path in (
        ("instrument_spec", spec_path),
        ("price_daily", daily_path),
        ("price_h4", h4_path),
        ("contract_calendar", calendar_path),
    ):
        source_files[role] = {
            "path": str(path),
            "source_locator": f"https://licensed.example.test/{role}",
            "captured_at": CAPTURED,
            "available_at": CAPTURED,
            "source_timezone": "America/Chicago",
            "freshness_max_seconds": 3600,
        }
    official_snapshots = []
    for role in ("macro_rates", "macro_usd", "event_clock"):
        path = root / f"{role}.json"
        write_json(path, {"role": role})
        official_snapshots.append(
            {
                "role": role,
                "path": str(path),
                "source_locator": f"https://agency.gov/{role}",
                "captured_at": CAPTURED,
                "available_at": CAPTURED,
                "observed_at": (
                    "2025-11-07T13:30:00Z"
                    if role == "event_clock"
                    else CAPTURED
                ),
                "source_timezone": "UTC",
                "timestamp_semantics": (
                    "event_time" if role == "event_clock" else "publication_time"
                ),
                "record_count": 1,
                "freshness_max_seconds": 3600,
            }
        )
    config = {
        "run_id": "run-gcz26-test",
        "contract_code": CONTRACT_CODE,
        "as_of": AS_OF,
        "data_cutoff": CUTOFF,
        "resolution_sessions": RESOLUTION_SESSIONS,
        "previous_frame": None,
        "licence": {
            "name": "Synthetic CME licence fixture",
            "region_or_entity": "test entity",
            "version_or_effective_date": "2025-01-01",
            "locator": "https://licensing.example.test/cme",
            "usage_scope": "internal_evaluation",
            "accepted_by_account_holder": True,
            "verified_at": CAPTURED,
        },
        "source_files": source_files,
        "official_snapshots": official_snapshots,
    }
    config_path = root / "config.json"
    write_json(config_path, config)
    return config_path


def _gc_forecast(public_dir: Path) -> dict:
    feature = json.loads((public_dir / "feature-snapshot.json").read_text())
    baseline = json.loads((public_dir / "baseline-snapshot.json").read_text())
    manifest = json.loads((public_dir / "evidence-manifest.json").read_text())
    contract = manifest["futures_contract"]
    return {
        "contract_version": "2.2.0",
        "forecast_id": "forecast-gcz26",
        "frame_id": "frame-gcz26",
        "question": "Which GCZ26 five-session settlement outcome resolves?",
        "instrument": CONTRACT_CODE,
        "created_at": AS_OF,
        "data_cutoff": CUTOFF,
        "horizon": {
            "unit": "completed_trading_session",
            "primary_sessions": 5,
            "diagnostic_sessions": [3],
            "starts_after_cutoff": True,
        },
        "outcomes": [
            {
                "outcome_id": outcome,
                "description": f"GCZ26 {outcome} outcome.",
                "probability": baseline["probabilities"][outcome],
            }
            for outcome in ("up", "down", "range")
        ],
        "baseline": {
            "baseline_ref": "baseline-snapshot.json",
            "method": "rolling_historical_frequency",
            "probabilities": baseline["probabilities"],
            "version": "gc-baseline:0.1.0",
            "sample_size": baseline["training"]["sample_size"],
            "training_start": baseline["training"]["start_session"],
            "training_end": baseline["training"]["end_session"],
            "frozen_at": baseline["provenance"]["created_at"],
            "source_snapshot_sha256": baseline["source_daily_snapshot_sha256"],
        },
        "evidence_refs": ["e-gc-price"],
        "counterevidence_refs": [],
        "resolution_rule": {
            "protocol_id": "gc-single-contract-direction-5d:0.1.0",
            "reference_price_field": "settlement",
            "normalizer": {
                "method": "wilder_atr_seed_mean",
                "lookback_sessions": 20,
                "freeze_at_cutoff": True,
            },
            "neutral_band_atr_multiple": 0.5,
            "boundary_policy": "inclusive_range",
            "missing_data_policy": "mark_unresolvable",
            "frozen_values": {
                "feature_snapshot_ref": "feature-snapshot.json",
                "feature_payload_sha256": feature["feature_payload_sha256"],
                "reference_session": feature["reference_session"],
                "reference_close": feature["reference_close"],
                "atr20_at_cutoff": feature["atr20"]["value"],
                "price_component": "SETTLEMENT",
                "daily_alignment": None,
                "alignment_timezone": "America/Chicago",
                "calendar_id": "cme-gc-settlement",
                "calendar_version": "0.1.0",
                "contract_code": CONTRACT_CODE,
                "first_position_date": contract["first_position_date"],
                "last_trade_date": contract["last_trade_date"],
                "resolution_session_sequence_sha256": contract[
                    "resolution_session_sequence_sha256"
                ],
            },
        },
        "invalidation_conditions": [
            "The frozen contract calendar or settlement series is invalid."
        ],
        "forecast_abstention": {
            "abstain": False,
            "reason_codes": [],
            "reason": None,
        },
        "status": "open",
        "model_versions": ["gc-baseline-only:0.1.0"],
    }


class FuturesPreparationTests(unittest.TestCase):
    def test_single_contract_gc_ready_bundle_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public_dir = root / "public"
            private_dir = root / "private"
            prepare_gc_bundle(
                _write_gc_config(root),
                public_dir,
                private_dir,
            )

            self.assertEqual(
                validate_bundle(
                    public_dir,
                    private_root=private_dir,
                    raise_on_error=False,
                ),
                [],
            )
            feature = json.loads((public_dir / "feature-snapshot.json").read_text())
            baseline = json.loads((public_dir / "baseline-snapshot.json").read_text())
            manifest = json.loads((public_dir / "evidence-manifest.json").read_text())
            self.assertEqual(feature["reference_price_field"], "settlement")
            self.assertEqual(feature["instrument"], CONTRACT_CODE)
            self.assertEqual(
                baseline["protocol_id"],
                "gc-single-contract-direction-5d:0.1.0",
            )
            self.assertFalse(manifest["futures_contract"]["continuous"])

    def test_continuous_contract_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "continuous"):
            _validate_contract_spec(
                _contract_spec(continuous=True),
                CONTRACT_CODE,
                RESOLUTION_SESSIONS,
                CUTOFF,
            )

    def test_forecast_window_must_precede_delivery_lifecycle(self) -> None:
        with self.assertRaisesRegex(ValueError, "forecast window"):
            _validate_contract_spec(
                _contract_spec(first_position_date="2025-11-06"),
                CONTRACT_CODE,
                RESOLUTION_SESSIONS,
                CUTOFF,
            )

    def test_contract_month_must_match_contract_code(self) -> None:
        with self.assertRaisesRegex(ValueError, "contract_month"):
            _validate_contract_spec(
                _contract_spec(contract_month="2026-08"),
                CONTRACT_CODE,
                RESOLUTION_SESSIONS,
                CUTOFF,
            )

    def test_gc_feature_cannot_use_spot_price_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public_dir = root / "public"
            private_dir = root / "private"
            prepare_gc_bundle(_write_gc_config(root), public_dir, private_dir)
            feature_path = public_dir / "feature-snapshot.json"
            feature = json.loads(feature_path.read_text())
            feature["reference_price_field"] = "mid.c"
            feature["feature_payload_sha256"] = canonical_payload_sha256(
                feature, "feature_payload_sha256"
            )
            write_json(feature_path, feature)

            errors = validate_bundle(
                public_dir,
                private_root=private_dir,
                raise_on_error=False,
            )
            self.assertTrue(
                any("reference_price_field" in error for error in errors),
                errors,
            )

    def test_gc_forecast_contract_freezes_contract_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public_dir = root / "public"
            private_dir = root / "private"
            prepare_gc_bundle(_write_gc_config(root), public_dir, private_dir)
            forecast = _gc_forecast(public_dir)
            self.assertEqual(
                schema_errors(
                    forecast,
                    "forecast-contract.schema.json",
                    "forecast-gcz26",
                ),
                [],
            )

            forecast["resolution_rule"]["protocol_id"] = (
                "xauusd-direction-5d:0.2.0"
            )
            self.assertTrue(
                schema_errors(
                    forecast,
                    "forecast-contract.schema.json",
                    "forecast-gcz26-cross-track",
                )
            )
            forecast["resolution_rule"]["protocol_id"] = (
                "gc-single-contract-direction-5d:0.1.0"
            )
            del forecast["resolution_rule"]["frozen_values"]["first_position_date"]
            self.assertTrue(
                schema_errors(
                    forecast,
                    "forecast-contract.schema.json",
                    "forecast-gcz26-invalid",
                )
            )

    def test_gc_manifest_requires_contract_calendar_role(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public_dir = root / "public"
            private_dir = root / "private"
            prepare_gc_bundle(_write_gc_config(root), public_dir, private_dir)
            manifest_path = public_dir / "evidence-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["snapshots"] = [
                item
                for item in manifest["snapshots"]
                if item["role"] != "contract_calendar"
            ]
            write_json(manifest_path, manifest)

            errors = validate_bundle(
                public_dir,
                private_root=private_dir,
                raise_on_error=False,
            )
            self.assertTrue(
                any("contract_calendar" in error for error in errors),
                errors,
            )

    def test_completed_gc_cognition_bundle_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public_dir = root / "public"
            private_dir = root / "private"
            prepare_gc_bundle(_write_gc_config(root), public_dir, private_dir)
            baseline = json.loads((public_dir / "baseline-snapshot.json").read_text())
            probabilities = baseline["probabilities"]
            evidence = [
                {
                    "evidence_id": "e-gc-price",
                    "layer": "market",
                    "kind": "observation",
                    "claim": "Synthetic GCZ26 settlement inputs were frozen.",
                    "dependency_group": "gc-settlement-fixture",
                    "source": {
                        "title": "Synthetic licensed GC fixture",
                        "author": None,
                        "locator": "private://gc-d-canonical.json",
                        "published_at": None,
                        "accessed_at": CAPTURED,
                    },
                    "source_timezone": "America/Chicago",
                    "bar_timestamp_semantics": "close_time",
                    "observed_at": CAPTURED,
                    "available_at": CAPTURED,
                    "recorded_at": CAPTURED,
                    "availability_verified": True,
                    "vintage_id": "gc-fixture-v1",
                    "licence": {
                        "name": "Synthetic fixture",
                        "usage_scope": "internal_evaluation",
                        "locator": None,
                        "verified": True,
                    },
                    "quality": {
                        "reliability": 1.0,
                        "independence": 1.0,
                        "freshness": 1.0,
                        "notes": [],
                    },
                    "tags": ["test", "gc"],
                }
            ]
            scenarios = [
                {
                    "scenario_id": f"scenario-{outcome}",
                    "resolution_outcome_id": outcome,
                    "description": f"Synthetic GCZ26 {outcome} outcome.",
                    "probability": probabilities[outcome],
                    "triggers": [f"Synthetic {outcome} trigger."],
                }
                for outcome in ("up", "down", "range")
            ]
            frame = {
                "frame_id": "frame-gcz26",
                "instrument": CONTRACT_CODE,
                "as_of": AS_OF,
                "data_cutoff": CUTOFF,
                "horizon": "5 completed COMEX settlement sessions",
                "state": {
                    "direction": "range",
                    "lifecycle": "maturity",
                    "stability": "stable",
                    "posterior": {"up": 0.3, "down": 0.3, "range": 0.4},
                },
                "change_model": {
                    "xing": "synthetic single-contract fixture",
                    "shi": 0.0,
                    "ji": 0.5,
                    "shi_temporal": "test-only",
                    "wei": "maturity",
                    "xin": 0.5,
                },
                "evidence_refs": ["e-gc-price"],
                "counterevidence_refs": [],
                "scenarios": scenarios,
                "invalidation_conditions": ["Fixture integrity fails."],
                "risk": {
                    "level": "medium",
                    "research_posture": "observe",
                    "warnings": ["Synthetic GC test only."],
                },
                "abstention": {
                    "state": {"abstain": False, "reason_codes": [], "reason": None},
                    "forecast": {
                        "abstain": False,
                        "reason_codes": [],
                        "reason": None,
                    },
                },
                "data_gaps": [],
                "provenance": {
                    "data_snapshot": "evidence-manifest.json",
                    "feature_version": "features-run-gcz26-test",
                    "model_versions": ["gc-baseline-only:0.1.0"],
                    "prompt_version": "daily-cognition-run:0.3.0",
                    "contract_version": "2.2.0",
                    "certification_level": "Q1",
                    "resolution_protocol_version": (
                        "gc-single-contract-direction-5d:0.1.0"
                    ),
                },
            }
            write_json(public_dir / "evidence-items.json", evidence)
            write_json(public_dir / "market-cognition-frame.json", frame)
            write_json(public_dir / "forecast-contract.json", _gc_forecast(public_dir))
            (public_dir / "explanation.md").write_text(
                "Synthetic GC cognition fixture.\n", encoding="utf-8"
            )
            run_path = public_dir / "run.json"
            run = json.loads(run_path.read_text())
            run["status"] = "completed"
            run["outputs"].update(
                {
                    "evidence_items": "evidence-items.json",
                    "frame": "market-cognition-frame.json",
                    "forecast": "forecast-contract.json",
                    "explanation": "explanation.md",
                }
            )
            write_json(run_path, run)

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
