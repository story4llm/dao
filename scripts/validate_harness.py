#!/usr/bin/env python3
"""Validate the repository harness without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "harness.yaml",
    "docs/research/system-design.md",
    "docs/product/vision.md",
    "docs/architecture/domain-ontology.md",
    "docs/architecture/agent-protocol.md",
    "docs/harness/CONTEXT_MAP.md",
    "docs/harness/WORKFLOW.md",
    "docs/harness/QUALITY_GATES.md",
    "docs/harness/RESEARCH_POLICY.md",
    "state/PROJECT_STATE.md",
    "state/DECISION_LOG.md",
    "state/OPEN_QUESTIONS.md",
    "tasks/TEMPLATE.md",
    "evals/README.md",
    "schemas/evidence-item.schema.json",
    "schemas/forecast-contract.schema.json",
    "schemas/market-cognition-frame.schema.json",
    "templates/research-note.md",
    "templates/forecast-record.yaml",
    "templates/market-cognition-frame.yaml",
]

SCHEMA_REQUIREMENTS = {
    "evidence-item.schema.json": {"evidence_id", "available_at", "quality"},
    "forecast-contract.schema.json": {
        "forecast_id",
        "data_cutoff",
        "outcomes",
        "resolution_rule",
        "invalidation_conditions",
    },
    "market-cognition-frame.schema.json": {
        "frame_id",
        "as_of",
        "data_cutoff",
        "scenarios",
        "invalidation_conditions",
        "risk",
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

        expected = SCHEMA_REQUIREMENTS.get(path.name, set())
        required = set(payload.get("required", []))
        missing = expected - required
        if missing:
            errors.append(
                f"{path.relative_to(ROOT)} missing required contract fields: "
                + ", ".join(sorted(missing))
            )


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
    for field in ("as_of:", "data_cutoff:", "invalidation_conditions:", "abstain:"):
        if field not in frame_template:
            errors.append(f"market cognition frame template missing field: {field}")


def main() -> int:
    errors: list[str] = []
    validate_required_paths(errors)
    validate_schemas(errors)
    validate_internal_links(errors)
    validate_guardrails(errors)

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

