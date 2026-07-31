"""Cross-file validation for one cognition run bundle."""

from __future__ import annotations

import json
import math
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from .contracts import (
    ContractError,
    canonical_json_bytes,
    canonical_payload_sha256,
    load_json,
    parse_datetime,
    probability_sum_errors,
    schema_errors,
    sha256_bytes,
    sha256_file,
    unique_outcomes_errors,
)
from .features import classify_normalized_change


CORE_ROLES = {
    "instrument_spec",
    "price_daily",
    "price_h4",
    "macro_rates",
    "macro_usd",
    "event_clock",
}
TERMINAL_STATUSES = {"ready", "completed", "resolved"}
SECRET_PATTERNS = (
    re.compile(r"authorization\s*:\s*bearer", re.IGNORECASE),
    re.compile(r"\boanda_api_token\b", re.IGNORECASE),
    re.compile(r"\boanda_account_id\b", re.IGNORECASE),
    re.compile(r'"accountID"\s*:', re.IGNORECASE),
)
DECIMAL_TOLERANCE = Decimal("1e-9")
GC_INSTRUMENT_PATTERN = re.compile(r"^GC[FGHJKMNQUVXZ][0-9]{2}$")
GC_PROTOCOL_ID = "gc-single-contract-direction-5d:0.1.0"
XAUUSD_PROTOCOL_ID = "xauusd-direction-5d:0.2.0"


def _add_schema_errors(
    errors: list[str], document: Any, document_type: str, label: str
) -> None:
    schema_by_type = {
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
    errors.extend(schema_errors(document, schema_by_type[document_type], label))


def _resolve_bundle_ref(root: Path, value: str, label: str, errors: list[str]) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        errors.append(f"{label}: absolute paths are forbidden")
        return root / "__invalid__"
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        errors.append(f"{label}: path escapes run directory")
        return root / "__invalid__"
    return resolved


def _resolve_private_ref(
    private_root: Path,
    value: str,
    label: str,
    errors: list[str],
) -> Path:
    if not value.startswith("private://"):
        errors.append(f"{label}: private reference must start with private://")
        return private_root / "__invalid__"
    relative = Path(value.removeprefix("private://"))
    if relative.is_absolute():
        errors.append(f"{label}: private reference must be relative")
        return private_root / "__invalid__"
    resolved = (private_root / relative).resolve()
    try:
        resolved.relative_to(private_root.resolve())
    except ValueError:
        errors.append(f"{label}: private reference escapes private root")
        return private_root / "__invalid__"
    return resolved


def _load_ref(
    root: Path,
    value: str | None,
    label: str,
    errors: list[str],
) -> Any | None:
    if value is None:
        return None
    path = _resolve_bundle_ref(root, value, label, errors)
    if not path.is_file():
        errors.append(f"{label}: referenced file does not exist: {value}")
        return None
    try:
        return load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: invalid JSON: {exc}")
        return None


def _time_leq(
    left: str,
    right: str,
    label: str,
    errors: list[str],
) -> None:
    try:
        if parse_datetime(left) > parse_datetime(right):
            errors.append(f"{label}: {left} is after {right}")
    except (TypeError, ValueError) as exc:
        errors.append(f"{label}: invalid date-time: {exc}")


def _check_secret_leak(document: Any, label: str, errors: list[str]) -> None:
    text = json.dumps(document, ensure_ascii=False)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"{label}: possible credential or account identifier leak")


def _probabilities_by_outcome(
    items: list[dict[str, Any]],
    outcome_field: str,
) -> dict[str, float | None]:
    return {item[outcome_field]: item.get("probability") for item in items}


def _close(left: float, right: float, tolerance: float = 1e-9) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def _decimal_close(
    left: Decimal,
    right: Decimal,
    tolerance: Decimal = DECIMAL_TOLERANCE,
) -> bool:
    scale = max(Decimal(1), abs(left), abs(right))
    return abs(left - right) <= tolerance * scale


def _validate_bundle(
    run_dir: Path,
    *,
    private_root: Path | None = None,
    raise_on_error: bool = True,
) -> list[str]:
    """Validate schemas, cross-file semantics and private hashes."""

    root = run_dir.resolve()
    errors: list[str] = []
    run_path = root / "run.json"
    if not run_path.is_file():
        errors.append("run.json: missing")
        if raise_on_error:
            raise ContractError(errors)
        return errors
    try:
        run = load_json(run_path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"run.json: invalid JSON: {exc}")
        if raise_on_error:
            raise ContractError(errors)
        return errors

    _add_schema_errors(errors, run, "run", "run.json")
    _check_secret_leak(run, "run.json", errors)

    mode = run.get("mode")
    status = run.get("status")
    run_input = run.get("input", {})
    outputs = run.get("outputs", {})
    as_of = run.get("as_of")
    data_cutoff = run.get("data_cutoff")
    instrument = run.get("instrument")
    is_gc = isinstance(instrument, str) and bool(
        GC_INSTRUMENT_PATTERN.fullmatch(instrument)
    )
    if isinstance(as_of, str) and isinstance(data_cutoff, str):
        _time_leq(data_cutoff, as_of, "run.data_cutoff", errors)

    manifest = _load_ref(
        root, run_input.get("evidence_manifest"), "run.input.evidence_manifest", errors
    )
    feature = _load_ref(
        root, run_input.get("feature_snapshot"), "run.input.feature_snapshot", errors
    )
    baseline = _load_ref(root, run_input.get("baseline"), "run.input.baseline", errors)

    if mode == "certified" and status in TERMINAL_STATUSES and private_root is None:
        errors.append(
            "certified terminal run requires --private-root for raw hash verification"
        )

    snapshots_by_role: dict[str, dict[str, Any]] = {}
    if manifest is not None:
        _add_schema_errors(errors, manifest, "manifest", "evidence-manifest.json")
        _check_secret_leak(manifest, "evidence-manifest.json", errors)
        if manifest.get("instrument") != run.get("instrument"):
            errors.append("manifest instrument does not match run")
        if manifest.get("data_cutoff") != data_cutoff:
            errors.append("manifest data_cutoff does not match run")
        if manifest.get("as_of") != as_of:
            errors.append("manifest as_of does not match run")
        provider = manifest.get("provider", {})
        if is_gc:
            contract = manifest.get("futures_contract", {})
            if contract.get("contract_code") != instrument:
                errors.append("futures contract_code does not match run instrument")
            if provider.get("instrument_id") != instrument:
                errors.append("futures provider instrument_id does not match run")
            sessions = contract.get("resolution_sessions", [])
            if isinstance(sessions, list):
                expected_session_hash = sha256_bytes(canonical_json_bytes(sessions))
                if (
                    contract.get("resolution_session_sequence_sha256")
                    != expected_session_hash
                ):
                    errors.append("futures resolution session hash mismatch")
                try:
                    first_position = date.fromisoformat(
                        contract["first_position_date"]
                    )
                    last_trade = date.fromisoformat(contract["last_trade_date"])
                    parsed_sessions = [parse_datetime(value) for value in sessions]
                    if parsed_sessions != sorted(parsed_sessions):
                        errors.append(
                            "futures resolution sessions must be increasing"
                        )
                    if any(
                        value.date() >= first_position
                        or value.date() >= last_trade
                        for value in parsed_sessions
                    ):
                        errors.append(
                            "futures resolution window reaches delivery lifecycle"
                        )
                except (KeyError, TypeError, ValueError) as exc:
                    errors.append(f"invalid futures contract lifecycle: {exc}")
        elif manifest.get("futures_contract") is not None:
            errors.append("XAUUSD manifest cannot contain futures_contract")

        snapshots = manifest.get("snapshots", [])
        snapshot_ids = [item.get("snapshot_id") for item in snapshots]
        if len(snapshot_ids) != len(set(snapshot_ids)):
            errors.append("manifest snapshot_id values must be unique")
        roles = [item.get("role") for item in snapshots]
        if len(roles) != len(set(roles)):
            errors.append("manifest snapshot roles must be unique")
        missing_roles = CORE_ROLES - set(roles)
        if is_gc and "contract_calendar" not in roles:
            missing_roles.add("contract_calendar")
        if missing_roles:
            errors.append(
                "manifest missing certified roles: " + ", ".join(sorted(missing_roles))
            )
        snapshots_by_role = {item["role"]: item for item in snapshots if "role" in item}

        if isinstance(as_of, str) and isinstance(data_cutoff, str):
            verified_at = manifest.get("licence", {}).get("verified_at")
            if isinstance(verified_at, str):
                _time_leq(verified_at, data_cutoff, "manifest.licence.verified_at", errors)
            for snapshot in snapshots:
                snapshot_id = snapshot.get("snapshot_id", "<unknown>")
                for field in ("available_at",):
                    value = snapshot.get(field)
                    if isinstance(value, str):
                        _time_leq(
                            value,
                            data_cutoff,
                            f"manifest.{snapshot_id}.{field}",
                            errors,
                        )
                captured_at = snapshot.get("captured_at")
                if isinstance(captured_at, str):
                    _time_leq(
                        captured_at,
                        as_of,
                        f"manifest.{snapshot_id}.captured_at",
                        errors,
                    )
                    try:
                        age_seconds = (
                            parse_datetime(data_cutoff) - parse_datetime(captured_at)
                        ).total_seconds()
                        max_age = snapshot.get("freshness_max_seconds")
                        if (
                            isinstance(max_age, int)
                            and age_seconds > max_age
                        ):
                            errors.append(
                                f"manifest.{snapshot_id}: snapshot is stale "
                                f"({age_seconds:.0f}s > {max_age}s)"
                            )
                    except (TypeError, ValueError) as exc:
                        errors.append(
                            f"manifest.{snapshot_id}: invalid freshness time: {exc}"
                        )
                if snapshot.get("role") != "event_clock":
                    last_observed_at = snapshot.get("last_observed_at")
                    if isinstance(last_observed_at, str):
                        _time_leq(
                            last_observed_at,
                            data_cutoff,
                            f"manifest.{snapshot_id}.last_observed_at",
                            errors,
                        )

        coverage = manifest.get("coverage", {})
        if coverage.get("daily_complete_bars") != run_input.get("daily_complete_bars"):
            errors.append("run daily_complete_bars does not match manifest coverage")
        if coverage.get("h4_complete_bars") != run_input.get("h4_complete_bars"):
            errors.append("run h4_complete_bars does not match manifest coverage")

        if private_root is not None:
            private_root = private_root.resolve()
            for snapshot in snapshots:
                snapshot_id = snapshot.get("snapshot_id", "<unknown>")
                private_ref = snapshot.get("private_location_ref")
                if isinstance(private_ref, str):
                    private_path = _resolve_private_ref(
                        private_root, private_ref, snapshot_id, errors
                    )
                    if not private_path.is_file():
                        errors.append(f"{snapshot_id}: private snapshot file missing")
                    else:
                        if sha256_file(private_path) != snapshot.get("sha256"):
                            errors.append(f"{snapshot_id}: private snapshot hash mismatch")
                        if private_path.stat().st_size != snapshot.get("bytes"):
                            errors.append(f"{snapshot_id}: private snapshot byte count mismatch")
                source_ref = snapshot.get("source_response_location_ref")
                source_hash = snapshot.get("source_response_sha256")
                if source_ref is None or source_hash is None:
                    errors.append(f"{snapshot_id}: source response reference/hash missing")
                elif isinstance(source_ref, str):
                    source_path = _resolve_private_ref(
                        private_root, source_ref, f"{snapshot_id}.source", errors
                    )
                    if not source_path.is_file():
                        errors.append(f"{snapshot_id}: source response file missing")
                    elif sha256_file(source_path) != source_hash:
                        errors.append(f"{snapshot_id}: source response hash mismatch")

    if feature is not None:
        _add_schema_errors(errors, feature, "feature", "feature-snapshot.json")
        if feature.get("instrument") != instrument:
            errors.append("feature instrument does not match run")
        if feature.get("data_cutoff") != data_cutoff:
            errors.append("feature data_cutoff does not match run")
        if manifest is not None and feature.get("source_manifest_id") != manifest.get(
            "manifest_id"
        ):
            errors.append("feature source_manifest_id does not match manifest")
        expected = canonical_payload_sha256(feature, "feature_payload_sha256")
        if feature.get("feature_payload_sha256") != expected:
            errors.append("feature payload hash mismatch")
        daily = snapshots_by_role.get("price_daily")
        if daily and feature.get("atr20", {}).get("input_snapshot_sha256") != daily.get(
            "sha256"
        ):
            errors.append("feature ATR input hash does not match daily snapshot")
        if isinstance(data_cutoff, str) and isinstance(
            feature.get("reference_session"), str
        ):
            _time_leq(
                feature["reference_session"],
                data_cutoff,
                "feature.reference_session",
                errors,
            )

    if baseline is not None:
        _add_schema_errors(errors, baseline, "baseline", "baseline-snapshot.json")
        if baseline.get("instrument") != instrument:
            errors.append("baseline instrument does not match run")
        expected_protocol = GC_PROTOCOL_ID if is_gc else XAUUSD_PROTOCOL_ID
        if baseline.get("protocol_id") != expected_protocol:
            errors.append("baseline protocol does not match run instrument")
        if baseline.get("data_cutoff") != data_cutoff:
            errors.append("baseline data_cutoff does not match run")
        expected = canonical_payload_sha256(baseline, "baseline_payload_sha256")
        if baseline.get("baseline_payload_sha256") != expected:
            errors.append("baseline payload hash mismatch")
        counts = baseline.get("training", {}).get("outcome_counts", {})
        sample_size = baseline.get("training", {}).get("sample_size")
        if isinstance(sample_size, int) and sum(counts.values()) != sample_size:
            errors.append("baseline outcome_counts do not sum to sample_size")
        probabilities = baseline.get("probabilities", {})
        errors.extend(
            probability_sum_errors(
                [probabilities.get(key) for key in ("up", "down", "range")],
                "baseline",
            )
        )
        if isinstance(sample_size, int) and sample_size > 0:
            for outcome in ("up", "down", "range"):
                expected_probability = counts.get(outcome, 0) / sample_size
                actual = probabilities.get(outcome)
                if isinstance(actual, (int, float)) and not _close(
                    actual, expected_probability
                ):
                    errors.append(
                        f"baseline probability for {outcome} does not match count"
                    )
        daily = snapshots_by_role.get("price_daily")
        if daily and baseline.get("source_daily_snapshot_sha256") != daily.get("sha256"):
            errors.append("baseline source hash does not match daily snapshot")

    evidence_items = _load_ref(
        root, outputs.get("evidence_items"), "run.outputs.evidence_items", errors
    )
    frame = _load_ref(root, outputs.get("frame"), "run.outputs.frame", errors)
    forecast = _load_ref(root, outputs.get("forecast"), "run.outputs.forecast", errors)
    delta = _load_ref(root, outputs.get("delta"), "run.outputs.delta", errors)
    resolution = _load_ref(
        root, outputs.get("resolution"), "run.outputs.resolution", errors
    )

    evidence_by_id: dict[str, dict[str, Any]] = {}
    if evidence_items is not None:
        if not isinstance(evidence_items, list) or not evidence_items:
            errors.append("evidence-items.json must contain a non-empty array")
        else:
            for index, item in enumerate(evidence_items):
                _add_schema_errors(
                    errors, item, "evidence_item", f"evidence-items.json[{index}]"
                )
                evidence_id = item.get("evidence_id")
                if evidence_id in evidence_by_id:
                    errors.append(f"duplicate evidence_id: {evidence_id}")
                evidence_by_id[evidence_id] = item
                if isinstance(item.get("available_at"), str) and isinstance(
                    data_cutoff, str
                ):
                    _time_leq(
                        item["available_at"],
                        data_cutoff,
                        f"evidence {evidence_id}.available_at",
                        errors,
                    )

    if frame is not None:
        _add_schema_errors(errors, frame, "frame", "market-cognition-frame.json")
        if frame.get("instrument") != run.get("instrument"):
            errors.append("frame instrument does not match run")
        if frame.get("data_cutoff") != data_cutoff:
            errors.append("frame data_cutoff does not match run")
        expected_protocol = GC_PROTOCOL_ID if is_gc else XAUUSD_PROTOCOL_ID
        if (
            frame.get("provenance", {}).get("resolution_protocol_version")
            != expected_protocol
        ):
            errors.append("frame protocol does not match run instrument")
        posterior = frame.get("state", {}).get("posterior", {})
        errors.extend(
            probability_sum_errors(
                [posterior.get(key) for key in ("up", "down", "range")],
                "frame state posterior",
            )
        )
        scenarios = frame.get("scenarios", [])
        errors.extend(unique_outcomes_errors(scenarios, "frame scenarios"))
        forecast_abstain = frame.get("abstention", {}).get("forecast", {}).get("abstain")
        scenario_probabilities = [item.get("probability") for item in scenarios]
        if forecast_abstain is False:
            errors.extend(
                probability_sum_errors(scenario_probabilities, "frame scenarios")
            )
        elif forecast_abstain is True and any(
            value is not None for value in scenario_probabilities
        ):
            errors.append("abstained frame scenarios must use null probabilities")
        refs = set(frame.get("evidence_refs", [])) | set(
            frame.get("counterevidence_refs", [])
        )
        missing_refs = refs - set(evidence_by_id)
        if missing_refs:
            errors.append(
                "frame references unknown evidence: " + ", ".join(sorted(missing_refs))
            )
        if mode == "certified" and status in {"completed", "resolved"}:
            if frame.get("provenance", {}).get("certification_level") != "Q1":
                errors.append("completed certified frame must be a Q1 candidate")

    if forecast is not None:
        _add_schema_errors(errors, forecast, "forecast", "forecast-contract.json")
        if forecast.get("instrument") != instrument:
            errors.append("forecast instrument does not match run")
        expected_protocol = GC_PROTOCOL_ID if is_gc else XAUUSD_PROTOCOL_ID
        if (
            forecast.get("resolution_rule", {}).get("protocol_id")
            != expected_protocol
        ):
            errors.append("forecast protocol does not match run instrument")
        if frame is not None and forecast.get("frame_id") != frame.get("frame_id"):
            errors.append("forecast frame_id does not match frame")
        if forecast.get("data_cutoff") != data_cutoff:
            errors.append("forecast data_cutoff does not match run")
        outcomes = forecast.get("outcomes", [])
        errors.extend(unique_outcomes_errors(outcomes, "forecast outcomes"))
        abstain = forecast.get("forecast_abstention", {}).get("abstain")
        outcome_probabilities = [item.get("probability") for item in outcomes]
        if abstain is False:
            errors.extend(
                probability_sum_errors(outcome_probabilities, "forecast outcomes")
            )
        elif abstain is True and any(value is not None for value in outcome_probabilities):
            errors.append("abstained forecast outcomes must use null probabilities")

        if baseline is not None:
            forecast_baseline = forecast.get("baseline", {})
            if forecast_baseline.get("baseline_ref") != run_input.get("baseline"):
                errors.append("forecast baseline_ref does not match run")
            if forecast_baseline.get("probabilities") != baseline.get("probabilities"):
                errors.append("forecast frozen baseline probabilities do not match snapshot")
            if forecast_baseline.get("sample_size") != baseline.get("training", {}).get(
                "sample_size"
            ):
                errors.append("forecast baseline sample size does not match snapshot")
            if forecast_baseline.get("source_snapshot_sha256") != baseline.get(
                "source_daily_snapshot_sha256"
            ):
                errors.append("forecast baseline source hash does not match snapshot")
            if abstain is False:
                model_probabilities = _probabilities_by_outcome(outcomes, "outcome_id")
                if set(model_probabilities) == {"up", "down", "range"}:
                    for outcome in ("up", "down", "range"):
                        if not _close(
                            float(model_probabilities[outcome]),
                            float(baseline["probabilities"][outcome]),
                        ):
                            errors.append(
                                "v0.2 first-run forecast probabilities must equal "
                                f"the frozen baseline ({outcome})"
                            )

        if feature is not None:
            frozen = forecast.get("resolution_rule", {}).get("frozen_values", {})
            expected_pairs = {
                "feature_snapshot_ref": run_input.get("feature_snapshot"),
                "feature_payload_sha256": feature.get("feature_payload_sha256"),
                "reference_session": feature.get("reference_session"),
                "reference_close": feature.get("reference_close"),
                "atr20_at_cutoff": feature.get("atr20", {}).get("value"),
                "calendar_id": feature.get("trading_calendar", {}).get("calendar_id"),
                "calendar_version": feature.get("trading_calendar", {}).get("version"),
            }
            if is_gc and manifest is not None:
                contract = manifest.get("futures_contract", {})
                expected_pairs.update(
                    {
                        "contract_code": instrument,
                        "first_position_date": contract.get("first_position_date"),
                        "last_trade_date": contract.get("last_trade_date"),
                        "resolution_session_sequence_sha256": contract.get(
                            "resolution_session_sequence_sha256"
                        ),
                    }
                )
            for field, expected_value in expected_pairs.items():
                if frozen.get(field) != expected_value:
                    errors.append(f"forecast frozen {field} does not match feature snapshot")

        if frame is not None:
            frame_probabilities = _probabilities_by_outcome(
                frame.get("scenarios", []), "resolution_outcome_id"
            )
            forecast_probabilities = _probabilities_by_outcome(outcomes, "outcome_id")
            if frame_probabilities != forecast_probabilities:
                errors.append("frame scenario probabilities do not match forecast")
        if isinstance(forecast.get("created_at"), str) and isinstance(data_cutoff, str):
            _time_leq(
                data_cutoff,
                forecast["created_at"],
                "run.data_cutoff versus forecast.created_at",
                errors,
            )

    if delta is not None:
        _add_schema_errors(errors, delta, "delta", "cognition-delta.json")
        if frame is not None and delta.get("current_frame_id") != frame.get("frame_id"):
            errors.append("delta current_frame_id does not match frame")

    if resolution is not None:
        _add_schema_errors(errors, resolution, "resolution", "resolution-record.json")
        if forecast is not None and resolution.get(
            "protocol_version"
        ) != forecast.get("resolution_rule", {}).get("protocol_id"):
            errors.append("resolution protocol does not match forecast")
        if forecast is not None:
            if resolution.get("forecast_id") != forecast.get("forecast_id"):
                errors.append("resolution forecast_id does not match forecast")
            if resolution.get("frame_id") != forecast.get("frame_id"):
                errors.append("resolution frame_id does not match forecast")
        if resolution.get("status") == "resolved" and forecast is not None:
            observed = resolution["observed"]
            reference = Decimal(str(observed["reference_close"]))
            diagnostic = Decimal(str(observed["diagnostic_close_3"]))
            final = Decimal(str(observed["resolution_close_5"]))
            atr = Decimal(str(observed["atr20_at_cutoff"]))
            normalized_3 = (diagnostic - reference) / atr
            normalized_5 = (final - reference) / atr
            if not _decimal_close(
                Decimal(str(observed["normalized_change_3"])), normalized_3
            ):
                errors.append("resolution normalized_change_3 is not reproducible")
            if not _decimal_close(
                Decimal(str(observed["normalized_change_5"])), normalized_5
            ):
                errors.append("resolution normalized_change_5 is not reproducible")
            expected_outcome = classify_normalized_change(normalized_5)
            if observed.get("outcome_id") != expected_outcome:
                errors.append("resolution outcome_id is not reproducible")

            forecast_abstains = (
                forecast.get("forecast_abstention", {}).get("abstain") is True
            )
            if forecast_abstains:
                errors.append("resolved resolution cannot score an abstained forecast")
            else:
                model_probabilities = _probabilities_by_outcome(
                    forecast["outcomes"], "outcome_id"
                )
                baseline_probabilities = forecast["baseline"]["probabilities"]
                one_hot = {
                    outcome: 1.0 if outcome == expected_outcome else 0.0
                    for outcome in ("up", "down", "range")
                }
                brier = sum(
                    (float(model_probabilities[outcome]) - one_hot[outcome]) ** 2
                    for outcome in one_hot
                ) / 3.0
                log_loss = -math.log(
                    max(float(model_probabilities[expected_outcome]), 1e-15)
                )
                baseline_brier = sum(
                    (float(baseline_probabilities[outcome]) - one_hot[outcome]) ** 2
                    for outcome in one_hot
                ) / 3.0
                if baseline_brier == 0:
                    errors.append("resolution baseline Brier is zero; BSS is undefined")
                else:
                    bss = 1.0 - brier / baseline_brier
                    expected_scores = {
                        "brier_multiclass": brier,
                        "log_loss": log_loss,
                        "baseline_brier": baseline_brier,
                        "brier_skill_score": bss,
                    }
                    for field, expected_value in expected_scores.items():
                        if not _close(
                            float(resolution["scoring"][field]), expected_value
                        ):
                            errors.append(f"resolution {field} is not reproducible")

    if errors and raise_on_error:
        raise ContractError(errors)
    return errors


def validate_bundle(
    run_dir: Path,
    *,
    private_root: Path | None = None,
    raise_on_error: bool = True,
) -> list[str]:
    """Reject malformed bundles without leaking an implementation traceback."""

    try:
        errors = _validate_bundle(
            run_dir,
            private_root=private_root,
            raise_on_error=False,
        )
    except (ArithmeticError, KeyError, TypeError, ValueError) as exc:
        errors = [f"bundle semantic validation could not continue: {exc}"]
    if errors and raise_on_error:
        raise ContractError(errors)
    return errors
