"""Deterministic baseline forecast emission for an automated Agent run."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import format_datetime, load_json, write_json


def _utc_now() -> str:
    return format_datetime(datetime.now(timezone.utc))


def generate_baseline_forecast(run_dir: Path) -> Path:
    """Emit a schema-shaped five-session forecast from frozen runtime inputs."""
    root = run_dir.resolve()
    run = load_json(root / "run.json")
    baseline = load_json(root / str(run["input"]["baseline"]))
    feature = load_json(root / str(run["input"]["feature_snapshot"]))
    manifest = load_json(root / str(run["input"]["evidence_manifest"]))
    instrument = run["instrument"]
    is_gc = instrument.startswith("GC")
    training = baseline["training"]
    probabilities = baseline["probabilities"]
    contract = manifest.get("futures_contract", {})
    calendar = feature["trading_calendar"]
    bar_config = feature["bar_config"]
    frozen_values: dict[str, Any] = {
        "feature_snapshot_ref": run["input"]["feature_snapshot"],
        "feature_payload_sha256": feature["feature_payload_sha256"],
        "reference_session": feature["reference_session"],
        "reference_close": feature["reference_close"],
        "atr20_at_cutoff": feature["atr20"]["value"],
        "price_component": bar_config["price_component"],
        "daily_alignment": bar_config.get("daily_alignment"),
        "alignment_timezone": bar_config["alignment_timezone"],
        "calendar_id": calendar["calendar_id"],
        "calendar_version": calendar.get("calendar_version", calendar.get("version")),
    }
    if is_gc:
        frozen_values.update(
            {
                "contract_code": contract["contract_code"],
                "first_position_date": contract["first_position_date"],
                "last_trade_date": contract["last_trade_date"],
                "resolution_session_sequence_sha256": contract[
                    "resolution_session_sequence_sha256"
                ],
            }
        )
    forecast = {
        "contract_version": "2.2.0" if is_gc else "2.1.0",
        "forecast_id": f"forecast-{run['run_id']}",
        "frame_id": f"frame-{run['run_id']}",
        "question": f"Which {instrument} five-session outcome resolves?",
        "instrument": instrument,
        "created_at": _utc_now(),
        "data_cutoff": run["data_cutoff"],
        "horizon": {
            "unit": "completed_trading_session",
            "primary_sessions": 5,
            "diagnostic_sessions": [3],
            "starts_after_cutoff": True,
        },
        "outcomes": [
            {
                "outcome_id": outcome,
                "description": f"{instrument} {outcome} outcome.",
                "probability": probabilities[outcome],
            }
            for outcome in ("up", "down", "range")
        ],
        "baseline": {
            "baseline_ref": run["input"]["baseline"],
            "method": "rolling_historical_frequency",
            "probabilities": probabilities,
            "version": "gc-baseline:0.1.0" if is_gc else "baseline:0.1.0",
            "sample_size": training["sample_size"],
            "training_start": training["start_session"],
            "training_end": training["end_session"],
            "frozen_at": baseline["provenance"]["created_at"],
            "source_snapshot_sha256": baseline["source_daily_snapshot_sha256"],
        },
        "evidence_refs": [
            item["snapshot_id"]
            for item in manifest["snapshots"]
            if item.get("role") in {"price_daily", "price_h4"}
        ],
        "counterevidence_refs": [],
        "resolution_rule": {
            "protocol_id": baseline["protocol_id"],
            "reference_price_field": feature["reference_price_field"],
            "normalizer": {
                "method": "wilder_atr_seed_mean",
                "lookback_sessions": 20,
                "freeze_at_cutoff": True,
            },
            "neutral_band_atr_multiple": 0.5,
            "boundary_policy": "inclusive_range",
            "missing_data_policy": "mark_unresolvable",
            "frozen_values": frozen_values,
        },
        "invalidation_conditions": [
            "The frozen price snapshot, contract identity, or resolution calendar is invalid.",
            "The five-session resolution window cannot be observed completely.",
        ],
        "forecast_abstention": {
            "abstain": training["sample_size"] < training["minimum_sample_size"],
            "reason_codes": (
                ["missing_baseline_history"]
                if training["sample_size"] < training["minimum_sample_size"]
                else []
            ),
            "reason": (
                "Frozen baseline has fewer than the required historical origins."
                if training["sample_size"] < training["minimum_sample_size"]
                else None
            ),
        },
        "status": "open",
        "model_versions": ["gc-baseline-only:0.1.0" if is_gc else "baseline-only:0.1.0"],
    }
    output = root / "forecast-contract.json"
    write_json(output, forecast)
    return output
