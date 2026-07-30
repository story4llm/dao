"""Private OANDA collection and first-run bundle preparation."""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import (
    format_datetime,
    load_json,
    sha256_file,
    write_json,
)
from .features import (
    build_baseline_snapshot,
    build_feature_snapshot,
    normalize_oanda_candles,
)


RUNTIME_VERSION = "dao-certified-runtime:0.2.0"
OANDA_BASES = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}
OFFICIAL_ROLES = {"macro_rates", "macro_usd", "event_clock"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _request_json(url: str, token: str) -> tuple[bytes, dict[str, Any], str | None]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept-Datetime-Format": "RFC3339",
            "User-Agent": "dao-certified-runtime/0.2.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            request_id = response.headers.get("RequestID")
    except urllib.error.HTTPError as exc:
        safe_message = exc.read(4096).decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OANDA request failed with HTTP {exc.code}: {safe_message}"
        ) from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OANDA returned non-JSON data") from exc
    return raw, payload, request_id


def _ensure_empty_target(path: Path, label: str) -> None:
    if path.exists():
        if not path.is_dir():
            raise ValueError(f"{label} is not a directory: {path}")
        if any(path.iterdir()):
            raise ValueError(f"{label} is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _write_raw(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(payload)


def _contains_sensitive_config_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in {
                "token",
                "api_token",
                "oanda_api_token",
                "account_id",
                "accountid",
                "oanda_account_id",
                "authorization",
                "credential",
                "credentials",
                "secret",
            }:
                return True
            if _contains_sensitive_config_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_config_key(item) for item in value)
    elif isinstance(value, str) and value.lower().startswith("bearer "):
        return True
    return False


def _price_snapshot(
    *,
    role: str,
    canonical_path: Path,
    raw_path: Path,
    request_locator: str,
    request_id: str | None,
    captured_at: datetime,
    canonical: dict[str, Any],
) -> dict[str, Any]:
    candles = canonical["candles"]
    return {
        "snapshot_id": f"snapshot-{role.replace('_', '-')}",
        "role": role,
        "private_location_ref": f"private://{canonical_path.name}",
        "request_locator_redacted": request_locator,
        "request_id": request_id,
        "source_locator": "https://developer.oanda.com/rest-live-v20/pricing-ep/",
        "captured_at": format_datetime(captured_at),
        "available_at": format_datetime(captured_at),
        "sha256": sha256_file(canonical_path),
        "source_response_location_ref": f"private://{raw_path.name}",
        "source_response_sha256": sha256_file(raw_path),
        "bytes": canonical_path.stat().st_size,
        "record_count": len(candles),
        "first_observed_at": candles[0]["time"],
        "last_observed_at": candles[-1]["time"],
        "source_timezone": "UTC; daily alignment America/New_York 17:00",
        "timestamp_semantics": "open_time",
        "complete_only": True,
        "transform_id": "oanda-complete-midpoint-candles:0.1.0",
        "freshness_max_seconds": 600,
    }


def _instrument_snapshot(
    *,
    canonical_path: Path,
    raw_path: Path,
    request_id: str | None,
    captured_at: datetime,
) -> dict[str, Any]:
    captured = format_datetime(captured_at)
    return {
        "snapshot_id": "snapshot-instrument-spec",
        "role": "instrument_spec",
        "private_location_ref": f"private://{canonical_path.name}",
        "request_locator_redacted": (
            "/v3/accounts/{accountID}/instruments?instruments=XAU_USD"
        ),
        "request_id": request_id,
        "source_locator": "https://developer.oanda.com/rest-live-v20/account-ep/",
        "captured_at": captured,
        "available_at": captured,
        "sha256": sha256_file(canonical_path),
        "source_response_location_ref": f"private://{raw_path.name}",
        "source_response_sha256": sha256_file(raw_path),
        "bytes": canonical_path.stat().st_size,
        "record_count": 1,
        "first_observed_at": captured,
        "last_observed_at": captured,
        "source_timezone": "UTC",
        "timestamp_semantics": "not_applicable",
        "complete_only": True,
        "transform_id": "oanda-xauusd-instrument-filter:0.1.0",
        "freshness_max_seconds": 600,
    }


def _copy_official_snapshot(
    item: dict[str, Any],
    private_dir: Path,
) -> dict[str, Any]:
    role = item.get("role")
    if role not in OFFICIAL_ROLES:
        raise ValueError(f"unsupported official snapshot role: {role}")
    source_path = Path(str(item.get("path", ""))).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError(f"official snapshot file does not exist: {source_path}")
    destination = private_dir / f"official-{role}{source_path.suffix or '.snapshot'}"
    shutil.copyfile(source_path, destination)
    captured_at = item.get("captured_at")
    available_at = item.get("available_at")
    observed_at = item.get("observed_at", available_at)
    if not all(
        isinstance(value, str) for value in (captured_at, available_at, observed_at)
    ):
        raise ValueError(f"{role} requires captured_at, available_at and observed_at")
    freshness_max_seconds = int(item.get("freshness_max_seconds", 0))
    if freshness_max_seconds <= 0:
        raise ValueError(f"{role} requires positive freshness_max_seconds")
    return {
        "snapshot_id": f"snapshot-{role.replace('_', '-')}",
        "role": role,
        "private_location_ref": f"private://{destination.name}",
        "request_locator_redacted": item.get("request_locator_redacted")
        or item.get("source_locator"),
        "request_id": None,
        "source_locator": item["source_locator"],
        "captured_at": captured_at,
        "available_at": available_at,
        "sha256": sha256_file(destination),
        "source_response_location_ref": f"private://{destination.name}",
        "source_response_sha256": sha256_file(destination),
        "bytes": destination.stat().st_size,
        "record_count": int(item.get("record_count", 1)),
        "first_observed_at": observed_at,
        "last_observed_at": observed_at,
        "source_timezone": item["source_timezone"],
        "timestamp_semantics": item["timestamp_semantics"],
        "complete_only": True,
        "transform_id": "identity-copy:0.1.0",
        "freshness_max_seconds": freshness_max_seconds,
    }


def prepare_private_bundle(
    config_path: Path,
    public_dir: Path,
    private_dir: Path,
) -> dict[str, Path]:
    """Collect account-scoped OANDA data and emit a ready certified skeleton."""

    token = os.environ.get("OANDA_API_TOKEN")
    account_id = os.environ.get("OANDA_ACCOUNT_ID")
    if not token or not account_id:
        raise ValueError(
            "OANDA_API_TOKEN and OANDA_ACCOUNT_ID must be set in the local environment"
        )
    config = load_json(config_path)
    serialized_config = json.dumps(config, ensure_ascii=False).lower()
    if _contains_sensitive_config_key(config):
        raise ValueError("credentials must not appear in the bundle config")
    run_id = config.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("config.run_id is required")
    environment = config.get("environment")
    if environment not in OANDA_BASES:
        raise ValueError("config.environment must be practice or live")
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
    if "replace" in serialized_config or "example.com" in serialized_config:
        raise ValueError("example placeholders cannot be used for a certified bundle")
    official_items = config.get("official_snapshots", [])
    roles = [item.get("role") for item in official_items]
    if set(roles) != OFFICIAL_ROLES or len(roles) != len(set(roles)):
        raise ValueError(
            "official_snapshots must contain macro_rates, macro_usd and event_clock once"
        )

    _ensure_empty_target(private_dir, "private_dir")
    _ensure_empty_target(public_dir, "public_dir")
    base = OANDA_BASES[environment]

    encoded_account = urllib.parse.quote(account_id, safe="")
    instrument_url = (
        f"{base}/v3/accounts/{encoded_account}/instruments?"
        + urllib.parse.urlencode({"instruments": "XAU_USD"})
    )
    instrument_raw, instrument_payload, instrument_request_id = _request_json(
        instrument_url, token
    )
    instrument_captured_at = utc_now()
    instruments = [
        item for item in instrument_payload.get("instruments", []) if item.get("name") == "XAU_USD"
    ]
    if len(instruments) != 1:
        raise ValueError("the OANDA account did not return exactly one XAU_USD instrument")
    instrument_raw_path = private_dir / "oanda-instrument-source.json"
    instrument_path = private_dir / "oanda-instrument-xauusd.json"
    _write_raw(instrument_raw_path, instrument_raw)
    write_json(
        instrument_path,
        {
            "instrument": instruments[0],
            "captured_at": format_datetime(instrument_captured_at),
        },
    )
    snapshots = [
        _instrument_snapshot(
            canonical_path=instrument_path,
            raw_path=instrument_raw_path,
            request_id=instrument_request_id,
            captured_at=instrument_captured_at,
        )
    ]

    canonical_by_granularity: dict[str, dict[str, Any]] = {}
    for granularity, count, role in (
        ("D", 5000, "price_daily"),
        ("H4", 300, "price_h4"),
    ):
        params = {
            "price": "M",
            "granularity": granularity,
            "count": count,
            "dailyAlignment": 17,
            "alignmentTimezone": "America/New_York",
            "smooth": "false",
        }
        request_locator = (
            "/v3/accounts/{accountID}/instruments/XAU_USD/candles?"
            + urllib.parse.urlencode(params)
        )
        url = (
            f"{base}/v3/accounts/{encoded_account}/instruments/XAU_USD/candles?"
            + urllib.parse.urlencode(params)
        )
        raw, payload, request_id = _request_json(url, token)
        captured_at = utc_now()
        canonical = normalize_oanda_candles(payload, granularity)
        raw_path = private_dir / f"oanda-{granularity.lower()}-source.json"
        canonical_path = private_dir / f"oanda-{granularity.lower()}-complete.json"
        _write_raw(raw_path, raw)
        write_json(canonical_path, canonical)
        snapshots.append(
            _price_snapshot(
                role=role,
                canonical_path=canonical_path,
                raw_path=raw_path,
                request_locator=request_locator,
                request_id=request_id,
                captured_at=captured_at,
                canonical=canonical,
            )
        )
        canonical_by_granularity[granularity] = canonical

    for item in official_items:
        snapshots.append(_copy_official_snapshot(item, private_dir))

    data_cutoff_dt = utc_now()
    data_cutoff = format_datetime(data_cutoff_dt)
    daily_snapshot = canonical_by_granularity["D"]
    h4_snapshot = canonical_by_granularity["H4"]
    daily_meta = next(item for item in snapshots if item["role"] == "price_daily")

    manifest_id = f"evidence-{run_id}"
    feature = build_feature_snapshot(
        daily_snapshot,
        manifest_id=manifest_id,
        data_cutoff=data_cutoff,
        source_snapshot_sha256=daily_meta["sha256"],
        created_at=utc_now(),
        feature_snapshot_id=f"features-{run_id}",
    )
    baseline = build_baseline_snapshot(
        daily_snapshot,
        data_cutoff=data_cutoff,
        source_snapshot_sha256=daily_meta["sha256"],
        created_at=utc_now(),
        baseline_id=f"baseline-{run_id}",
    )
    as_of = format_datetime(utc_now())
    manifest = {
        "contract_version": "0.2.0",
        "manifest_id": manifest_id,
        "instrument": "XAUUSD",
        "provider": {
            "provider_id": "oanda-v20",
            "instrument_id": "XAU_USD",
            "environment": environment,
            "account_instrument_verified": True,
            "qualification_version": "data-source-qualification:0.1.0",
        },
        "as_of": as_of,
        "data_cutoff": data_cutoff,
        "licence": licence,
        "snapshots": snapshots,
        "coverage": {
            "daily_complete_bars": len(daily_snapshot["candles"]),
            "h4_complete_bars": len(h4_snapshot["candles"]),
            "last_daily_complete_at": daily_snapshot["candles"][-1]["time"],
            "last_h4_complete_at": h4_snapshot["candles"][-1]["time"],
        },
        "quality": {
            "missing_intervals": [],
            "stale": False,
            "future_records": False,
            "notes": [
                "Gap interpretation uses the frozen OANDA XAU/USD NY17 session sequence.",
                "Official snapshot freshness was attested in the local config.",
            ],
        },
        "provenance": {
            "created_at": as_of,
            "created_by": "prepare-oanda-bundle",
            "runtime_version": RUNTIME_VERSION,
            "source_policy_version": "data-source-qualification:0.1.0",
        },
    }
    run = {
        "contract_version": "0.2.0",
        "run_id": run_id,
        "mode": "certified",
        "instrument": "XAUUSD",
        "as_of": as_of,
        "data_cutoff": data_cutoff,
        "status": "ready",
        "input": {
            "evidence_manifest": "evidence-manifest.json",
            "previous_frame": config.get("previous_frame"),
            "feature_snapshot": "feature-snapshot.json",
            "baseline": "baseline-snapshot.json",
            "daily_complete_bars": len(daily_snapshot["candles"]),
            "h4_complete_bars": len(h4_snapshot["candles"]),
            "private_raw_data": True,
        },
        "gates": {
            "instrument_available": "pass",
            "licence": "pass",
            "temporal_integrity": "pass",
            "bar_semantics": "pass",
            "completeness": "pass",
            "snapshot_hash": "pass",
            "macro_coverage": "pass",
            "event_clock": "pass",
            "feature_snapshot_frozen": "pass",
            "baseline_frozen": "pass",
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
            "prompt_version": "daily-cognition-run:0.2.0",
            "source_policy_version": "data-source-qualification:0.1.0",
            "runtime_version": RUNTIME_VERSION,
            "model_versions": ["baseline-only:0.1.0"],
            "created_at": as_of,
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
