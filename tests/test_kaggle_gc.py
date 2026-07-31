"""Tests for the Kaggle-only GC preparation pipeline."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dao_runtime.bundle import validate_bundle
from dao_runtime.cli import build_parser
from dao_runtime.contracts import format_datetime, sha256_file, write_json
from dao_runtime.forecast import generate_baseline_forecast
from dao_runtime.kaggle_gc import (
    DEFAULT_DATASET_REF,
    REQUIRED_DAILY_BARS,
    normalize_kaggle_gc_csv,
    prepare_gc_bundle,
)
from tests.test_bundle import build_valid_bundle


FAKE_METADATA = {"title": "COMEX Gold Futures", "licenses": [{"name": "other"}]}
FAKE_TOKEN = "kaggle-secret-token-1234567890"


def synthetic_csv(
    *,
    rows: int = REQUIRED_DAILY_BARS + 7,
    end_days_ago: int = 1,
    header: str = "Date,Open,High,Low,Close,Volume",
    extra_lines: list[str] | None = None,
) -> str:
    end = datetime.now(timezone.utc).date() - timedelta(days=end_days_ago)
    lines = [header]
    for offset in range(rows - 1, -1, -1):
        day = end - timedelta(days=offset)
        base = 2000 + (rows - offset) * 0.25
        lines.append(
            f"{day.isoformat()},{base:.2f},{base + 2:.2f},{base - 2:.2f},{base:.2f},1200"
        )
    lines.extend(extra_lines or [])
    return "\n".join(lines) + "\n"


def make_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def fake_kaggle_run(zip_bytes: bytes):
    def run(command, **kwargs):
        assert kwargs.get("shell") is not True
        if "--version" in command:
            return SimpleNamespace(returncode=0, stdout="Kaggle CLI 2.2.1", stderr="")
        target = Path(command[command.index("-p") + 1])
        target.mkdir(parents=True, exist_ok=True)
        if "metadata" in command:
            (target / "dataset-metadata.json").write_text(
                json.dumps(FAKE_METADATA), encoding="utf-8"
            )
        elif "download" in command:
            (target / "gc-dataset.zip").write_bytes(zip_bytes)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return run


def write_official_files(root: Path) -> list[dict]:
    captured = format_datetime(datetime.now(timezone.utc))
    items = []
    for role, semantics in (
        ("macro_rates", "publication_time"),
        ("macro_usd", "publication_time"),
        ("event_clock", "event_time"),
    ):
        path = root / f"{role}.json"
        write_json(path, {"role": role, "value": 1})
        items.append(
            {
                "role": role,
                "path": str(path),
                "source_locator": f"https://official.gov/{role}",
                "captured_at": captured,
                "available_at": captured,
                "observed_at": captured,
                "source_timezone": "UTC",
                "timestamp_semantics": semantics,
                "record_count": 1,
                "freshness_max_seconds": 345600,
            }
        )
    return items


def write_config(root: Path, **overrides) -> Path:
    config = {
        "run_id": "run-20260731-gc",
        "mode": "automated",
        "dataset_ref": DEFAULT_DATASET_REF,
        "dataset_file": None,
        "freshness_max_days": 10,
        "column_mapping": None,
        "previous_frame": None,
        "official_snapshots": write_official_files(root / "official"),
    }
    config.update(overrides)
    path = root / "gc-config.json"
    write_json(path, config)
    return path


def run_prepare(
    root: Path,
    *,
    csv_text: str | None = None,
    zip_files: dict[str, str] | None = None,
    config_overrides: dict | None = None,
) -> tuple[Path, Path, dict[str, Path]]:
    files = zip_files if zip_files is not None else {"gc_daily.csv": csv_text}
    config_path = write_config(root, **(config_overrides or {}))
    public_dir = root / "public"
    private_dir = root / "private"
    with (
        patch("dao_runtime.kaggle_gc.shutil.which", return_value="/usr/bin/kaggle"),
        patch(
            "dao_runtime.kaggle_gc.subprocess.run",
            side_effect=fake_kaggle_run(make_zip(files)),
        ),
    ):
        paths = prepare_gc_bundle(config_path, public_dir, private_dir)
    return public_dir, private_dir, paths


def normalize_text(csv_text: str, **kwargs) -> dict:
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "data.csv"
        path.write_text(csv_text, encoding="utf-8")
        return normalize_kaggle_gc_csv(
            path, dataset_ref=DEFAULT_DATASET_REF, **kwargs
        )


class KaggleCliIntegrationTests(unittest.TestCase):
    def test_prepare_gc_uses_kaggle_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_path = write_config(root)
            calls: list[list[str]] = []
            fake = fake_kaggle_run(make_zip({"gc.csv": synthetic_csv()}))

            def recording(command, **kwargs):
                calls.append(list(command))
                return fake(command, **kwargs)

            with (
                patch(
                    "dao_runtime.kaggle_gc.shutil.which",
                    return_value="/usr/bin/kaggle",
                ),
                patch("dao_runtime.kaggle_gc.subprocess.run", side_effect=recording),
            ):
                prepare_gc_bundle(config_path, root / "public", root / "private")

            download_calls = [call for call in calls if "download" in call]
            self.assertEqual(len(download_calls), 1)
            self.assertIn(DEFAULT_DATASET_REF, download_calls[0])
            self.assertTrue(all(call[0] == "/usr/bin/kaggle" for call in calls))

    def test_only_one_gc_prepare_command_exists(self) -> None:
        commands = set(build_parser()._subparsers._group_actions[0].choices)
        gc_commands = {name for name in commands if "gc" in name}
        self.assertEqual(gc_commands, {"prepare-gc"})
        for forbidden in ("prepare-kaggle-gc", "prepare-cme-gc", "prepare-gc-v2"):
            self.assertNotIn(forbidden, commands)

    def test_missing_kaggle_cli_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_path = write_config(root)
            with (
                patch("dao_runtime.kaggle_gc.shutil.which", return_value=None),
                self.assertRaisesRegex(RuntimeError, "kaggle CLI not found"),
            ):
                prepare_gc_bundle(config_path, root / "public", root / "private")

    def test_invalid_dataset_ref_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_path = write_config(
                root, dataset_ref="../not/a/kaggle/ref"
            )
            with (
                patch("dao_runtime.kaggle_gc.subprocess.run") as run_mock,
                self.assertRaisesRegex(ValueError, "dataset_ref"),
            ):
                prepare_gc_bundle(config_path, root / "public", root / "private")
            run_mock.assert_not_called()

    def test_kaggle_token_is_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict(
                "os.environ", {"KAGGLE_API_TOKEN": FAKE_TOKEN}, clear=False
            ):
                public_dir, private_dir, _ = run_prepare(
                    root, csv_text=synthetic_csv()
                )
            for path in [*public_dir.rglob("*"), *private_dir.rglob("*")]:
                if path.is_file():
                    self.assertNotIn(
                        FAKE_TOKEN.encode(), path.read_bytes(), path.name
                    )

    def test_archive_sha256_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            public_dir, private_dir, _ = run_prepare(
                Path(temp), csv_text=synthetic_csv()
            )
            manifest = json.loads(
                (public_dir / "evidence-manifest.json").read_text()
            )
            archive_hash = sha256_file(private_dir / "kaggle" / "original.zip")
            self.assertEqual(manifest["dataset"]["archive_sha256"], archive_hash)
            download_manifest = json.loads(
                (private_dir / "kaggle" / "download-manifest.json").read_text()
            )
            self.assertEqual(download_manifest["archive"]["sha256"], archive_hash)
            self.assertEqual(
                manifest["dataset"]["kaggle_cli_version"], "Kaggle CLI 2.2.1"
            )

    def test_metadata_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _, private_dir, _ = run_prepare(Path(temp), csv_text=synthetic_csv())
            metadata = json.loads(
                (private_dir / "kaggle" / "dataset-metadata.json").read_text()
            )
            self.assertEqual(metadata, FAKE_METADATA)

    def test_zip_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "escapes extraction directory"):
                run_prepare(
                    Path(temp),
                    zip_files={"../evil.csv": synthetic_csv()},
                )


class CsvAdapterTests(unittest.TestCase):
    def test_csv_columns_are_case_insensitive(self) -> None:
        text = synthetic_csv(header="DATE,OPEN,HIGH,LOW,CLOSE,VOL")
        duplicate_row = text.splitlines()[-1]
        canonical = normalize_text(text + duplicate_row + "\n")
        self.assertEqual(
            len(canonical["candles"]), REQUIRED_DAILY_BARS + 7
        )
        self.assertEqual(canonical["price_component"], "CLOSE")
        self.assertEqual(
            canonical["timestamp_semantics"], "dataset_observation_date"
        )

    def test_multiple_candidate_csv_files_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "uniquely identify"):
                run_prepare(
                    Path(temp),
                    zip_files={
                        "first.csv": synthetic_csv(),
                        "second.csv": synthetic_csv(),
                    },
                )

    def test_duplicate_dates_are_rejected(self) -> None:
        base = synthetic_csv()
        last = base.splitlines()[-1].split(",")
        last[-1] = "999"
        with self.assertRaisesRegex(ValueError, "conflicting rows"):
            normalize_text(base + ",".join(last) + "\n")

    def test_conflicting_duplicate_dates_are_rejected(self) -> None:
        base = synthetic_csv()
        last = base.splitlines()[-1].split(",")
        last[4] = last[2]
        with self.assertRaisesRegex(ValueError, "conflicting rows"):
            normalize_text(base + ",".join(last) + "\n")

    def test_invalid_ohlc_bounds_are_rejected(self) -> None:
        bad = "2026-07-30,2000.00,1990.00,2010.00,2000.00,10"
        with self.assertRaisesRegex(ValueError, "invalid OHLC bounds"):
            normalize_text(synthetic_csv(extra_lines=[bad]))

    def test_negative_volume_is_rejected(self) -> None:
        bad = "2026-07-30,2000.00,2002.00,1998.00,2000.00,-5"
        with self.assertRaisesRegex(ValueError, "non-negative"):
            normalize_text(synthetic_csv(extra_lines=[bad]))

    def test_unparseable_price_is_rejected(self) -> None:
        bad = "2026-07-30,,2002.00,1998.00,2000.00,5"
        with self.assertRaisesRegex(ValueError, "decimal price"):
            normalize_text(synthetic_csv(extra_lines=[bad]))

    def test_short_history_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "daily observations"):
            normalize_text(synthetic_csv(rows=40))


class GcBundleSemanticsTests(unittest.TestCase):
    def test_stale_dataset_blocks_forecast(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            public_dir, private_dir, paths = run_prepare(
                Path(temp), csv_text=synthetic_csv(end_days_ago=30)
            )
            run = json.loads((public_dir / "run.json").read_text())
            self.assertEqual(run["status"], "blocked")
            self.assertEqual(run["blocking_reasons"], ["stale_dataset"])
            self.assertIsNone(run["outputs"]["forecast"])
            self.assertEqual(list(paths), ["run"])
            self.assertEqual(
                validate_bundle(
                    public_dir, private_root=private_dir, raise_on_error=False
                ),
                [],
            )
            with self.assertRaisesRegex(ValueError, "ready run"):
                generate_baseline_forecast(public_dir)

    def test_gc_feature_uses_close_not_settlement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            public_dir, _, _ = run_prepare(Path(temp), csv_text=synthetic_csv())
            feature_text = (public_dir / "feature-snapshot.json").read_text()
            feature = json.loads(feature_text)
            self.assertEqual(feature["reference_price_field"], "close")
            self.assertEqual(feature["bar_config"]["price_component"], "CLOSE")
            self.assertNotIn("settlement", feature_text.lower())

    def test_gc_does_not_require_h4(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            public_dir, private_dir, _ = run_prepare(
                Path(temp), csv_text=synthetic_csv()
            )
            run = json.loads((public_dir / "run.json").read_text())
            manifest = json.loads(
                (public_dir / "evidence-manifest.json").read_text()
            )
            self.assertIsNone(run["input"]["h4_complete_bars"])
            self.assertIsNone(manifest["coverage"]["h4_complete_bars"])
            self.assertEqual(
                validate_bundle(
                    public_dir, private_root=private_dir, raise_on_error=False
                ),
                [],
            )

    def test_gc_does_not_require_contract_month(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            public_dir, _, _ = run_prepare(Path(temp), csv_text=synthetic_csv())
            manifest = json.loads(
                (public_dir / "evidence-manifest.json").read_text()
            )
            self.assertNotIn("futures_contract", manifest)
            self.assertEqual(manifest["instrument"], "GC")
            for name in ("run.json", "evidence-manifest.json"):
                self.assertNotIn(
                    "contract_month", (public_dir / name).read_text()
                )

    def test_gc_does_not_require_contract_calendar(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            public_dir, _, _ = run_prepare(Path(temp), csv_text=synthetic_csv())
            manifest = json.loads(
                (public_dir / "evidence-manifest.json").read_text()
            )
            roles = {item["role"] for item in manifest["snapshots"]}
            self.assertEqual(
                roles,
                {"price_daily", "macro_rates", "macro_usd", "event_clock"},
            )

    def test_old_cme_provider_is_not_supported(self) -> None:
        with self.assertRaises(ModuleNotFoundError):
            import dao_runtime.futures  # noqa: F401
        with tempfile.TemporaryDirectory() as temp:
            public_dir, private_dir, _ = run_prepare(
                Path(temp), csv_text=synthetic_csv()
            )
            manifest_path = public_dir / "evidence-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["provider"]["provider_id"] = "cme-licensed-snapshot"
            write_json(manifest_path, manifest)
            errors = validate_bundle(
                public_dir, private_root=private_dir, raise_on_error=False
            )
            self.assertTrue(errors)

    def test_certified_mode_is_rejected_for_gc(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "mode=automated"):
                run_prepare(
                    Path(temp),
                    csv_text=synthetic_csv(),
                    config_overrides={"mode": "certified"},
                )

    def test_xauusd_oanda_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, private_root = build_valid_bundle(Path(temp))
            self.assertEqual(
                validate_bundle(
                    run_dir, private_root=private_root, raise_on_error=False
                ),
                [],
            )

    def test_ready_gc_bundle_passes_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            public_dir, private_dir, paths = run_prepare(
                Path(temp), csv_text=synthetic_csv()
            )
            self.assertEqual(
                sorted(paths), ["baseline", "feature", "manifest", "run"]
            )
            self.assertEqual(
                validate_bundle(
                    public_dir, private_root=private_dir, raise_on_error=False
                ),
                [],
            )
            forecast_path = generate_baseline_forecast(public_dir)
            forecast = json.loads(forecast_path.read_text())
            self.assertEqual(forecast["instrument"], "GC")
            self.assertEqual(
                forecast["resolution_rule"]["protocol_id"],
                "gc-kaggle-daily-direction-5d:0.1.0",
            )
            self.assertEqual(
                forecast["resolution_rule"]["frozen_values"]["dataset_ref"],
                DEFAULT_DATASET_REF,
            )
            self.assertFalse(forecast["forecast_abstention"]["abstain"])
            run_path = public_dir / "run.json"
            run = json.loads(run_path.read_text())
            run["outputs"]["forecast"] = "forecast-contract.json"
            write_json(run_path, run)
            self.assertEqual(
                validate_bundle(
                    public_dir, private_root=private_dir, raise_on_error=False
                ),
                [],
            )

    def test_downloaded_raw_data_is_not_written_to_public_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            public_dir, _, _ = run_prepare(Path(temp), csv_text=synthetic_csv())
            names = sorted(path.name for path in public_dir.rglob("*"))
            self.assertEqual(
                names,
                [
                    "baseline-snapshot.json",
                    "evidence-manifest.json",
                    "feature-snapshot.json",
                    "run.json",
                ],
            )
            for path in public_dir.rglob("*"):
                self.assertNotIn(path.suffix, {".zip", ".csv"})


if __name__ == "__main__":
    unittest.main()
