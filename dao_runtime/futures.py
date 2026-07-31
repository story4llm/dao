"""Private COMEX GC single-contract bundle preparation."""

from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .contracts import (
    canonical_json_bytes,
    format_datetime,
    load_json,
    parse_datetime,
    sha256_bytes,
    sha256_file,
    write_json,
)
from .features import (
    ATR_PERIOD,
    HORIZON,
    MIN_BASELINE_SAMPLES,
    build_market_baseline_snapshot,
    build_market_feature_snapshot,
)
from .oanda import (
    OFFICIAL_ROLES,
    _contains_placeholder,
    _contains_sensitive_config_key,
    _copy_official_snapshot,
    _ensure_empty_target,
)


RUNTIME_VERSION = "dao-certified-runtime:0.3.0"
GC_CONTRACT_PATTERN = re.compile(r"^GC[FGHJKMNQUVXZ][0-9]{2}$")
GC_PROTOCOL_ID = "gc-single-contract-direction-5d:0.1.0"
GC_CALENDAR_ID = "cme-gc-settlement"
GC_CALENDAR_VERSION = "0.1.0"
REQUIRED_DAILY_BARS = ATR_PERIOD + HORIZON + MIN_BASELINE_SAMPLES + 1
MONTH_BY_CODE = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _positive_decimal(value: Any, label: str) -> str:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not a decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{label} must be a positive finite decimal")
    return format(parsed, "f")


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a non-negative integer")
    parsed = int(value)
    if parsed < 0 or parsed != value:
        raise ValueError(f"{label} must be a non-negative integer")
    return parsed


def _validate_contract_spec(
    payload: dict[str, Any],
    contract_code: str,
    resolution_sessions: list[str],
    data_cutoff: str,
) -> dict[str, Any]:
    if not GC_CONTRACT_PATTERN.fullmatch(contract_code):
        raise ValueError(
            "contract_code must identify one listed GC month, for example GCZ26"
        )
    expected = {
        "product_code": "GC",
        "contract_code": contract_code,
        "venue": "COMEX",
        "contract_size_oz": 100,
        "tick_size": 0.1,
        "currency": "USD",
        "price_unit": "troy_ounce",
        "continuous": False,
        "roll_policy": "none",
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"instrument spec {field} must be {value!r}")
    contract_month = payload.get("contract_month")
    if not isinstance(contract_month, str) or not re.fullmatch(
        r"[0-9]{4}-(0[1-9]|1[0-2])", contract_month
    ):
        raise ValueError("instrument spec contract_month must use YYYY-MM")
    expected_contract_month = (
        f"20{contract_code[-2:]}-{MONTH_BY_CODE[contract_code[2]]:02d}"
    )
    if contract_month != expected_contract_month:
        raise ValueError(
            "instrument spec contract_month does not match contract_code"
        )
    try:
        first_position_date = date.fromisoformat(payload["first_position_date"])
        last_trade_date = date.fromisoformat(payload["last_trade_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "instrument spec requires ISO first_position_date and last_trade_date"
        ) from exc
    if first_position_date > last_trade_date:
        raise ValueError("first_position_date cannot be after last_trade_date")
    if len(resolution_sessions) != HORIZON:
        raise ValueError("resolution_sessions must contain exactly five sessions")
    parsed_sessions = [parse_datetime(value) for value in resolution_sessions]
    if parsed_sessions != sorted(parsed_sessions) or len(set(parsed_sessions)) != HORIZON:
        raise ValueError("resolution_sessions must be unique and increasing")
    if any(session <= parse_datetime(data_cutoff) for session in parsed_sessions):
        raise ValueError("resolution_sessions must be after data_cutoff")
    for session in parsed_sessions:
        if session.date() >= first_position_date or session.date() >= last_trade_date:
            raise ValueError(
                "five-session forecast window must end before first position "
                "and last trade dates"
            )
    return {
        "product_code": "GC",
        "contract_code": contract_code,
        "venue": "COMEX",
        "contract_month": contract_month,
        "first_position_date": first_position_date.isoformat(),
        "last_trade_date": last_trade_date.isoformat(),
        "contract_size_oz": 100,
        "tick_size": 0.1,
        "currency": "USD",
        "price_unit": "troy_ounce",
        "continuous": False,
        "roll_policy": "none",
        "daily_reference_price_field": "settlement",
        "exchange_timezone": "America/Chicago",
        "calendar_id": GC_CALENDAR_ID,
        "calendar_version": GC_CALENDAR_VERSION,
        "resolution_sessions": resolution_sessions,
        "resolution_session_sequence_sha256": sha256_bytes(
            canonical_json_bytes(resolution_sessions)
        ),
    }


def _normalize_records(
    payload: dict[str, Any],
    *,
    contract_code: str,
    granularity: str,
    data_cutoff: str,
) -> dict[str, Any]:
    if payload.get("contract_code") != contract_code:
        raise ValueError(f"{granularity} source contract_code does not match config")
    close_field = "settlement" if granularity == "D" else "c"
    records: list[dict[str, Any]] = []
    for index, record in enumerate(payload.get("records", [])):
        if record.get("complete") is not True:
            continue
        time = record.get("time")
        available_at = record.get("available_at")
        if not isinstance(time, str) or not isinstance(available_at, str):
            raise ValueError(f"{granularity} record {index} lacks time/available_at")
        parse_datetime(time)
        if parse_datetime(time) > parse_datetime(data_cutoff):
            raise ValueError(f"{granularity} record {index} is after data_cutoff")
        if parse_datetime(available_at) > parse_datetime(data_cutoff):
            raise ValueError(
                f"{granularity} record {index} was unavailable at data_cutoff"
            )
        price = {
            field: _positive_decimal(record.get(field), f"{granularity}[{index}].{field}")
            for field in ("o", "h", "l", close_field)
        }
        numeric = {field: Decimal(value) for field, value in price.items()}
        if numeric["h"] < max(numeric.values()) or numeric["l"] > min(numeric.values()):
            raise ValueError(f"{granularity} record {index} has invalid OHLC bounds")
        normalized = {
            "time": time,
            "available_at": available_at,
            "price": price,
            "volume": _nonnegative_int(
                record.get("volume", 0), f"{granularity}[{index}].volume"
            ),
            "complete": True,
        }
        if granularity == "D":
            normalized["open_interest"] = _nonnegative_int(
                record.get("open_interest", 0),
                f"{granularity}[{index}].open_interest",
            )
        records.append(normalized)
    records.sort(key=lambda item: parse_datetime(item["time"]))
    timestamps = [item["time"] for item in records]
    if len(timestamps) != len(set(timestamps)):
        raise ValueError(f"{granularity} source contains duplicate timestamps")
    minimum = REQUIRED_DAILY_BARS if granularity == "D" else 30
    if len(records) < minimum:
        raise ValueError(
            f"{granularity} source requires at least {minimum} complete records"
        )
    return {
        "instrument": contract_code,
        "product_code": "GC",
        "venue": "COMEX",
        "granularity": granularity,
        "price_component": "SETTLEMENT" if granularity == "D" else "TRADE",
        "timestamp_semantics": "session_close" if granularity == "D" else "bar_start",
        "candles": records,
    }


def _source_config(config: dict[str, Any], role: str) -> dict[str, Any]:
    source = config.get("source_files", {}).get(role)
    if not isinstance(source, dict):
        raise ValueError(f"source_files.{role} is required")
    required = {
        "path",
        "source_locator",
        "captured_at",
        "available_at",
        "source_timezone",
        "freshness_max_seconds",
    }
    if required - set(source):
        raise ValueError(f"source_files.{role} metadata is incomplete")
    return source


def _copy_and_load_source(
    source: dict[str, Any],
    private_dir: Path,
    role: str,
) -> tuple[Path, dict[str, Any]]:
    source_path = Path(str(source["path"])).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError(f"{role} source file does not exist: {source_path}")
    raw_path = private_dir / f"gc-{role}-source{source_path.suffix or '.json'}"
    shutil.copyfile(source_path, raw_path)
    try:
        payload = load_json(raw_path)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{role} source must be JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{role} source must contain one JSON object")
    return raw_path, payload


def _snapshot(
    *,
    role: str,
    source: dict[str, Any],
    raw_path: Path,
    canonical_path: Path,
    canonical: dict[str, Any],
) -> dict[str, Any]:
    candles = canonical.get("candles")
    observed = candles if isinstance(candles, list) else []
    first = observed[0]["time"] if observed else source["available_at"]
    last = observed[-1]["time"] if observed else source["available_at"]
    return {
        "snapshot_id": f"snapshot-{role.replace('_', '-')}",
        "role": role,
        "private_location_ref": f"private://{canonical_path.name}",
        "request_locator_redacted": source["source_locator"],
        "request_id": source.get("request_id"),
        "source_locator": source["source_locator"],
        "captured_at": source["captured_at"],
        "available_at": source["available_at"],
        "sha256": sha256_file(canonical_path),
        "source_response_location_ref": f"private://{raw_path.name}",
        "source_response_sha256": sha256_file(raw_path),
        "bytes": canonical_path.stat().st_size,
        "record_count": len(observed) if observed else 1,
        "first_observed_at": first,
        "last_observed_at": last,
        "source_timezone": source["source_timezone"],
        "timestamp_semantics": (
            canonical.get("timestamp_semantics")
            if observed
            else "not_applicable"
        ),
        "complete_only": True,
        "transform_id": (
            f"dao-gc-{role.replace('_', '-')}-canonical:0.1.0"
        ),
        "freshness_max_seconds": int(source["freshness_max_seconds"]),
    }


def prepare_gc_bundle(
    config_path: Path,
    public_dir: Path,
    private_dir: Path,
) -> dict[str, Path]:
    """Import licensed GC snapshots and emit a certified ready-run skeleton."""

    config = load_json(config_path)
    if _contains_sensitive_config_key(config):
        raise ValueError("credentials must not appear in the bundle config")
    if _contains_placeholder(config):
        raise ValueError("example placeholders cannot be used for a certified bundle")
    run_id = config.get("run_id")
    contract_code = config.get("contract_code")
    as_of = config.get("as_of")
    data_cutoff = config.get("data_cutoff")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("config.run_id is required")
    if not isinstance(contract_code, str):
        raise ValueError("config.contract_code is required")
    if not isinstance(as_of, str) or not isinstance(data_cutoff, str):
        raise ValueError("config.as_of and config.data_cutoff are required")
    if parse_datetime(data_cutoff) > parse_datetime(as_of):
        raise ValueError("config.data_cutoff cannot be after config.as_of")
    resolution_sessions = config.get("resolution_sessions")
    if not isinstance(resolution_sessions, list) or not all(
        isinstance(value, str) for value in resolution_sessions
    ):
        raise ValueError("config.resolution_sessions must be a date-time array")

    licence = config.get("licence", {})
    required_licence = {
        "name",
        "region_or_entity",
        "version_or_effective_date",
        "locator",
        "usage_scope",
        "accepted_by_account_holder",
        "verified_at",
    }
    if required_licence - set(licence):
        raise ValueError("licence attestation is incomplete")
    if (
        licence.get("usage_scope") != "internal_evaluation"
        or licence.get("accepted_by_account_holder") is not True
    ):
        raise ValueError("licence attestation does not permit certified internal use")

    official_items = config.get("official_snapshots", [])
    roles = [item.get("role") for item in official_items]
    if set(roles) != OFFICIAL_ROLES or len(roles) != len(set(roles)):
        raise ValueError(
            "official_snapshots must contain macro_rates, macro_usd and event_clock once"
        )

    _ensure_empty_target(private_dir, "private_dir")
    _ensure_empty_target(public_dir, "public_dir")

    spec_source = _source_config(config, "instrument_spec")
    calendar_source = _source_config(config, "contract_calendar")
    calendar_raw_path, calendar_payload = _copy_and_load_source(
        calendar_source, private_dir, "contract-calendar"
    )
    if calendar_payload.get("contract_code") != contract_code:
        raise ValueError("contract calendar contract_code does not match config")
    if calendar_payload.get("calendar_id") != GC_CALENDAR_ID or calendar_payload.get(
        "calendar_version"
    ) != GC_CALENDAR_VERSION:
        raise ValueError("contract calendar identity is not supported")
    if calendar_payload.get("resolution_sessions") != resolution_sessions:
        raise ValueError(
            "config resolution_sessions do not match contract calendar snapshot"
        )
    calendar_path = private_dir / "gc-contract-calendar-canonical.json"
    write_json(calendar_path, calendar_payload)

    spec_raw_path, spec_payload = _copy_and_load_source(
        spec_source, private_dir, "instrument-spec"
    )
    contract = _validate_contract_spec(
        spec_payload, contract_code, resolution_sessions, data_cutoff
    )
    spec_path = private_dir / "gc-instrument-spec-canonical.json"
    write_json(spec_path, contract)
    snapshots = [
        _snapshot(
            role="instrument_spec",
            source=spec_source,
            raw_path=spec_raw_path,
            canonical_path=spec_path,
            canonical=contract,
        ),
        _snapshot(
            role="contract_calendar",
            source=calendar_source,
            raw_path=calendar_raw_path,
            canonical_path=calendar_path,
            canonical=calendar_payload,
        ),
    ]

    canonical_by_granularity: dict[str, dict[str, Any]] = {}
    for role, granularity in (("price_daily", "D"), ("price_h4", "H4")):
        source = _source_config(config, role)
        raw_path, payload = _copy_and_load_source(source, private_dir, role)
        canonical = _normalize_records(
            payload,
            contract_code=contract_code,
            granularity=granularity,
            data_cutoff=data_cutoff,
        )
        latest_record_availability = max(
            parse_datetime(item["available_at"]) for item in canonical["candles"]
        )
        if parse_datetime(source["available_at"]) < latest_record_availability:
            raise ValueError(
                f"{role} source available_at predates a record's available_at"
            )
        canonical_path = private_dir / f"gc-{granularity.lower()}-canonical.json"
        write_json(canonical_path, canonical)
        snapshots.append(
            _snapshot(
                role=role,
                source=source,
                raw_path=raw_path,
                canonical_path=canonical_path,
                canonical=canonical,
            )
        )
        canonical_by_granularity[granularity] = canonical

    for item in official_items:
        snapshots.append(_copy_official_snapshot(item, private_dir))

    daily = canonical_by_granularity["D"]
    h4 = canonical_by_granularity["H4"]
    daily_meta = next(item for item in snapshots if item["role"] == "price_daily")
    manifest_id = f"evidence-{run_id}"
    created_at = utc_now()
    feature = build_market_feature_snapshot(
        daily,
        manifest_id=manifest_id,
        data_cutoff=data_cutoff,
        source_snapshot_sha256=daily_meta["sha256"],
        created_at=created_at,
        feature_snapshot_id=f"features-{run_id}",
        instrument=contract_code,
        reference_price_field="settlement",
        price_container="price",
        close_field="settlement",
        price_component="SETTLEMENT",
        daily_alignment=None,
        alignment_timezone="America/Chicago",
        timestamp_semantics="session_close",
        calendar_id=GC_CALENDAR_ID,
        calendar_version=GC_CALENDAR_VERSION,
        runtime_version=RUNTIME_VERSION,
    )
    baseline = build_market_baseline_snapshot(
        daily,
        data_cutoff=data_cutoff,
        source_snapshot_sha256=daily_meta["sha256"],
        created_at=created_at,
        baseline_id=f"baseline-{run_id}",
        instrument=contract_code,
        protocol_id=GC_PROTOCOL_ID,
        reference_price_field="settlement",
        price_container="price",
        close_field="settlement",
        daily_alignment=None,
        alignment_timezone="America/Chicago",
        calendar_id=GC_CALENDAR_ID,
        calendar_version=GC_CALENDAR_VERSION,
        runtime_version=RUNTIME_VERSION,
        code_version="gc-baseline:0.1.0",
    )
    manifest = {
        "contract_version": "0.3.0",
        "manifest_id": manifest_id,
        "instrument": contract_code,
        "provider": {
            "provider_id": "cme-licensed-snapshot",
            "instrument_id": contract_code,
            "environment": "production",
            "instrument_verified": True,
            "qualification_version": "data-source-qualification:0.2.0",
        },
        "futures_contract": contract,
        "as_of": as_of,
        "data_cutoff": data_cutoff,
        "licence": licence,
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
            "notes": [
                "Single listed GC contract; no continuous-series construction or roll.",
                "Daily C0 and ATR use settlement; H4 trade bars are auxiliary only.",
            ],
        },
        "provenance": {
            "created_at": format_datetime(created_at),
            "created_by": "prepare-gc-bundle",
            "runtime_version": RUNTIME_VERSION,
            "source_policy_version": "data-source-qualification:0.2.0",
        },
    }
    run = {
        "contract_version": "0.3.0",
        "run_id": run_id,
        "mode": "certified",
        "instrument": contract_code,
        "as_of": as_of,
        "data_cutoff": data_cutoff,
        "status": "ready",
        "input": {
            "evidence_manifest": "evidence-manifest.json",
            "previous_frame": config.get("previous_frame"),
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
            "evidence_items": None,
            "frame": None,
            "forecast": None,
            "delta": None,
            "resolution": None,
            "explanation": None,
        },
        "blocking_reasons": [],
        "provenance": {
            "prompt_version": "daily-cognition-run:0.3.0",
            "source_policy_version": "data-source-qualification:0.2.0",
            "runtime_version": RUNTIME_VERSION,
            "model_versions": ["gc-baseline-only:0.1.0"],
            "created_at": format_datetime(created_at),
        },
    }
    paths = {
        "run": public_dir / "run.json",
        "manifest": public_dir / "evidence-manifest.json",
        "feature": public_dir / "feature-snapshot.json",
        "baseline": public_dir / "baseline-snapshot.json",
    }
    write_json(paths["run"], run)
    write_json(paths["manifest"], manifest)
    write_json(paths["feature"], feature)
    write_json(paths["baseline"], baseline)
    return paths
