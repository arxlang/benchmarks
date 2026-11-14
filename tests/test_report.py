import contextlib
import io
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import bench, make_run


class ReportTests(unittest.TestCase):
    def test_report_parses_hyperfine_1(self):
        """Prevents hyperfine 1.x reports from losing timing and baseline data."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = make_run(
                root,
                "1.x",
                [
                    {"command": "python", "median": 2.5, "min": 2.0, "stddev": 0.2,
                     "memory_usage_byte": 1048576},
                    {"command": "c-O2", "median": 1.25, "min": 1.2, "stddev": 0.05,
                     "memory_usage_byte": 2097152},
                ],
                [
                    {"command": "python", "median": 1.0, "min": 0.9, "stddev": 0.1,
                     "memory_usage_byte": 524288},
                    {"command": "c-O2", "median": 0.25, "min": 0.2, "stddev": 0.05,
                     "memory_usage_byte": 262144},
                ],
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                bench.cmd_report(Namespace(dir=str(run)))
            text = output.getvalue()
            self.assertIn("median (s)", text)
            self.assertIn("startup (s)", text)
            self.assertIn("net (s)", text)
            self.assertIn("2.5000", text)
            self.assertIn("1.0000", text)
            self.assertIn("1.5000", text)
            self.assertIn("memory (MiB)", text)
            self.assertIn("1.0", text)
            self.assertIn("2.0", text)
            self.assertIn("1.0x", text)
            self.assertIn("2.0x", text)

    def test_report_parses_hyperfine_2_with_memory(self):
        """Prevents hyperfine 2.x memory values from being reported in bytes."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = make_run(
                root,
                "2.x-memory",
                [{"command": "python", "name": "python", "median": 0.8, "min": 0.7,
                  "stddev": 0.1, "memory": 2097152}],
                [{"command": "python", "name": "python", "median": 0.5, "min": 0.4,
                  "stddev": 0.1, "memory": 1048576}],
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                bench.cmd_report(Namespace(dir=str(run)))
            text = output.getvalue()
            self.assertIn("memory (MiB)", text)
            self.assertIn("2.0", text)
            self.assertIn("1.0", text)

    def test_report_parses_hyperfine_2_without_memory(self):
        """Prevents hyperfine 2.x reports without memory data from failing."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = make_run(
                root,
                "2.x",
                [{"command": "python", "name": "python", "median": 0.8, "min": 0.7,
                  "stddev": 0.1}],
                [{"command": "python", "name": "python", "median": 1.0, "min": 0.9,
                  "stddev": 0.1}],
                memory=False,
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                bench.cmd_report(Namespace(dir=str(run)))
            text = output.getvalue()
            self.assertIn("0.8000", text)
            self.assertIn("1.0000", text)
            self.assertIn("0.0000", text)
            self.assertIn("1.0x", text)
            self.assertNotIn("memory (MiB)", text)

    def test_report_without_baseline_omits_startup_columns(self):
        """Prevents reports without a baseline from inventing startup timings."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = make_run(
                root,
                "2.x-no-baseline",
                [{"command": "python", "name": "python", "median": 0.8, "min": 0.7,
                  "stddev": 0.1}],
                [{"command": "python", "name": "python", "median": 0.2, "min": 0.1,
                  "stddev": 0.1}],
            )
            (run / "_baseline.json").unlink()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                bench.cmd_report(Namespace(dir=str(run)))
            text = output.getvalue()
            self.assertNotIn("startup (s)", text)
            self.assertNotIn("net (s)", text)
            self.assertIn("0.8000", text)
