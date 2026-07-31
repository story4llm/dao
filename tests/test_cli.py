from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from dao_runtime.cli import main


class CliTests(unittest.TestCase):
    def test_prepare_reports_malformed_upstream_shapes_without_traceback(self) -> None:
        argv = [
            "prepare-oanda",
            "--config",
            "config.json",
            "--public-dir",
            "public",
            "--private-dir",
            "private",
        ]
        for exception in (KeyError("time"), TypeError("mid must be an object")):
            with self.subTest(exception=type(exception).__name__):
                stderr = io.StringIO()
                with (
                    patch(
                        "dao_runtime.cli.prepare_private_bundle",
                        side_effect=exception,
                    ),
                    redirect_stderr(stderr),
                ):
                    result = main(argv)
                self.assertEqual(result, 1)
                self.assertIn("DAO runtime failed:", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
