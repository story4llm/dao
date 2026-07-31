"""Kaggle-sourced COMEX GC daily bundle preparation.

The GC research track has exactly one data source: the public Kaggle dataset
downloaded through the official ``kaggle`` CLI. Authentication is fully owned
by the CLI (``kaggle auth login``, ``KAGGLE_API_TOKEN``, ``~/.kaggle``); this
module never reads, parses or stores Kaggle credentials.
"""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .contracts import format_datetime, load_json, sha256_file, write_json
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
GC_PROTOCOL_ID = "gc-kaggle-daily-direction-5d:0.1.0"
GC_CALENDAR_ID = "kaggle-gc-observed-daily"
GC_CALENDAR_VERSION = "0.1.0"
DEFAULT_DATASET_REF = "youneseloiarm/comex-gold-futures-dataset-gc-contract"
DATASET_REF_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$"
)
REQUIRED_DAILY_BARS = ATR_PERIOD + HORIZON + MIN_BASELINE_SAMPLES + 1
DEFAULT_FRESHNESS_MAX_DAYS = 10

DATE_COLUMNS = {"date", "datetime", "timestamp", "time"}
VOLUME_COLUMNS = {"volume", "vol"}
PRICE_COLUMNS = {"open", "high", "low", "close"}
REDACTED_LINE = re.compile(r"token|secret|key|authorization|credential", re.IGNORECASE)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _redact_cli_output(text: str, limit: int = 400) -> str:
    kept = [
        line
        for line in (text or "").splitlines()
        if line.strip() and not REDACTED_LINE.search(line)
    ]
    return " | ".join(kept)[:limit] or "no diagnostic output"


def _kaggle_executable() -> str:
    executable = shutil.which("kaggle")
    if executable is None:
        raise RuntimeError(
            "kaggle CLI not found; install it with "
            "python -m pip install -e '.[kaggle]' and authenticate with "
            "kaggle auth login"
        )
    return executable


def _run_kaggle(args: list[str]) -> str:
    executable = _kaggle_executable()
    result = subprocess.run(  # noqa: S603 - fixed executable, no shell
        [executable, *args],
        capture_output=True,
        text=True,
        timeout=600,
        shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"kaggle {' '.join(args[:2])} failed: "
            + _redact_cli_output(result.stderr or result.stdout)
        )
    return result.stdout


def _kaggle_cli_version() -> str:
    return _run_kaggle(["--version"]).strip() or "unknown"


def _validate_dataset_ref(value: Any) -> str:
    if not isinstance(value, str) or not DATASET_REF_PATTERN.fullmatch(value):
        raise ValueError(
            "config.dataset_ref must look like <owner>/<dataset-slug>"
        )
    return value


def _download_dataset(dataset_ref: str, kaggle_dir: Path) -> Path:
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    _run_kaggle(["datasets", "metadata", dataset_ref, "-p", str(kaggle_dir)])
    metadata_path = kaggle_dir / "dataset-metadata.json"
    if not metadata_path.is_file():
        raise RuntimeError("kaggle metadata download did not produce dataset-metadata.json")
    _run_kaggle(["datasets", "download", dataset_ref, "-p", str(kaggle_dir), "-o"])
    archives = sorted(path for path in kaggle_dir.glob("*.zip") if path.is_file())
    if len(archives) != 1:
        raise RuntimeError(
            f"expected exactly one downloaded dataset archive, found {len(archives)}"
        )
    archive_path = kaggle_dir / "original.zip"
    if archives[0] != archive_path:
        archives[0].rename(archive_path)
    return archive_path


def _safe_extract(archive_path: Path, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    resolved_destination = destination.resolve()
    extracted: list[Path] = []
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            member = Path(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise ValueError(
                    f"dataset archive member escapes extraction directory: {info.filename}"
                )
            target = (destination / member).resolve()
            if not target.is_relative_to(resolved_destination):
                raise ValueError(
                    f"dataset archive member escapes extraction directory: {info.filename}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            extracted.append(target)
    if not extracted:
        raise ValueError("dataset archive contains no files")
    return extracted


def _normalized_header(row: list[str]) -> list[str]:
    return [cell.strip().lower() for cell in row]


def _column_index(
    header: list[str],
    logical: str,
    column_mapping: dict[str, str] | None,
) -> int | None:
    if column_mapping and logical in column_mapping:
        wanted = str(column_mapping[logical]).strip().lower()
        return header.index(wanted) if wanted in header else None
    if logical == "date":
        candidates = DATE_COLUMNS
    elif logical == "volume":
        candidates = VOLUME_COLUMNS
    else:
        candidates = {logical}
    for index, cell in enumerate(header):
        if cell in candidates:
            return index
    return None


def _is_candidate_csv(path: Path, column_mapping: dict[str, str] | None) -> bool:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            first = next(csv.reader(handle), None)
    except (OSError, UnicodeDecodeError, csv.Error):
        return False
    if not first:
        return False
    header = _normalized_header(first)
    return all(
        _column_index(header, logical, column_mapping) is not None
        for logical in ("date", "open", "high", "low", "close")
    )


def _select_dataset_csv(
    extracted: list[Path],
    dataset_file: str | None,
    column_mapping: dict[str, str] | None,
) -> Path:
    csv_files = [path for path in extracted if path.suffix.lower() == ".csv"]
    if dataset_file is not None:
        by_name = {path.name: path for path in csv_files}
        if dataset_file not in by_name:
            raise ValueError(
                f"config.dataset_file {dataset_file!r} is not present in the dataset"
            )
        return by_name[dataset_file]
    candidates = [
        path for path in csv_files if _is_candidate_csv(path, column_mapping)
    ]
    if len(candidates) != 1:
        raise ValueError(
            "could not uniquely identify one OHLCV csv in the dataset; "
            f"found {len(candidates)} candidates. Set config.dataset_file explicitly."
        )
    return candidates[0]


def _parse_observation_date(value: str) -> str:
    text = value.strip()
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%m/%d/%Y", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        raise ValueError(f"unparseable observation date: {value!r}")
    return f"{parsed.date().isoformat()}T00:00:00Z"


def _positive_price(value: str, label: str) -> Decimal:
    try:
        parsed = Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"{label} is not a decimal price") from None
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{label} must be a positive finite price")
    return parsed


def normalize_kaggle_gc_csv(
    csv_path: Path,
    *,
    dataset_ref: str,
    column_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Normalize one Kaggle GC daily OHLCV csv into the canonical snapshot."""

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        first = next(reader, None)
        if not first:
            raise ValueError("dataset csv is empty")
        header = _normalized_header(first)
        indexes: dict[str, int | None] = {
            logical: _column_index(header, logical, column_mapping)
            for logical in ("date", "open", "high", "low", "close", "volume")
        }
        missing = [
            logical
            for logical in ("date", "open", "high", "low", "close")
            if indexes[logical] is None
        ]
        if missing:
            raise ValueError(
                "dataset csv is missing required columns: " + ", ".join(missing)
            )

        rows_by_time: dict[str, dict[str, Any]] = {}
        for line_number, row in enumerate(reader, start=2):
            if not row or not any(cell.strip() for cell in row):
                continue
            label = f"csv line {line_number}"
            try:
                time = _parse_observation_date(row[indexes["date"]])
                price = {
                    field[0]: _positive_price(
                        row[indexes[field]], f"{label} {field}"
                    )
                    for field in ("open", "high", "low", "close")
                }
            except IndexError:
                raise ValueError(f"{label} has fewer cells than the header") from None
            if price["h"] < max(price.values()) or price["l"] > min(price.values()):
                raise ValueError(f"{label} has invalid OHLC bounds")
            volume = 0
            volume_index = indexes["volume"]
            if volume_index is not None and volume_index < len(row):
                cell = row[volume_index].strip()
                if cell:
                    try:
                        volume = int(Decimal(cell))
                    except (InvalidOperation, ValueError):
                        raise ValueError(f"{label} volume is not numeric") from None
            if volume < 0:
                raise ValueError(f"{label} volume must be non-negative")
            candle = {
                "time": time,
                "price": {
                    field: format(price[field], "f") for field in ("o", "h", "l", "c")
                },
                "volume": volume,
                "complete": True,
            }
            existing = rows_by_time.get(time)
            if existing is None:
                rows_by_time[time] = candle
            elif existing != candle:
                raise ValueError(
                    f"conflicting rows for observation date {time[:10]}"
                )
            # ponytail: identical duplicate rows are silently dropped by the dict

    candles = sorted(rows_by_time.values(), key=lambda item: item["time"])
    if len(candles) < REQUIRED_DAILY_BARS:
        raise ValueError(
            f"dataset requires at least {REQUIRED_DAILY_BARS} daily observations, "
            f"found {len(candles)}"
        )
    return {
        "instrument": "GC",
        "provider": "kaggle",
        "dataset_ref": dataset_ref,
        "granularity": "D",
        "price_component": "CLOSE",
        "timestamp_semantics": "dataset_observation_date",
        "candles": candles,
    }


def _dataset_staleness_days(canonical: dict[str, Any], now: datetime) -> int:
    last = canonical["candles"][-1]["time"]
    last_date = datetime.fromisoformat(last.replace("Z", "+00:00")).date()
    return (now.date() - last_date).days


def _price_daily_snapshot(
    *,
    dataset_ref: str,
    canonical_path: Path,
    archive_path: Path,
    downloaded_at: str,
    canonical: dict[str, Any],
    freshness_max_seconds: int,
) -> dict[str, Any]:
    candles = canonical["candles"]
    return {
        "snapshot_id": "snapshot-price-daily",
        "role": "price_daily",
        "private_location_ref": f"private://{canonical_path.name}",
        "request_locator_redacted": f"kaggle datasets download {dataset_ref}",
        "request_id": None,
        "source_locator": f"https://www.kaggle.com/datasets/{dataset_ref}",
        "captured_at": downloaded_at,
        "available_at": downloaded_at,
        "sha256": sha256_file(canonical_path),
        "source_response_location_ref": f"private://kaggle/{archive_path.name}",
        "source_response_sha256": sha256_file(archive_path),
        "bytes": canonical_path.stat().st_size,
        "record_count": len(candles),
        "first_observed_at": candles[0]["time"],
        "last_observed_at": candles[-1]["time"],
        "source_timezone": "UTC",
        "timestamp_semantics": "dataset_observation_date",
        "complete_only": True,
        "transform_id": "kaggle-gc-daily-csv:0.1.0",
        "freshness_max_seconds": freshness_max_seconds,
    }


def _base_run(
    *,
    run_id: str,
    as_of: str,
    data_cutoff: str,
    previous_frame: Any,
    created_at: str,
) -> dict[str, Any]:
    return {
        "contract_version": "0.3.0",
        "run_id": run_id,
        "mode": "automated",
        "instrument": "GC",
        "as_of": as_of,
        "data_cutoff": data_cutoff,
        "status": "ready",
        "input": {
            "evidence_manifest": "evidence-manifest.json",
            "previous_frame": previous_frame,
            "feature_snapshot": "feature-snapshot.json",
            "baseline": "baseline-snapshot.json",
            "daily_complete_bars": 0,
            "h4_complete_bars": None,
            "private_raw_data": True,
        },
        "gates": {
            "instrument_available": "pass",
            "licence": "unknown",
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
            "prompt_version": "daily-cognition-run:0.3.0",
            "source_policy_version": "data-source-qualification:0.2.0",
            "runtime_version": RUNTIME_VERSION,
            "model_versions": ["gc-baseline-only:0.1.0"],
            "created_at": created_at,
        },
    }


def prepare_gc_bundle(
    config_path: Path,
    public_dir: Path,
    private_dir: Path,
) -> dict[str, Path]:
    """Download the Kaggle GC dataset and emit an automated ready-run skeleton."""

    config = load_json(config_path)
    if _contains_sensitive_config_key(config):
        raise ValueError("credentials must not appear in the bundle config")
    if _contains_placeholder(config):
        raise ValueError("example placeholders cannot be used for a GC bundle")
    run_id = config.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("config.run_id is required")
    mode = config.get("mode", "automated")
    if mode != "automated":
        raise ValueError(
            "the Kaggle GC track only supports mode=automated; "
            "certified CME semantics were removed"
        )
    dataset_ref = _validate_dataset_ref(config.get("dataset_ref", DEFAULT_DATASET_REF))
    dataset_file = config.get("dataset_file")
    if dataset_file is not None and not isinstance(dataset_file, str):
        raise ValueError("config.dataset_file must be a string or null")
    column_mapping = config.get("column_mapping")
    if column_mapping is not None and not isinstance(column_mapping, dict):
        raise ValueError("config.column_mapping must be an object or null")
    freshness_max_days = config.get("freshness_max_days", DEFAULT_FRESHNESS_MAX_DAYS)
    if not isinstance(freshness_max_days, int) or freshness_max_days <= 0:
        raise ValueError("config.freshness_max_days must be a positive integer")
    official_items = config.get("official_snapshots", [])
    roles = [item.get("role") for item in official_items]
    if set(roles) != OFFICIAL_ROLES or len(roles) != len(set(roles)):
        raise ValueError(
            "official_snapshots must contain macro_rates, macro_usd and event_clock once"
        )

    _ensure_empty_target(private_dir, "private_dir")
    _ensure_empty_target(public_dir, "public_dir")

    cli_version = _kaggle_cli_version()
    kaggle_dir = private_dir / "kaggle"
    archive_path = _download_dataset(dataset_ref, kaggle_dir)
    downloaded_at = format_datetime(utc_now())
    archive_sha256 = sha256_file(archive_path)
    extracted_root = (kaggle_dir / "extracted").resolve()
    extracted = _safe_extract(archive_path, extracted_root)
    csv_path = _select_dataset_csv(extracted, dataset_file, column_mapping)
    write_json(
        kaggle_dir / "download-manifest.json",
        {
            "dataset_ref": dataset_ref,
            "downloaded_at": downloaded_at,
            "kaggle_cli_version": cli_version,
            "archive": {"name": archive_path.name, "bytes": archive_path.stat().st_size, "sha256": archive_sha256},
            "metadata_sha256": sha256_file(kaggle_dir / "dataset-metadata.json"),
            "files": [
                {
                    "name": str(path.relative_to(extracted_root)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in extracted
            ],
            "selected_csv": csv_path.name,
        },
    )

    canonical = normalize_kaggle_gc_csv(
        csv_path, dataset_ref=dataset_ref, column_mapping=column_mapping
    )
    canonical_path = private_dir / "normalized-gc-daily.json"
    write_json(canonical_path, canonical)

    now = utc_now()
    as_of = format_datetime(now)
    data_cutoff = as_of
    run = _base_run(
        run_id=run_id,
        as_of=as_of,
        data_cutoff=data_cutoff,
        previous_frame=config.get("previous_frame"),
        created_at=as_of,
    )
    run["input"]["daily_complete_bars"] = len(canonical["candles"])

    staleness_days = _dataset_staleness_days(canonical, now)
    if staleness_days > freshness_max_days:
        run["status"] = "blocked"
        run["input"]["evidence_manifest"] = None
        run["input"]["feature_snapshot"] = None
        run["input"]["baseline"] = None
        run["gates"]["temporal_integrity"] = "fail"
        run["gates"]["feature_snapshot_frozen"] = "unknown"
        run["gates"]["baseline_frozen"] = "unknown"
        run["blocking_reasons"] = ["stale_dataset"]
        run_path = public_dir / "run.json"
        write_json(run_path, run)
        return {"run": run_path}

    snapshots = [
        _price_daily_snapshot(
            dataset_ref=dataset_ref,
            canonical_path=canonical_path,
            archive_path=archive_path,
            downloaded_at=downloaded_at,
            canonical=canonical,
            freshness_max_seconds=freshness_max_days * 86400,
        )
    ]
    for item in official_items:
        snapshots.append(_copy_official_snapshot(item, private_dir))

    daily_meta = snapshots[0]
    manifest_id = f"evidence-{run_id}"
    created_at = utc_now()
    feature = build_market_feature_snapshot(
        canonical,
        manifest_id=manifest_id,
        data_cutoff=data_cutoff,
        source_snapshot_sha256=daily_meta["sha256"],
        created_at=created_at,
        feature_snapshot_id=f"features-{run_id}",
        instrument="GC",
        reference_price_field="close",
        price_container="price",
        close_field="c",
        price_component="CLOSE",
        daily_alignment=None,
        alignment_timezone="UTC",
        timestamp_semantics="dataset_observation_date",
        calendar_id=GC_CALENDAR_ID,
        calendar_version=GC_CALENDAR_VERSION,
        runtime_version=RUNTIME_VERSION,
    )
    baseline = build_market_baseline_snapshot(
        canonical,
        data_cutoff=data_cutoff,
        source_snapshot_sha256=daily_meta["sha256"],
        created_at=created_at,
        baseline_id=f"baseline-{run_id}",
        instrument="GC",
        protocol_id=GC_PROTOCOL_ID,
        reference_price_field="close",
        price_container="price",
        close_field="c",
        daily_alignment=None,
        alignment_timezone="UTC",
        calendar_id=GC_CALENDAR_ID,
        calendar_version=GC_CALENDAR_VERSION,
        runtime_version=RUNTIME_VERSION,
        code_version="gc-baseline:0.1.0",
    )
    manifest = {
        "contract_version": "0.3.0",
        "manifest_id": manifest_id,
        "instrument": "GC",
        "provider": {
            "provider_id": "kaggle",
            "instrument_id": "GC",
            "dataset_ref": dataset_ref,
            "source_description": "Kaggle dataset derived from TradingView",
            "qualification": "exploratory",
            "certified_eligible": False,
            "qualification_version": "data-source-qualification:0.2.0",
        },
        "dataset": {
            "dataset_ref": dataset_ref,
            "dataset_file": csv_path.name,
            "downloaded_at": downloaded_at,
            "archive_sha256": archive_sha256,
            "kaggle_cli_version": cli_version,
        },
        "as_of": as_of,
        "data_cutoff": data_cutoff,
        "licence": {
            "name": "Kaggle dataset licence as published on the dataset page",
            "region_or_entity": "Kaggle",
            "version_or_effective_date": "unknown",
            "locator": f"https://www.kaggle.com/datasets/{dataset_ref}",
            "usage_scope": "unknown",
            "accepted_by_account_holder": False,
            "verified_at": downloaded_at,
        },
        "snapshots": snapshots,
        "coverage": {
            "daily_complete_bars": len(canonical["candles"]),
            "h4_complete_bars": None,
            "last_daily_complete_at": canonical["candles"][-1]["time"],
            "last_h4_complete_at": None,
        },
        "quality": {
            "missing_intervals": [],
            "stale": False,
            "future_records": False,
            "notes": [
                "Daily Close from a public Kaggle dataset; it is not the CME official settlement.",
                "Rows carry only an observation date; no per-record availability time is claimed.",
                "No single delivery-month identity is claimed for this series.",
            ],
        },
        "provenance": {
            "created_at": format_datetime(created_at),
            "created_by": "prepare-gc-bundle",
            "runtime_version": RUNTIME_VERSION,
            "source_policy_version": "data-source-qualification:0.2.0",
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
