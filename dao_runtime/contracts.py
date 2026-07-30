"""JSON contract and integrity helpers."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"

DOCUMENT_SCHEMAS = {
    "run": "cognition-run.schema.json",
    "manifest": "evidence-manifest.schema.json",
    "feature": "feature-snapshot.schema.json",
    "baseline": "baseline-snapshot.schema.json",
    "evidence_item": "evidence-item.schema.json",
    "frame": "market-cognition-frame.schema.json",
    "forecast": "forecast-contract.schema.json",
    "delta": "cognition-delta.schema.json",
    "resolution": "resolution-record.schema.json",
}


class ContractError(ValueError):
    """One or more machine contract rules failed."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"date-time lacks timezone: {value}")
    return parsed


def format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_payload_sha256(payload: dict[str, Any], hash_field: str) -> str:
    candidate = copy.deepcopy(payload)
    candidate.pop(hash_field, None)
    return hashlib.sha256(canonical_json_bytes(candidate)).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def schema_errors(document: Any, schema_name: str, label: str) -> list[str]:
    schema = load_json(SCHEMA_DIR / schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{label}:{location}: {error.message}")
    return errors


def validate_document(document: Any, document_type: str, label: str) -> None:
    schema_name = DOCUMENT_SCHEMAS[document_type]
    errors = schema_errors(document, schema_name, label)
    if errors:
        raise ContractError(errors)


def probability_sum_errors(
    values: list[float | None],
    label: str,
    *,
    tolerance: float = 1e-9,
) -> list[str]:
    if any(value is None for value in values):
        return [f"{label}: probabilities contain null"]
    total = sum(float(value) for value in values)
    if abs(total - 1.0) > tolerance:
        return [f"{label}: probabilities sum to {total:.12g}, not 1"]
    return []


def unique_outcomes_errors(items: list[dict[str, Any]], label: str) -> list[str]:
    outcomes = [item.get("outcome_id") or item.get("resolution_outcome_id") for item in items]
    if len(outcomes) != 3 or set(outcomes) != {"up", "down", "range"}:
        return [f"{label}: outcomes must contain up/down/range exactly once"]
    return []
