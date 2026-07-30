#!/usr/bin/env python3
"""Validate the repository harness without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "harness.yaml",
    "docs/research/system-design.md",
    "docs/product/vision.md",
    "docs/product/prd-v0.1.md",
    "docs/product/trend-cognition-spec-v0.1.md",
    "evals/gold-standard-annotation-guide-v0.1.md",
    "evals/evaluation-contract-v0.2.md",
    "docs/data/data-source-qualification-matrix-v0.1.md",
    "evals/pilots/README.md",
    "evals/pilots/pilot-findings.md",
    "docs/architecture/domain-ontology.md",
    "docs/architecture/agent-protocol.md",
    "docs/harness/CONTEXT_MAP.md",
    "docs/harness/WORKFLOW.md",
    "docs/harness/QUALITY_GATES.md",
    "docs/harness/RESEARCH_POLICY.md",
    "docs/harness/DAILY_RUNBOOK.md",
    "docs/decisions/ADR-0003-separate-state-forecast-and-revision-evaluation.md",
    "docs/decisions/ADR-0004-github-harness-private-evidence-runtime.md",
    "docs/decisions/ADR-0005-machine-enforced-certified-runtime.md",
    "state/PROJECT_STATE.md",
    "state/DECISION_LOG.md",
    "state/OPEN_QUESTIONS.md",
    "tasks/TEMPLATE.md",
    "evals/README.md",
    "schemas/evidence-item.schema.json",
    "schemas/evidence-manifest.schema.json",
    "schemas/forecast-contract.schema.json",
    "schemas/market-cognition-frame.schema.json",
    "schemas/cognition-delta.schema.json",
    "schemas/annotation-record.schema.json",
    "schemas/resolution-record.schema.json",
    "schemas/cognition-run.schema.json",
    "schemas/feature-snapshot.schema.json",
    "schemas/baseline-snapshot.schema.json",
    "templates/research-note.md",
    "templates/forecast-record.yaml",
    "templates/market-cognition-frame.yaml",
    "templates/cognition-delta.yaml",
    "templates/annotation-record.yaml",
    "templates/resolution-record.yaml",
    "templates/cognition-run.json",
    "templates/private-bundle-config.example.json",
    "prompts/daily-cognition-run-v0.1.md",
    "prompts/daily-cognition-run-v0.2.md",
    "examples/runs/blocked-no-qualified-evidence/run.json",
    "examples/runs/blocked-no-qualified-evidence/explanation.md",
    "tasks/2026-07-30-first-runnable-cognition-loop.md",
    "tasks/2026-07-30-certified-runtime-hardening-v0.2.md",
    "dao_runtime/__init__.py",
    "dao_runtime/contracts.py",
    "dao_runtime/features.py",
    "dao_runtime/bundle.py",
    "dao_runtime/oanda.py",
    "dao_runtime/cli.py",
    "scripts/dao_runtime.py",
    "tests/test_features.py",
    "tests/test_bundle.py",
    "tests/test_oanda.py",
    ".github/workflows/validate.yml",
    "pyproject.toml",
    ".gitignore",
]

SCHEMA_REQUIREMENTS = {
    "evidence-manifest.schema.json": {
        "contract_version",
        "manifest_id",
        "instrument",
        "provider",
        "data_cutoff",
        "licence",
        "snapshots",
        "coverage",
        "quality",
        "provenance",
    },
    "evidence-item.schema.json": {
        "evidence_id",
        "dependency_group",
        "source_timezone",
        "bar_timestamp_semantics",
        "available_at",
        "availability_verified",
        "licence",
        "quality",
    },
    "forecast-contract.schema.json": {
        "contract_version",
        "forecast_id",
        "frame_id",
        "data_cutoff",
        "outcomes",
        "resolution_rule",
        "invalidation_conditions",
        "forecast_abstention",
    },
    "market-cognition-frame.schema.json": {
        "frame_id",
        "as_of",
        "data_cutoff",
        "scenarios",
        "invalidation_conditions",
        "risk",
        "abstention",
        "provenance",
    },
    "cognition-delta.schema.json": {
        "delta_id",
        "previous_frame_id",
        "current_frame_id",
        "posterior_delta",
        "revision_drivers",
        "temporal_audit",
    },
    "annotation-record.schema.json": {
        "record_id",
        "sample_id",
        "phase",
        "blinding",
        "temporal_audit",
        "certification",
    },
    "resolution-record.schema.json": {
        "resolution_id",
        "forecast_id",
        "protocol_version",
        "observed",
        "scoring",
        "audit",
    },
    "cognition-run.schema.json": {
        "contract_version",
        "run_id",
        "mode",
        "instrument",
        "as_of",
        "data_cutoff",
        "status",
        "input",
        "gates",
        "outputs",
        "blocking_reasons",
        "provenance",
    },
    "feature-snapshot.schema.json": {
        "contract_version",
        "feature_snapshot_id",
        "instrument",
        "data_cutoff",
        "source_manifest_id",
        "reference_session",
        "reference_close",
        "atr20",
        "bar_config",
        "trading_calendar",
        "feature_payload_sha256",
        "provenance",
    },
    "baseline-snapshot.schema.json": {
        "contract_version",
        "baseline_id",
        "instrument",
        "protocol_id",
        "data_cutoff",
        "method",
        "training",
        "probabilities",
        "normalization",
        "source_daily_snapshot_sha256",
        "feature_config_sha256",
        "baseline_payload_sha256",
        "provenance",
    },
}

LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
SKIP_LINK_PREFIXES = ("http://", "https://", "mailto:", "#", "sandbox:")


def validate_required_paths(errors: list[str]) -> None:
    for relative in REQUIRED_PATHS:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing required file: {relative}")
        elif path.stat().st_size == 0:
            errors.append(f"required file is empty: {relative}")


def validate_schemas(errors: list[str]) -> None:
    for path in sorted((ROOT / "schemas").glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON schema {path.relative_to(ROOT)}: {exc}")
            continue

        if payload.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{path.relative_to(ROOT)} must use JSON Schema 2020-12")
        try:
            Draft202012Validator.check_schema(payload)
        except SchemaError as exc:
            errors.append(
                f"invalid JSON Schema {path.relative_to(ROOT)}: {exc.message}"
            )

        expected = SCHEMA_REQUIREMENTS.get(path.name, set())
        required = set(payload.get("required", []))
        missing = expected - required
        if missing:
            errors.append(
                f"{path.relative_to(ROOT)} missing required contract fields: "
                + ", ".join(sorted(missing))
            )


def validate_instance(
    payload: object,
    schema_name: str,
    label: str,
    errors: list[str],
) -> None:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{label}:{location}: {error.message}")


def validate_internal_links(errors: list[str]) -> None:
    for markdown in sorted(ROOT.rglob("*.md")):
        if ".git" in markdown.parts:
            continue
        text = markdown.read_text(encoding="utf-8")
        for raw_target in LINK_PATTERN.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(SKIP_LINK_PREFIXES):
                continue
            file_part = target.split("#", 1)[0]
            if not file_part:
                continue
            resolved = (markdown.parent / file_part).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                errors.append(
                    f"{markdown.relative_to(ROOT)} links outside repository: {target}"
                )
                continue
            if not resolved.exists():
                errors.append(
                    f"{markdown.relative_to(ROOT)} has broken link: {target}"
                )


def validate_guardrails(errors: list[str]) -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for phrase in ("允许弃权", "不自动交易", "时间必须可追溯", "传统思想与计算引擎分层"):
        if phrase not in agents:
            errors.append(f"AGENTS.md missing guardrail: {phrase}")

    report = (ROOT / "docs/research/system-design.md").read_text(encoding="utf-8")
    if not report.startswith("# 《从易经“观变”到 AI 黄金趋势智能系统》"):
        errors.append("research report title is missing or changed")

    frame_template = (ROOT / "templates/market-cognition-frame.yaml").read_text(
        encoding="utf-8"
    )
    for field in (
        "as_of:",
        "data_cutoff:",
        "invalidation_conditions:",
        "abstention:",
        "research_posture:",
    ):
        if field not in frame_template:
            errors.append(f"market cognition frame template missing field: {field}")

    evaluation_contract = (ROOT / "evals/evaluation-contract-v0.2.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "xauusd-direction-5d:0.2.0",
        "第 3 个完整交易日只作为诊断检查点",
        "状态认知",
        "条件预测",
        "信念修正",
        "预测弃权时",
    ):
        if phrase not in evaluation_contract:
            errors.append(f"evaluation contract missing rule: {phrase}")

    if "allowed_actions" in frame_template:
        errors.append("market cognition frame template still uses allowed_actions")

    daily_prompt = (ROOT / "prompts/daily-cognition-run-v0.2.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "不要自行从公开网页补行情",
        "不得改用 TradingView",
        "三类概率为 `null`",
        "不得重新计算、改写或用文字估计",
        "validate-bundle",
    ):
        if phrase not in daily_prompt:
            errors.append(f"daily cognition prompt missing guardrail: {phrase}")

    source_policy = (
        ROOT / "docs/data/data-source-qualification-matrix-v0.1.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "OANDA REST v20 `XAU_USD`",
        "Rejected for AI runtime",
        "runtime/private/",
        "certified",
        "exploratory",
    ):
        if phrase not in source_policy:
            errors.append(f"source policy missing qualification rule: {phrase}")

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for ignored in ("runtime/private/", "runs/**/raw/", ".env"):
        if ignored not in gitignore:
            errors.append(f".gitignore does not protect: {ignored}")


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_pilot_evals(errors: list[str]) -> None:
    pilot_root = ROOT / "evals" / "pilots"
    evidence_paths = sorted((pilot_root / "evidence").glob("*.json"))
    frame_paths = sorted((pilot_root / "frames").glob("*.json"))

    if len(evidence_paths) != 5:
        errors.append(
            f"pilot evals require 5 evidence snapshots, found {len(evidence_paths)}"
        )
    if len(frame_paths) != 5:
        errors.append(f"pilot evals require 5 cognition frames, found {len(frame_paths)}")

    evidence_ids: set[str] = set()
    evidence_available_at: dict[str, datetime] = {}
    evidence_required = {
        "dependency_group",
        "source_timezone",
        "bar_timestamp_semantics",
        "availability_verified",
        "vintage_id",
        "licence",
    }

    for path in evidence_paths:
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid pilot evidence JSON {path.relative_to(ROOT)}: {exc}")
            continue
        if not isinstance(items, list) or not items:
            errors.append(f"{path.relative_to(ROOT)} must contain a non-empty array")
            continue

        for item in items:
            validate_instance(
                item,
                "evidence-item.schema.json",
                f"{path.relative_to(ROOT)}",
                errors,
            )
            evidence_id = item.get("evidence_id")
            if not evidence_id:
                errors.append(f"{path.relative_to(ROOT)} has evidence without evidence_id")
                continue
            if evidence_id in evidence_ids:
                errors.append(f"duplicate pilot evidence id: {evidence_id}")
            evidence_ids.add(evidence_id)
            missing_fields = evidence_required - set(item)
            if missing_fields:
                errors.append(
                    f"{evidence_id} missing v0.2 evidence fields: "
                    + ", ".join(sorted(missing_fields))
                )
            if item.get("availability_verified") is not False:
                errors.append(
                    f"{evidence_id} must remain availability_verified=false at Q0"
                )
            licence = item.get("licence", {})
            if licence.get("verified") is not False:
                errors.append(f"{evidence_id} must retain unverified Q0 licence")
            if not item.get("dependency_group"):
                errors.append(f"{evidence_id} has empty dependency_group")
            notes = item.get("quality", {}).get("notes", [])
            if any(
                str(note).startswith(
                    (
                        "dependency_group=",
                        "availability_verified=",
                        "source_timezone=",
                        "bar_timestamp_semantics=",
                        "vintage_id=",
                    )
                )
                for note in notes
            ):
                errors.append(
                    f"{evidence_id} keeps structured v0.2 fields in quality.notes"
                )
            try:
                evidence_available_at[evidence_id] = parse_datetime(item["available_at"])
            except (KeyError, TypeError, ValueError):
                errors.append(f"{evidence_id} has invalid available_at")

    directions: set[str] = set()
    lifecycles: set[str] = set()
    state_abstain_count = 0
    forecast_abstain_count = 0

    for path in frame_paths:
        try:
            frame = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid pilot frame JSON {path.relative_to(ROOT)}: {exc}")
            continue
        validate_instance(
            frame,
            "market-cognition-frame.schema.json",
            str(path.relative_to(ROOT)),
            errors,
        )

        try:
            cutoff = parse_datetime(frame["data_cutoff"])
            posterior = frame["state"]["posterior"]
            scenarios = frame["scenarios"]
        except (KeyError, TypeError, ValueError):
            errors.append(f"{path.relative_to(ROOT)} is missing core frame fields")
            continue

        posterior_sum = sum(posterior.values())
        abstention = frame.get("abstention", {})
        state_abstention = abstention.get("state", {})
        forecast_abstention = abstention.get("forecast", {})
        state_abstain = state_abstention.get("abstain")
        forecast_abstain = forecast_abstention.get("abstain")
        probabilities = [item.get("probability") for item in scenarios]
        if abs(posterior_sum - 1.0) > 1e-9:
            errors.append(
                f"{path.relative_to(ROOT)} state posterior sums to {posterior_sum}, not 1"
            )
        if set(posterior) != {"up", "down", "range"}:
            errors.append(
                f"{path.relative_to(ROOT)} posterior must contain only up/down/range"
            )

        outcome_ids = [item.get("resolution_outcome_id") for item in scenarios]
        if set(outcome_ids) != {"up", "down", "range"} or len(outcome_ids) != 3:
            errors.append(
                f"{path.relative_to(ROOT)} scenarios must map once to up/down/range"
            )

        if forecast_abstain is True:
            forecast_abstain_count += 1
            if any(value is not None for value in probabilities):
                errors.append(
                    f"{path.relative_to(ROOT)} forecast abstention must use null probabilities"
                )
            if not forecast_abstention.get("reason"):
                errors.append(
                    f"{path.relative_to(ROOT)} forecast abstains without a reason"
                )
        elif forecast_abstain is False:
            if any(not isinstance(value, (int, float)) for value in probabilities):
                errors.append(
                    f"{path.relative_to(ROOT)} non-abstained forecast needs probabilities"
                )
            else:
                scenario_sum = sum(probabilities)
                if abs(scenario_sum - 1.0) > 1e-9:
                    errors.append(
                        f"{path.relative_to(ROOT)} scenario probabilities sum to "
                        f"{scenario_sum}, not 1"
                    )
            if forecast_abstention.get("reason") is not None:
                errors.append(
                    f"{path.relative_to(ROOT)} non-abstained forecast has a reason"
                )
        else:
            errors.append(
                f"{path.relative_to(ROOT)} missing forecast abstention decision"
            )

        if state_abstain is True:
            state_abstain_count += 1
            if not state_abstention.get("reason"):
                errors.append(
                    f"{path.relative_to(ROOT)} state abstains without a reason"
                )
        elif state_abstain is False:
            if state_abstention.get("reason") is not None:
                errors.append(
                    f"{path.relative_to(ROOT)} non-abstained state has a reason"
                )
        else:
            errors.append(f"{path.relative_to(ROOT)} missing state abstention decision")

        refs = set(frame.get("evidence_refs", [])) | set(
            frame.get("counterevidence_refs", [])
        )
        missing_refs = refs - evidence_ids
        if missing_refs:
            errors.append(
                f"{path.relative_to(ROOT)} has unknown evidence refs: "
                + ", ".join(sorted(missing_refs))
            )
        for ref in refs:
            available_at = evidence_available_at.get(ref)
            if available_at and available_at > cutoff:
                errors.append(
                    f"{path.relative_to(ROOT)} uses future evidence {ref}: "
                    f"{available_at.isoformat()} > {cutoff.isoformat()}"
                )

        if forecast_abstain:
            if frame.get("risk", {}).get("level") != "blocked":
                errors.append(
                    f"{path.relative_to(ROOT)} forecast abstention must use blocked risk"
                )
            if frame.get("risk", {}).get("research_posture") != "do_not_publish":
                errors.append(
                    f"{path.relative_to(ROOT)} forecast abstention must not be publishable"
                )

        if "allowed_actions" in frame.get("risk", {}):
            errors.append(f"{path.relative_to(ROOT)} still uses allowed_actions")
        if not frame.get("risk", {}).get("research_posture"):
            errors.append(f"{path.relative_to(ROOT)} missing research_posture")

        if frame.get("state", {}).get("direction") == "range":
            allowed_range_lifecycles = {"formation", "maturity", "transition"}
            if frame.get("state", {}).get("lifecycle") not in allowed_range_lifecycles:
                errors.append(
                    f"{path.relative_to(ROOT)} has illegal range lifecycle"
                )

        data_snapshot = frame.get("provenance", {}).get("data_snapshot")
        if not data_snapshot or not (ROOT / data_snapshot).is_file():
            errors.append(
                f"{path.relative_to(ROOT)} has invalid provenance data_snapshot"
            )
        provenance = frame.get("provenance", {})
        if provenance.get("certification_level") != "Q0":
            errors.append(
                f"{path.relative_to(ROOT)} pilot certification must remain Q0"
            )
        if provenance.get("contract_version") != "2.0.0-q0":
            errors.append(
                f"{path.relative_to(ROOT)} must use migrated 2.0.0-q0 contract"
            )
        if (
            provenance.get("resolution_protocol_version")
            != "xauusd-direction-5d:0.2.0"
        ):
            errors.append(
                f"{path.relative_to(ROOT)} has wrong resolution protocol version"
            )

        directions.add(frame.get("state", {}).get("direction", ""))
        lifecycles.add(frame.get("state", {}).get("lifecycle", ""))

    expected_directions = {"up", "down", "range", "uncertain"}
    if not expected_directions.issubset(directions):
        errors.append(
            "pilot frames do not cover directions: "
            + ", ".join(sorted(expected_directions - directions))
        )
    expected_lifecycles = {"expansion", "maturity", "exhaustion", "transition"}
    if not expected_lifecycles.issubset(lifecycles):
        errors.append(
            "pilot frames do not cover lifecycles: "
            + ", ".join(sorted(expected_lifecycles - lifecycles))
        )
    if state_abstain_count != 0:
        errors.append(
            f"pilot frames require 0 state abstentions, found {state_abstain_count}"
        )
    if forecast_abstain_count != 1:
        errors.append(
            "pilot frames require exactly 1 forecast abstention, "
            f"found {forecast_abstain_count}"
        )


def validate_blocked_run_example(errors: list[str]) -> None:
    path = ROOT / "examples/runs/blocked-no-qualified-evidence/run.json"
    try:
        run = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid blocked run example: {exc}")
        return

    validate_instance(
        run,
        "cognition-run.schema.json",
        str(path.relative_to(ROOT)),
        errors,
    )

    if run.get("contract_version") != "0.2.0":
        errors.append("blocked run example has wrong contract version")
    if run.get("mode") != "exploratory":
        errors.append("blocked run without qualified evidence must be exploratory")
    if run.get("instrument") != "XAUUSD":
        errors.append("blocked run example must use XAUUSD")
    if run.get("status") != "blocked":
        errors.append("run without qualified evidence must be blocked")

    try:
        as_of = parse_datetime(run["as_of"])
        cutoff = parse_datetime(run["data_cutoff"])
        if cutoff > as_of:
            errors.append("blocked run data_cutoff is after as_of")
    except (KeyError, TypeError, ValueError):
        errors.append("blocked run example has invalid as_of/data_cutoff")

    run_input = run.get("input", {})
    if run_input.get("private_raw_data") is not False:
        errors.append("blocked example must not claim private raw data")
    if run_input.get("daily_complete_bars", 0) >= 60:
        errors.append("blocked example unexpectedly passes daily history gate")
    if run_input.get("h4_complete_bars", 0) >= 30:
        errors.append("blocked example unexpectedly passes h4 history gate")
    if run_input.get("baseline") is not None:
        errors.append("blocked example unexpectedly contains a frozen baseline")

    expected_reasons = {
        "missing_evidence_manifest",
        "instrument_not_available",
        "missing_daily_history",
        "missing_h4_history",
        "missing_macro_rates",
        "missing_macro_usd",
        "missing_event_clock",
        "unverified_temporal_integrity",
        "unknown_bar_semantics",
        "missing_snapshot_hash",
        "missing_feature_snapshot",
        "missing_baseline",
    }
    reasons = set(run.get("blocking_reasons", []))
    missing_reasons = expected_reasons - reasons
    if missing_reasons:
        errors.append(
            "blocked run example omits reasons: "
            + ", ".join(sorted(missing_reasons))
        )

    outputs = run.get("outputs", {})
    if any(
        outputs.get(key) is not None
        for key in ("evidence_items", "frame", "forecast", "delta", "resolution")
    ):
        errors.append("blocked run must not emit frame or forecast files")

    gates = run.get("gates", {})
    if all(value == "pass" for value in gates.values()):
        errors.append("blocked run cannot pass every data gate")

    provenance = run.get("provenance", {})
    if provenance.get("prompt_version") != "daily-cognition-run:0.2.0":
        errors.append("blocked run has wrong prompt version")
    if provenance.get("source_policy_version") != "data-source-qualification:0.1.0":
        errors.append("blocked run has wrong source policy version")
    if provenance.get("runtime_version") != "dao-certified-runtime:0.2.0":
        errors.append("blocked run has wrong runtime version")


def main() -> int:
    errors: list[str] = []
    validate_required_paths(errors)
    validate_schemas(errors)
    validate_internal_links(errors)
    validate_guardrails(errors)
    validate_pilot_evals(errors)
    validate_blocked_run_example(errors)

    if errors:
        print("Harness validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "Harness validation passed: "
        f"{len(REQUIRED_PATHS)} required files, "
        f"{len(SCHEMA_REQUIREMENTS)} schemas, internal links, and guardrails."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
