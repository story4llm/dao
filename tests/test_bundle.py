from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dao_runtime.bundle import validate_bundle
from dao_runtime.contracts import (
    canonical_payload_sha256,
    schema_errors,
    sha256_file,
    write_json,
)
from dao_runtime.features import build_baseline_snapshot, build_feature_snapshot
from tests.test_features import synthetic_daily


CUTOFF = "2026-07-30T12:00:00Z"
AS_OF = "2026-07-30T12:02:00Z"
CAPTURED = "2026-07-30T11:59:00Z"


def _private_snapshot(private_root: Path, name: str, payload: object) -> tuple[Path, str]:
    path = private_root / name
    write_json(path, payload)
    return path, sha256_file(path)


def _snapshot(
    role: str,
    path: Path,
    digest: str,
    *,
    record_count: int = 1,
    first_observed_at: str = CAPTURED,
    last_observed_at: str = CAPTURED,
    timestamp_semantics: str = "publication_time",
) -> dict:
    return {
        "snapshot_id": f"snapshot-{role}",
        "role": role,
        "private_location_ref": f"private://{path.name}",
        "request_locator_redacted": f"https://official.example/{role}",
        "request_id": "request-test" if role.startswith("price_") else None,
        "source_locator": f"https://official.example/{role}",
        "captured_at": CAPTURED,
        "available_at": CAPTURED,
        "sha256": digest,
        "source_response_location_ref": f"private://{path.name}",
        "source_response_sha256": digest,
        "bytes": path.stat().st_size,
        "record_count": record_count,
        "first_observed_at": first_observed_at,
        "last_observed_at": last_observed_at,
        "source_timezone": "UTC",
        "timestamp_semantics": timestamp_semantics,
        "complete_only": True,
        "transform_id": "synthetic-fixture:0.1.0",
        "freshness_max_seconds": 3600,
    }


def build_valid_bundle(root: Path, *, completed: bool = True) -> tuple[Path, Path]:
    run_dir = root / "run"
    private_root = root / "private"
    run_dir.mkdir()
    private_root.mkdir()
    daily = synthetic_daily()
    daily_path, daily_hash = _private_snapshot(private_root, "daily.json", daily)
    h4 = copy.deepcopy(daily)
    h4["granularity"] = "H4"
    h4["candles"] = h4["candles"][-300:]
    h4_path, h4_hash = _private_snapshot(private_root, "h4.json", h4)
    instrument_path, instrument_hash = _private_snapshot(
        private_root, "instrument.json", {"name": "XAU_USD"}
    )

    snapshots = [
        _snapshot(
            "instrument_spec",
            instrument_path,
            instrument_hash,
            timestamp_semantics="not_applicable",
        ),
        _snapshot(
            "price_daily",
            daily_path,
            daily_hash,
            record_count=len(daily["candles"]),
            first_observed_at=daily["candles"][0]["time"],
            last_observed_at=daily["candles"][-1]["time"],
            timestamp_semantics="open_time",
        ),
        _snapshot(
            "price_h4",
            h4_path,
            h4_hash,
            record_count=len(h4["candles"]),
            first_observed_at=h4["candles"][0]["time"],
            last_observed_at=h4["candles"][-1]["time"],
            timestamp_semantics="open_time",
        ),
    ]
    for role in ("macro_rates", "macro_usd", "event_clock"):
        path, digest = _private_snapshot(private_root, f"{role}.json", {"role": role})
        semantics = "event_time" if role == "event_clock" else "publication_time"
        observed = "2026-08-03T12:00:00Z" if role == "event_clock" else CAPTURED
        snapshots.append(
            _snapshot(
                role,
                path,
                digest,
                first_observed_at=observed,
                last_observed_at=observed,
                timestamp_semantics=semantics,
            )
        )

    manifest = {
        "contract_version": "0.2.0",
        "manifest_id": "manifest-valid",
        "instrument": "XAUUSD",
        "provider": {
            "provider_id": "oanda-v20",
            "instrument_id": "XAU_USD",
            "environment": "practice",
            "account_instrument_verified": True,
            "qualification_version": "data-source-qualification:0.1.0",
        },
        "as_of": AS_OF,
        "data_cutoff": CUTOFF,
        "licence": {
            "name": "Test-only regional agreement",
            "region_or_entity": "test fixture",
            "version_or_effective_date": "2026-01-01",
            "locator": "https://official.example/licence",
            "usage_scope": "internal_evaluation",
            "accepted_by_account_holder": True,
            "verified_at": CAPTURED,
        },
        "snapshots": snapshots,
        "coverage": {
            "daily_complete_bars": len(daily["candles"]),
            "h4_complete_bars": len(h4["candles"]),
            "last_daily_complete_at": daily["candles"][-1]["time"],
            "last_h4_complete_at": h4["candles"][-1]["time"],
        },
        "quality": {
            "missing_intervals": [],
            "stale": False,
            "future_records": False,
            "notes": ["synthetic test fixture"],
        },
        "provenance": {
            "created_at": AS_OF,
            "created_by": "unit-test",
            "runtime_version": "dao-certified-runtime:0.2.0",
            "source_policy_version": "data-source-qualification:0.1.0",
        },
    }
    created_at = datetime(2026, 7, 30, 12, 1, tzinfo=timezone.utc)
    feature = build_feature_snapshot(
        daily,
        manifest_id=manifest["manifest_id"],
        data_cutoff=CUTOFF,
        source_snapshot_sha256=daily_hash,
        created_at=created_at,
        feature_snapshot_id="features-valid",
    )
    baseline = build_baseline_snapshot(
        daily,
        data_cutoff=CUTOFF,
        source_snapshot_sha256=daily_hash,
        created_at=created_at,
        baseline_id="baseline-valid",
    )
    write_json(run_dir / "evidence-manifest.json", manifest)
    write_json(run_dir / "feature-snapshot.json", feature)
    write_json(run_dir / "baseline-snapshot.json", baseline)

    evidence = [
        {
            "evidence_id": "e-price-1",
            "layer": "market",
            "kind": "observation",
            "claim": "Synthetic fixture close and ATR were frozen by the runtime.",
            "dependency_group": "price-fixture",
            "source": {
                "title": "Synthetic fixture",
                "author": None,
                "locator": "private://daily.json",
                "published_at": None,
                "accessed_at": CAPTURED,
            },
            "source_timezone": "UTC",
            "bar_timestamp_semantics": "open_time",
            "observed_at": CAPTURED,
            "available_at": CAPTURED,
            "recorded_at": CAPTURED,
            "availability_verified": True,
            "vintage_id": "fixture-v1",
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
            "tags": ["test"],
        }
    ]
    baseline_probabilities = baseline["probabilities"]
    scenarios = [
        {
            "scenario_id": f"scenario-{outcome}",
            "resolution_outcome_id": outcome,
            "description": f"Synthetic {outcome} outcome.",
            "probability": baseline_probabilities[outcome],
            "triggers": [f"fixture trigger for {outcome}"],
        }
        for outcome in ("up", "down", "range")
    ]
    frame = {
        "frame_id": "frame-valid",
        "instrument": "XAUUSD",
        "as_of": AS_OF,
        "data_cutoff": CUTOFF,
        "horizon": "5 completed trading sessions",
        "state": {
            "direction": "range",
            "lifecycle": "maturity",
            "stability": "stable",
            "posterior": {"up": 0.3, "down": 0.3, "range": 0.4},
        },
        "change_model": {
            "xing": "synthetic fixture",
            "shi": 0.0,
            "ji": 0.5,
            "shi_temporal": "test-only",
            "wei": "maturity",
            "xin": 0.5,
        },
        "evidence_refs": ["e-price-1"],
        "counterevidence_refs": [],
        "scenarios": scenarios,
        "invalidation_conditions": ["Fixture integrity fails."],
        "risk": {
            "level": "medium",
            "research_posture": "observe",
            "warnings": ["Synthetic test only."],
        },
        "abstention": {
            "state": {"abstain": False, "reason_codes": [], "reason": None},
            "forecast": {"abstain": False, "reason_codes": [], "reason": None},
        },
        "data_gaps": [],
        "provenance": {
            "data_snapshot": "evidence-manifest.json",
            "feature_version": feature["feature_snapshot_id"],
            "model_versions": ["baseline-only:0.1.0"],
            "prompt_version": "daily-cognition-run:0.2.0",
            "contract_version": "2.1.0",
            "certification_level": "Q1",
            "resolution_protocol_version": "xauusd-direction-5d:0.2.0",
        },
    }
    forecast = {
        "contract_version": "2.1.0",
        "forecast_id": "forecast-valid",
        "frame_id": frame["frame_id"],
        "question": "Which mutually exclusive 5-session direction outcome resolves?",
        "instrument": "XAUUSD",
        "created_at": "2026-07-30T12:05:00Z",
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
                "description": f"Synthetic {outcome} outcome.",
                "probability": baseline_probabilities[outcome],
            }
            for outcome in ("up", "down", "range")
        ],
        "baseline": {
            "baseline_ref": "baseline-snapshot.json",
            "method": "rolling_historical_frequency",
            "probabilities": baseline_probabilities,
            "version": "baseline:0.1.0",
            "sample_size": baseline["training"]["sample_size"],
            "training_start": baseline["training"]["start_session"],
            "training_end": baseline["training"]["end_session"],
            "frozen_at": baseline["provenance"]["created_at"],
            "source_snapshot_sha256": daily_hash,
        },
        "evidence_refs": ["e-price-1"],
        "counterevidence_refs": [],
        "resolution_rule": {
            "protocol_id": "xauusd-direction-5d:0.2.0",
            "reference_price_field": "mid.c",
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
                "price_component": "M",
                "daily_alignment": 17,
                "alignment_timezone": "America/New_York",
                "calendar_id": "oanda-xauusd-ny17",
                "calendar_version": "0.1.0",
            },
        },
        "invalidation_conditions": ["Fixture integrity fails."],
        "forecast_abstention": {"abstain": False, "reason_codes": [], "reason": None},
        "status": "open",
        "model_versions": ["baseline-only:0.1.0"],
    }
    write_json(run_dir / "evidence-items.json", evidence)
    write_json(run_dir / "market-cognition-frame.json", frame)
    write_json(run_dir / "forecast-contract.json", forecast)
    (run_dir / "explanation.md").write_text("Synthetic fixture.\n", encoding="utf-8")

    run = {
        "contract_version": "0.2.0",
        "run_id": "run-valid",
        "mode": "certified",
        "instrument": "XAUUSD",
        "as_of": AS_OF,
        "data_cutoff": CUTOFF,
        "status": "completed" if completed else "ready",
        "input": {
            "evidence_manifest": "evidence-manifest.json",
            "previous_frame": None,
            "feature_snapshot": "feature-snapshot.json",
            "baseline": "baseline-snapshot.json",
            "daily_complete_bars": len(daily["candles"]),
            "h4_complete_bars": len(h4["candles"]),
            "private_raw_data": True,
        },
        "gates": {
            key: "pass"
            for key in (
                "instrument_available",
                "licence",
                "temporal_integrity",
                "bar_semantics",
                "completeness",
                "snapshot_hash",
                "macro_coverage",
                "event_clock",
                "feature_snapshot_frozen",
                "baseline_frozen",
            )
        },
        "outputs": {
            "evidence_items": "evidence-items.json" if completed else None,
            "frame": "market-cognition-frame.json" if completed else None,
            "forecast": "forecast-contract.json" if completed else None,
            "delta": None,
            "resolution": None,
            "explanation": "explanation.md" if completed else None,
        },
        "blocking_reasons": [],
        "provenance": {
            "prompt_version": "daily-cognition-run:0.2.0",
            "source_policy_version": "data-source-qualification:0.1.0",
            "runtime_version": "dao-certified-runtime:0.2.0",
            "model_versions": ["baseline-only:0.1.0"],
            "created_at": AS_OF,
        },
    }
    write_json(run_dir / "run.json", run)
    return run_dir, private_root


def _resolved_record(
    forecast: dict,
    *,
    reference: float,
    diagnostic: float,
    final: float,
    atr: float,
    normalized_3: float,
    normalized_5: float,
    outcome: str,
) -> dict:
    probabilities = {
        item["outcome_id"]: item["probability"] for item in forecast["outcomes"]
    }
    one_hot = {
        candidate: 1.0 if candidate == outcome else 0.0
        for candidate in ("up", "down", "range")
    }
    brier = sum(
        (probabilities[candidate] - one_hot[candidate]) ** 2
        for candidate in one_hot
    ) / 3.0
    return {
        "resolution_id": "resolution-valid",
        "forecast_id": forecast["forecast_id"],
        "frame_id": forecast["frame_id"],
        "resolved_at": "2026-08-06T12:00:00Z",
        "protocol_version": "xauusd-direction-5d:0.2.0",
        "source_snapshot_ref": "private://resolution.json",
        "status": "resolved",
        "observed": {
            "reference_close": reference,
            "diagnostic_close_3": diagnostic,
            "resolution_close_5": final,
            "atr20_at_cutoff": atr,
            "normalized_change_3": normalized_3,
            "normalized_change_5": normalized_5,
            "outcome_id": outcome,
        },
        "scoring": {
            "eligible": True,
            "exclusion_reasons": [],
            "brier_multiclass": brier,
            "log_loss": -math.log(max(probabilities[outcome], 1e-15)),
            "baseline_brier": brier,
            "brier_skill_score": 0.0,
        },
        "audit": {
            "append_only": True,
            "forecast_frozen_before_outcomes": True,
            "resolver_ref": "unit-test",
            "notes": [],
        },
        "provenance": {
            "contract_version": "0.2.1",
            "resolver_version": "resolution:0.1.0",
        },
    }


class BundleValidationTests(unittest.TestCase):
    def test_valid_completed_bundle_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, private_root = build_valid_bundle(Path(temp))
            self.assertEqual(
                validate_bundle(
                    run_dir, private_root=private_root, raise_on_error=False
                ),
                [],
            )

    def test_failed_gates_cannot_claim_completed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, private_root = build_valid_bundle(Path(temp))
            run = json.loads((run_dir / "run.json").read_text())
            run["gates"]["licence"] = "fail"
            write_json(run_dir / "run.json", run)
            errors = validate_bundle(
                run_dir, private_root=private_root, raise_on_error=False
            )
            self.assertTrue(any("gates.licence" in error for error in errors), errors)

    def test_probability_sum_is_machine_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, private_root = build_valid_bundle(Path(temp))
            forecast = json.loads((run_dir / "forecast-contract.json").read_text())
            frame = json.loads((run_dir / "market-cognition-frame.json").read_text())
            for item in forecast["outcomes"]:
                item["probability"] = 0.9
            for item in frame["scenarios"]:
                item["probability"] = 0.9
            write_json(run_dir / "forecast-contract.json", forecast)
            write_json(run_dir / "market-cognition-frame.json", frame)
            errors = validate_bundle(
                run_dir, private_root=private_root, raise_on_error=False
            )
            self.assertTrue(any("probabilities sum" in error for error in errors), errors)

    def test_duplicate_outcomes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, private_root = build_valid_bundle(Path(temp))
            forecast = json.loads((run_dir / "forecast-contract.json").read_text())
            for item in forecast["outcomes"]:
                item["outcome_id"] = "up"
            write_json(run_dir / "forecast-contract.json", forecast)
            errors = validate_bundle(
                run_dir, private_root=private_root, raise_on_error=False
            )
            self.assertTrue(
                any("up/down/range exactly once" in error for error in errors), errors
            )

    def test_resolved_with_null_observations_and_scores_fails_schema(self) -> None:
        invalid = {
            "resolution_id": "resolution-invalid",
            "forecast_id": "forecast-valid",
            "frame_id": "frame-valid",
            "resolved_at": "2026-08-06T12:00:00Z",
            "protocol_version": "xauusd-direction-5d:0.2.0",
            "source_snapshot_ref": "private://resolution.json",
            "status": "resolved",
            "observed": {
                "reference_close": None,
                "diagnostic_close_3": None,
                "resolution_close_5": None,
                "atr20_at_cutoff": None,
                "normalized_change_3": None,
                "normalized_change_5": None,
                "outcome_id": None,
            },
            "scoring": {
                "eligible": True,
                "exclusion_reasons": [],
                "brier_multiclass": None,
                "log_loss": None,
                "baseline_brier": None,
                "brier_skill_score": None,
            },
            "audit": {
                "append_only": True,
                "forecast_frozen_before_outcomes": True,
                "resolver_ref": "unit-test",
                "notes": [],
            },
            "provenance": {
                "contract_version": "0.2.1",
                "resolver_version": "resolution:0.1.0",
            },
        }
        errors = schema_errors(
            invalid, "resolution-record.schema.json", "resolution-invalid"
        )
        self.assertTrue(errors)

    def test_resolution_scores_are_recomputed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, private_root = build_valid_bundle(Path(temp))
            forecast = json.loads((run_dir / "forecast-contract.json").read_text())
            run = json.loads((run_dir / "run.json").read_text())
            frozen = forecast["resolution_rule"]["frozen_values"]
            reference = frozen["reference_close"]
            atr = frozen["atr20_at_cutoff"]
            diagnostic = reference + 0.1 * atr
            final = reference + 1.0 * atr
            probabilities = {
                item["outcome_id"]: item["probability"]
                for item in forecast["outcomes"]
            }
            brier = (
                (probabilities["up"] - 1.0) ** 2
                + probabilities["down"] ** 2
                + probabilities["range"] ** 2
            ) / 3.0
            resolution = {
                "resolution_id": "resolution-wrong-score",
                "forecast_id": forecast["forecast_id"],
                "frame_id": forecast["frame_id"],
                "resolved_at": "2026-08-06T12:00:00Z",
                "protocol_version": "xauusd-direction-5d:0.2.0",
                "source_snapshot_ref": "private://resolution.json",
                "status": "resolved",
                "observed": {
                    "reference_close": reference,
                    "diagnostic_close_3": diagnostic,
                    "resolution_close_5": final,
                    "atr20_at_cutoff": atr,
                    "normalized_change_3": 0.1,
                    "normalized_change_5": 1.0,
                    "outcome_id": "up",
                },
                "scoring": {
                    "eligible": True,
                    "exclusion_reasons": [],
                    "brier_multiclass": brier + 0.1,
                    "log_loss": -math.log(max(probabilities["up"], 1e-15)),
                    "baseline_brier": brier,
                    "brier_skill_score": 0.0,
                },
                "audit": {
                    "append_only": True,
                    "forecast_frozen_before_outcomes": True,
                    "resolver_ref": "unit-test",
                    "notes": [],
                },
                "provenance": {
                    "contract_version": "0.2.1",
                    "resolver_version": "resolution:0.1.0",
                },
            }
            write_json(run_dir / "resolution-record.json", resolution)
            run["status"] = "resolved"
            run["outputs"]["resolution"] = "resolution-record.json"
            write_json(run_dir / "run.json", run)
            errors = validate_bundle(
                run_dir, private_root=private_root, raise_on_error=False
            )
            self.assertTrue(
                any("brier_multiclass is not reproducible" in error for error in errors),
                errors,
            )

    def test_resolution_boundary_classification_uses_decimal_arithmetic(self) -> None:
        cases = (
            ("positive", 0.1, 0.4, 0.5),
            ("negative", 0.4, 0.1, -0.5),
        )
        for label, reference, final, normalized in cases:
            with self.subTest(boundary=label), tempfile.TemporaryDirectory() as temp:
                run_dir, private_root = build_valid_bundle(Path(temp))
                forecast = json.loads((run_dir / "forecast-contract.json").read_text())
                run = json.loads((run_dir / "run.json").read_text())
                resolution = _resolved_record(
                    forecast,
                    reference=reference,
                    diagnostic=reference,
                    final=final,
                    atr=0.6,
                    normalized_3=0.0,
                    normalized_5=normalized,
                    outcome="range",
                )
                write_json(run_dir / "resolution-record.json", resolution)
                run["status"] = "resolved"
                run["outputs"]["resolution"] = "resolution-record.json"
                write_json(run_dir / "run.json", run)

                errors = validate_bundle(
                    run_dir, private_root=private_root, raise_on_error=False
                )

                self.assertEqual(errors, [])

    def test_resolved_abstained_forecast_has_explicit_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, private_root = build_valid_bundle(Path(temp))
            forecast = json.loads((run_dir / "forecast-contract.json").read_text())
            frame = json.loads((run_dir / "market-cognition-frame.json").read_text())
            run = json.loads((run_dir / "run.json").read_text())
            resolution = _resolved_record(
                forecast,
                reference=0.1,
                diagnostic=0.1,
                final=0.4,
                atr=0.6,
                normalized_3=0.0,
                normalized_5=0.5,
                outcome="range",
            )
            forecast["forecast_abstention"] = {
                "abstain": True,
                "reason_codes": ["insufficient_evidence"],
                "reason": "Synthetic abstention test.",
            }
            for item in forecast["outcomes"]:
                item["probability"] = None
            frame["abstention"]["forecast"] = {
                "abstain": True,
                "reason_codes": ["insufficient_evidence"],
                "reason": "Synthetic abstention test.",
            }
            for item in frame["scenarios"]:
                item["probability"] = None
            write_json(run_dir / "forecast-contract.json", forecast)
            write_json(run_dir / "market-cognition-frame.json", frame)
            write_json(run_dir / "resolution-record.json", resolution)
            run["status"] = "resolved"
            run["outputs"]["resolution"] = "resolution-record.json"
            write_json(run_dir / "run.json", run)

            errors = validate_bundle(
                run_dir, private_root=private_root, raise_on_error=False
            )

            self.assertIn(
                "resolved resolution cannot score an abstained forecast",
                errors,
            )
            self.assertFalse(
                any("could not continue" in error for error in errors),
                errors,
            )

    def test_missing_core_snapshot_role_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, private_root = build_valid_bundle(Path(temp))
            manifest = json.loads((run_dir / "evidence-manifest.json").read_text())
            manifest["snapshots"] = [
                item for item in manifest["snapshots"] if item["role"] != "event_clock"
            ]
            write_json(run_dir / "evidence-manifest.json", manifest)
            errors = validate_bundle(
                run_dir, private_root=private_root, raise_on_error=False
            )
            self.assertTrue(any("event_clock" in error for error in errors), errors)

    def test_private_hash_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, private_root = build_valid_bundle(Path(temp))
            (private_root / "daily.json").write_text("{}\n", encoding="utf-8")
            errors = validate_bundle(
                run_dir, private_root=private_root, raise_on_error=False
            )
            self.assertTrue(any("hash mismatch" in error for error in errors), errors)

    def test_malformed_semantics_are_rejected_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, private_root = build_valid_bundle(Path(temp))
            baseline = json.loads((run_dir / "baseline-snapshot.json").read_text())
            baseline["training"]["outcome_counts"]["up"] = "not-an-integer"
            baseline["baseline_payload_sha256"] = canonical_payload_sha256(
                baseline, "baseline_payload_sha256"
            )
            write_json(run_dir / "baseline-snapshot.json", baseline)
            errors = validate_bundle(
                run_dir, private_root=private_root, raise_on_error=False
            )
            self.assertTrue(errors)
            self.assertTrue(
                any("could not continue" in error for error in errors),
                errors,
            )

    def test_future_available_at_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, private_root = build_valid_bundle(Path(temp))
            manifest = json.loads((run_dir / "evidence-manifest.json").read_text())
            manifest["snapshots"][0]["available_at"] = "2026-07-30T12:00:01Z"
            write_json(run_dir / "evidence-manifest.json", manifest)
            errors = validate_bundle(
                run_dir, private_root=private_root, raise_on_error=False
            )
            self.assertTrue(any("available_at" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
