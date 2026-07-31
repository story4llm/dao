"""Command line interface for private preparation and bundle validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .bundle import validate_bundle
from .contracts import ContractError
from .futures import prepare_gc_bundle
from .forecast import generate_baseline_forecast
from .oanda import prepare_private_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dao-runtime")
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser(
        "prepare-oanda",
        help="prepare a private OANDA bundle and a public ready-run skeleton",
    )
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--public-dir", type=Path, required=True)
    prepare.add_argument("--private-dir", type=Path, required=True)

    prepare_gc = commands.add_parser(
        "prepare-gc",
        help="prepare a private single-contract COMEX GC bundle",
    )
    prepare_gc.add_argument("--config", type=Path, required=True)
    prepare_gc.add_argument("--public-dir", type=Path, required=True)
    prepare_gc.add_argument("--private-dir", type=Path, required=True)

    validate = commands.add_parser(
        "validate-bundle",
        help="validate schemas, cross-file semantics and private hashes",
    )
    validate.add_argument("--run-dir", type=Path, required=True)
    validate.add_argument("--private-root", type=Path)
    forecast = commands.add_parser(
        "generate-baseline-forecast",
        help="emit a deterministic five-session Forecast Contract from a ready run",
    )
    forecast.add_argument("--run-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"prepare-oanda", "prepare-gc"}:
            prepare_bundle = (
                prepare_private_bundle
                if args.command == "prepare-oanda"
                else prepare_gc_bundle
            )
            paths = prepare_bundle(
                args.config.resolve(),
                args.public_dir.resolve(),
                args.private_dir.resolve(),
            )
            validate_bundle(
                args.public_dir.resolve(),
                private_root=args.private_dir.resolve(),
            )
            for name, path in paths.items():
                print(f"{name}: {path}")
            print("private bundle prepared and validated")
        elif args.command == "validate-bundle":
            validate_bundle(
                args.run_dir.resolve(),
                private_root=args.private_root.resolve() if args.private_root else None,
            )
            print("bundle validation passed")
        elif args.command == "generate-baseline-forecast":
            path = generate_baseline_forecast(args.run_dir.resolve())
            print(f"forecast: {path}")
        return 0
    except (
        ContractError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"DAO runtime failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
