"""Deterministic price normalization, ATR and baseline calculations."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal
from typing import Any

from .contracts import (
    canonical_json_bytes,
    canonical_payload_sha256,
    format_datetime,
    parse_datetime,
    sha256_bytes,
)


ATR_PERIOD = 20
HORIZON = 5
NEUTRAL_BAND = Decimal("0.5")
MIN_BASELINE_SAMPLES = 252


def normalize_oanda_candles(payload: dict[str, Any], granularity: str) -> dict[str, Any]:
    if payload.get("instrument") != "XAU_USD":
        raise ValueError("OANDA response instrument is not XAU_USD")
    if payload.get("granularity") != granularity:
        raise ValueError(f"OANDA response granularity is not {granularity}")

    candles: list[dict[str, Any]] = []
    for candle in payload.get("candles", []):
        if candle.get("complete") is not True:
            continue
        mid = candle.get("mid")
        if not isinstance(mid, dict):
            raise ValueError("complete candle is missing midpoint OHLC")
        normalized_mid = {}
        for field in ("o", "h", "l", "c"):
            value = Decimal(str(mid[field]))
            if value <= 0:
                raise ValueError(f"non-positive midpoint {field}")
            normalized_mid[field] = format(value, "f")
        normalized = {
            "time": candle["time"],
            "mid": normalized_mid,
            "volume": int(candle.get("volume", 0)),
            "complete": True,
        }
        parse_datetime(normalized["time"])
        candles.append(normalized)

    candles.sort(key=lambda item: parse_datetime(item["time"]))
    timestamps = [item["time"] for item in candles]
    if len(timestamps) != len(set(timestamps)):
        raise ValueError("duplicate candle timestamps")
    if not candles:
        raise ValueError("OANDA response has no complete candles")

    return {
        "instrument": "XAU_USD",
        "granularity": granularity,
        "price_component": "M",
        "timestamp_semantics": "open_time",
        "candles": candles,
    }


def _decimal(
    candle: dict[str, Any],
    field: str,
    *,
    price_container: str = "mid",
) -> Decimal:
    return Decimal(str(candle[price_container][field]))


def true_range(
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    price_container: str = "mid",
    close_field: str = "c",
) -> Decimal:
    high = _decimal(current, "h", price_container=price_container)
    low = _decimal(current, "l", price_container=price_container)
    previous_close = _decimal(
        previous, close_field, price_container=price_container
    )
    return max(high - low, abs(high - previous_close), abs(low - previous_close))


def atr_seed_mean_at(
    candles: list[dict[str, Any]],
    index: int,
    period: int = ATR_PERIOD,
    *,
    price_container: str = "mid",
    close_field: str = "c",
) -> Decimal:
    if index < period:
        raise ValueError(f"ATR({period}) requires {period + 1} complete bars")
    ranges = [
        true_range(
            candles[position - 1],
            candles[position],
            price_container=price_container,
            close_field=close_field,
        )
        for position in range(index - period + 1, index + 1)
    ]
    atr = sum(ranges, Decimal(0)) / Decimal(period)
    if atr <= 0:
        raise ValueError("ATR must be positive")
    return atr


def classify_normalized_change(value: Decimal) -> str:
    if value > NEUTRAL_BAND:
        return "up"
    if value < -NEUTRAL_BAND:
        return "down"
    return "range"


def _feature_config(
    *,
    reference_price_field: str = "mid.c",
    daily_alignment: int | None = 17,
    alignment_timezone: str = "America/New_York",
    calendar_id: str = "oanda-xauusd-ny17",
    calendar_version: str = "0.1.0",
) -> dict[str, Any]:
    return {
        "reference_price_field": reference_price_field,
        "atr_method": "wilder_atr_seed_mean",
        "atr_lookback_true_ranges": ATR_PERIOD,
        "required_complete_bars": ATR_PERIOD + 1,
        "horizon_sessions": HORIZON,
        "neutral_band_atr_multiple": float(NEUTRAL_BAND),
        "boundary_policy": "inclusive_range",
        "daily_alignment": daily_alignment,
        "alignment_timezone": alignment_timezone,
        "calendar_id": calendar_id,
        "calendar_version": calendar_version,
    }


def build_market_feature_snapshot(
    daily_snapshot: dict[str, Any],
    *,
    manifest_id: str,
    data_cutoff: str,
    source_snapshot_sha256: str,
    created_at: datetime,
    feature_snapshot_id: str,
    instrument: str,
    reference_price_field: str,
    price_container: str,
    close_field: str,
    price_component: str,
    daily_alignment: int | None,
    alignment_timezone: str,
    timestamp_semantics: str,
    calendar_id: str,
    calendar_version: str,
    runtime_version: str,
) -> dict[str, Any]:
    candles = daily_snapshot["candles"]
    if len(candles) < ATR_PERIOD + 1:
        raise ValueError("feature snapshot requires at least 21 complete daily bars")
    last_index = len(candles) - 1
    atr = atr_seed_mean_at(
        candles,
        last_index,
        price_container=price_container,
        close_field=close_field,
    )
    reference = candles[last_index]
    session_hash = sha256_bytes(
        canonical_json_bytes([item["time"] for item in candles[-(ATR_PERIOD + 1) :]])
    )
    payload: dict[str, Any] = {
        "contract_version": "0.2.0" if instrument.startswith("GC") else "0.1.0",
        "feature_snapshot_id": feature_snapshot_id,
        "instrument": instrument,
        "data_cutoff": data_cutoff,
        "source_manifest_id": manifest_id,
        "reference_session": reference["time"],
        "reference_price_field": reference_price_field,
        "reference_close": float(
            _decimal(reference, close_field, price_container=price_container)
        ),
        "atr20": {
            "method": "wilder_atr_seed_mean",
            "lookback_true_ranges": ATR_PERIOD,
            "required_complete_bars": ATR_PERIOD + 1,
            "value": float(atr),
            "input_snapshot_sha256": source_snapshot_sha256,
            "calculation_version": "wilder-atr-seed20:0.1.0",
        },
        "bar_config": {
            "granularity": "D",
            "price_component": price_component,
            "daily_alignment": daily_alignment,
            "alignment_timezone": alignment_timezone,
            "timestamp_semantics": timestamp_semantics,
        },
        "trading_calendar": {
            "calendar_id": calendar_id,
            "version": calendar_version,
            "session_sequence_sha256": session_hash,
        },
        "feature_payload_sha256": "",
        "provenance": {
            "created_at": format_datetime(created_at),
            "runtime_version": runtime_version,
        },
    }
    payload["feature_payload_sha256"] = canonical_payload_sha256(
        payload, "feature_payload_sha256"
    )
    return payload


def build_feature_snapshot(
    daily_snapshot: dict[str, Any],
    *,
    manifest_id: str,
    data_cutoff: str,
    source_snapshot_sha256: str,
    created_at: datetime,
    feature_snapshot_id: str,
) -> dict[str, Any]:
    return build_market_feature_snapshot(
        daily_snapshot,
        manifest_id=manifest_id,
        data_cutoff=data_cutoff,
        source_snapshot_sha256=source_snapshot_sha256,
        created_at=created_at,
        feature_snapshot_id=feature_snapshot_id,
        instrument="XAUUSD",
        reference_price_field="mid.c",
        price_container="mid",
        close_field="c",
        price_component="M",
        daily_alignment=17,
        alignment_timezone="America/New_York",
        timestamp_semantics="open_time",
        calendar_id="oanda-xauusd-ny17",
        calendar_version="0.1.0",
        runtime_version="dao-certified-runtime:0.2.0",
    )


def build_market_baseline_snapshot(
    daily_snapshot: dict[str, Any],
    *,
    data_cutoff: str,
    source_snapshot_sha256: str,
    created_at: datetime,
    baseline_id: str,
    instrument: str,
    protocol_id: str,
    reference_price_field: str,
    price_container: str,
    close_field: str,
    daily_alignment: int | None,
    alignment_timezone: str,
    calendar_id: str,
    calendar_version: str,
    runtime_version: str,
    code_version: str,
) -> dict[str, Any]:
    candles = daily_snapshot["candles"]
    counts: Counter[str] = Counter()
    origin_sessions: list[str] = []
    for origin_index in range(ATR_PERIOD, len(candles) - HORIZON):
        atr = atr_seed_mean_at(
            candles,
            origin_index,
            price_container=price_container,
            close_field=close_field,
        )
        reference_close = _decimal(
            candles[origin_index], close_field, price_container=price_container
        )
        resolution_close = _decimal(
            candles[origin_index + HORIZON],
            close_field,
            price_container=price_container,
        )
        normalized = (resolution_close - reference_close) / atr
        counts[classify_normalized_change(normalized)] += 1
        origin_sessions.append(candles[origin_index]["time"])

    sample_size = sum(counts.values())
    if sample_size < MIN_BASELINE_SAMPLES:
        raise ValueError(
            f"baseline requires at least {MIN_BASELINE_SAMPLES} resolved origins, "
            f"found {sample_size}"
        )
    probabilities = {
        outcome: counts[outcome] / sample_size for outcome in ("up", "down", "range")
    }
    feature_config_hash = sha256_bytes(
        canonical_json_bytes(
            _feature_config(
                reference_price_field=reference_price_field,
                daily_alignment=daily_alignment,
                alignment_timezone=alignment_timezone,
                calendar_id=calendar_id,
                calendar_version=calendar_version,
            )
        )
    )
    payload: dict[str, Any] = {
        "contract_version": "0.2.0" if instrument.startswith("GC") else "0.1.0",
        "baseline_id": baseline_id,
        "instrument": instrument,
        "protocol_id": protocol_id,
        "data_cutoff": data_cutoff,
        "method": "rolling_historical_frequency",
        "training": {
            "start_session": origin_sessions[0],
            "end_session": origin_sessions[-1],
            "sample_size": sample_size,
            "minimum_sample_size": MIN_BASELINE_SAMPLES,
            "outcome_counts": {
                outcome: counts[outcome] for outcome in ("up", "down", "range")
            },
        },
        "probabilities": probabilities,
        "normalization": {
            "horizon_sessions": HORIZON,
            "atr_method": "wilder_atr_seed_mean",
            "atr_lookback_true_ranges": ATR_PERIOD,
            "neutral_band_atr_multiple": float(NEUTRAL_BAND),
            "boundary_policy": "inclusive_range",
        },
        "source_daily_snapshot_sha256": source_snapshot_sha256,
        "feature_config_sha256": feature_config_hash,
        "baseline_payload_sha256": "",
        "provenance": {
            "created_at": format_datetime(created_at),
            "runtime_version": runtime_version,
            "code_version": code_version,
        },
    }
    payload["baseline_payload_sha256"] = canonical_payload_sha256(
        payload, "baseline_payload_sha256"
    )
    return payload


def build_baseline_snapshot(
    daily_snapshot: dict[str, Any],
    *,
    data_cutoff: str,
    source_snapshot_sha256: str,
    created_at: datetime,
    baseline_id: str,
) -> dict[str, Any]:
    return build_market_baseline_snapshot(
        daily_snapshot,
        data_cutoff=data_cutoff,
        source_snapshot_sha256=source_snapshot_sha256,
        created_at=created_at,
        baseline_id=baseline_id,
        instrument="XAUUSD",
        protocol_id="xauusd-direction-5d:0.2.0",
        reference_price_field="mid.c",
        price_container="mid",
        close_field="c",
        daily_alignment=17,
        alignment_timezone="America/New_York",
        calendar_id="oanda-xauusd-ny17",
        calendar_version="0.1.0",
        runtime_version="dao-certified-runtime:0.2.0",
        code_version="baseline:0.1.0",
    )
