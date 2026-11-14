import os
import platform
import shutil
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import bench, make_fake_suite


HYPERFINE_AVAILABLE = shutil.which("hyperfine") is not None
HYPERFINE_REQUIRED = os.environ.get("REQUIRE_HYPERFINE") == "1"
requires_hyperfine = unittest.skipUnless(
    HYPERFINE_AVAILABLE or HYPERFINE_REQUIRED,
    "hyperfine not installed",
)


def arguments():
    return Namespace(suites=["fake"], case=None, lang="python", quick=True)


class FakeSuiteTests(unittest.TestCase):
    def setUp(self):
        bench._built.clear()

    @requires_hyperfine
    def test_good_run_is_completed_and_renamed(self):
        """Prevents successful runs from being left partial or unmarked."""
        if shutil.which("hyperfine") is None:
            self.fail("hyperfine is required when REQUIRE_HYPERFINE=1")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            suites = root / "suites"
            build = root / "build"
            results = root / "results"
            make_fake_suite(suites)
            with patch.object(bench, "SUITES", suites), \
                    patch.object(bench, "BUILD", build), \
                    patch.object(bench, "RESULTS", results):
                bench.cmd_check(arguments())
                bench.cmd_run(arguments())
            result_root = build / "quick-results"
            finished = [path for path in result_root.iterdir() if not path.name.startswith(".")]
            partial = [path for path in result_root.iterdir() if path.name.startswith(".")]
            self.assertEqual(len(finished), 1)
            self.assertTrue((finished[0] / "complete.json").is_file())
            self.assertEqual(partial, [])

    @requires_hyperfine
    def test_wrong_expected_leaves_only_partial_run(self):
        """Prevents failed verification from being reported as a finished run."""
        if shutil.which("hyperfine") is None:
            self.fail("hyperfine is required when REQUIRE_HYPERFINE=1")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            suites = root / "suites"
            build = root / "build"
            results = root / "results"
            make_fake_suite(suites, expected="wrong")
            args = arguments()
            with patch.object(bench, "SUITES", suites), \
                    patch.object(bench, "BUILD", build), \
                    patch.object(bench, "RESULTS", results):
                with self.assertRaises(SystemExit):
                    bench.cmd_run(args)
                result_root = build / "quick-results"
                partial = [path for path in result_root.iterdir() if path.name.startswith(".")]
                finished = [path for path in result_root.iterdir() if not path.name.startswith(".")]
                self.assertEqual(len(partial), 1)
                self.assertEqual(finished, [])
                with self.assertRaises(SystemExit):
                    bench.cmd_report(Namespace(dir=str(partial[0])))

    def test_existing_result_is_not_modified(self):
        """Prevents a repeated timestamp from overwriting an existing result."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            suites = root / "suites"
            build = root / "build"
            results = root / "results"
            make_fake_suite(suites)
            fixed_environment = {
                "timestamp_utc": "2026-11-14T010203Z",
                "arx": "test-arx",
            }
            name = (
                f"{fixed_environment['timestamp_utc']}_{platform.system().lower()}-"
                f"{platform.machine()}_arx-{fixed_environment['arx']}"
            )
            result_root = build / "quick-results"
            existing = result_root / name
            existing.mkdir(parents=True)
            sentinel = existing / "sentinel"
            sentinel.write_text("keep")
            with patch.object(bench, "SUITES", suites), \
                    patch.object(bench, "BUILD", build), \
                    patch.object(bench, "RESULTS", results), \
                    patch.object(bench, "environment", return_value=fixed_environment), \
                    patch.object(bench, "require"):
                with self.assertRaises(SystemExit):
                    bench.cmd_run(arguments())
            self.assertEqual(sentinel.read_text(), "keep")
            self.assertEqual(sorted(path.name for path in result_root.iterdir()), [name])
