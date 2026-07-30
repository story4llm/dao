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


def _decimal(candle: dict[str, Any], field: str) -> Decimal:
    return Decimal(str(candle["mid"][field]))


def true_range(previous: dict[str, Any], current: dict[str, Any]) -> Decimal:
    high = _decimal(current, "h")
    low = _decimal(current, "l")
    previous_close = _decimal(previous, "c")
    return max(high - low, abs(high - previous_close), abs(low - previous_close))


def atr_seed_mean_at(
    candles: list[dict[str, Any]],
    index: int,
    period: int = ATR_PERIOD,
) -> Decimal:
    if index < period:
        raise ValueError(f"ATR({period}) requires {period + 1} complete bars")
    ranges = [
        true_range(candles[position - 1], candles[position])
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


def _feature_config() -> dict[str, Any]:
    return {
        "reference_price_field": "mid.c",
        "atr_method": "wilder_atr_seed_mean",
        "atr_lookback_true_ranges": ATR_PERIOD,
        "required_complete_bars": ATR_PERIOD + 1,
        "horizon_sessions": HORIZON,
        "neutral_band_atr_multiple": float(NEUTRAL_BAND),
        "boundary_policy": "inclusive_range",
        "daily_alignment": 17,
        "alignment_timezone": "America/New_York",
        "calendar_id": "oanda-xauusd-ny17",
        "calendar_version": "0.1.0",
    }


def build_feature_snapshot(
    daily_snapshot: dict[str, Any],
    *,
    manifest_id: str,
    data_cutoff: str,
    source_snapshot_sha256: str,
    created_at: datetime,
    feature_snapshot_id: str,
) -> dict[str, Any]:
    candles = daily_snapshot["candles"]
    if len(candles) < ATR_PERIOD + 1:
        raise ValueError("feature snapshot requires at least 21 complete daily bars")
    last_index = len(candles) - 1
    atr = atr_seed_mean_at(candles, last_index)
    reference = candles[last_index]
    session_hash = sha256_bytes(
        canonical_json_bytes([item["time"] for item in candles[-(ATR_PERIOD + 1) :]])
    )
    payload: dict[str, Any] = {
        "contract_version": "0.1.0",
        "feature_snapshot_id": feature_snapshot_id,
        "instrument": "XAUUSD",
        "data_cutoff": data_cutoff,
        "source_manifest_id": manifest_id,
        "reference_session": reference["time"],
        "reference_price_field": "mid.c",
        "reference_close": float(_decimal(reference, "c")),
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
            "price_component": "M",
            "daily_alignment": 17,
            "alignment_timezone": "America/New_York",
            "timestamp_semantics": "open_time",
        },
        "trading_calendar": {
            "calendar_id": "oanda-xauusd-ny17",
            "version": "0.1.0",
            "session_sequence_sha256": session_hash,
        },
        "feature_payload_sha256": "",
        "provenance": {
            "created_at": format_datetime(created_at),
            "runtime_version": "dao-certified-runtime:0.2.0",
        },
    }
    payload["feature_payload_sha256"] = canonical_payload_sha256(
        payload, "feature_payload_sha256"
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
    candles = daily_snapshot["candles"]
    counts: Counter[str] = Counter()
    origin_sessions: list[str] = []
    for origin_index in range(ATR_PERIOD, len(candles) - HORIZON):
        atr = atr_seed_mean_at(candles, origin_index)
        reference_close = _decimal(candles[origin_index], "c")
        resolution_close = _decimal(candles[origin_index + HORIZON], "c")
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
    feature_config_hash = sha256_bytes(canonical_json_bytes(_feature_config()))
    payload: dict[str, Any] = {
        "contract_version": "0.1.0",
        "baseline_id": baseline_id,
        "instrument": "XAUUSD",
        "protocol_id": "xauusd-direction-5d:0.2.0",
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
            "runtime_version": "dao-certified-runtime:0.2.0",
            "code_version": "baseline:0.1.0",
        },
    }
    payload["baseline_payload_sha256"] = canonical_payload_sha256(
        payload, "baseline_payload_sha256"
    )
    return payload
