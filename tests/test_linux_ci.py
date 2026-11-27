import io
import os
import unittest
from contextlib import redirect_stderr
from unittest.mock import mock_open, patch

from support import bench


class LinuxCiTests(unittest.TestCase):
    def test_cpu_name_reads_linux_proc_cpuinfo(self):
        """Prevents Linux CPU models from falling back to an empty processor name."""
        cpuinfo = (
            "processor : 0\n"
            "model name : AMD EPYC 7763 64-Core Processor\n"
        )
        with patch.object(bench.sys, "platform", "linux"), \
                patch("builtins.open", mock_open(read_data=cpuinfo)):
            self.assertEqual(bench.cpu_name(), "AMD EPYC 7763 64-Core Processor")

    def test_conda_clang_warning_is_macos_only(self):
        """Prevents macOS-only conda clang warnings on Linux."""
        conda_clang = "/opt/conda/bin/clang"
        with patch.object(bench.sys, "platform", "linux"), \
                patch.object(bench.shutil, "which", return_value=conda_clang):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                bench.select_langs("c")
            self.assertNotIn("WARNING:", stderr.getvalue())

        with patch.object(bench.sys, "platform", "darwin"), \
                patch.object(bench.shutil, "which", return_value=conda_clang):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                bench.select_langs("c")
            self.assertIn("WARNING:", stderr.getvalue())

    def test_numba_python_falls_back_on_linux(self):
        """Prevents Numba benchmarks from assuming a macOS-specific conda path."""
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(bench.sys, "executable", "/usr/bin/python3"), \
                patch.object(bench.shutil, "which", return_value="/usr/bin/python3"):
            self.assertEqual(bench.resolve_numba_python(), "/usr/bin/python3")

    def test_numba_python_falls_back_to_python3(self):
        """Prevents Numba benchmarks from depending on sys.executable when it is empty."""
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(bench.sys, "executable", ""), \
                patch.object(bench.shutil, "which", return_value="/usr/local/bin/python3"):
            self.assertEqual(bench.resolve_numba_python(), "/usr/local/bin/python3")

    def test_numba_python_respects_explicit_environment(self):
        """Prevents an explicit NUMBA_PYTHON override from being ignored."""
        with patch.dict(os.environ, {"NUMBA_PYTHON": "/opt/numba/bin/python"}, clear=True):
            self.assertEqual(bench.resolve_numba_python(), "/opt/numba/bin/python")

    def test_bench_arx_install_is_recorded_when_set(self):
        """Prevents CI Arx installation provenance from being omitted."""
        with patch.dict(os.environ, {"BENCH_ARX_INSTALL": "arxpm"}, clear=True), \
                patch.object(bench, "sh", return_value=""), \
                patch.object(bench, "cpu_name", return_value="test CPU"), \
                patch.object(bench.platform, "platform", return_value="Linux-test"), \
                patch.object(bench.platform, "machine", return_value="x86_64"), \
                patch.object(bench.platform, "python_version", return_value="3.11.0"), \
                patch.object(bench.shutil, "which", return_value="/usr/bin/test"):
            env = bench.environment({"python": bench.LANGS["python"]})
        self.assertEqual(env["arx_install"], "arxpm")
        self.assertEqual(env["os"], "Linux-test")

    def test_bench_arx_install_is_omitted_when_empty(self):
        """Prevents an empty CI installation override from appearing in results."""
        with patch.dict(os.environ, {"BENCH_ARX_INSTALL": ""}, clear=True), \
                patch.object(bench, "sh", return_value=""), \
                patch.object(bench, "cpu_name", return_value="test CPU"), \
                patch.object(bench.platform, "platform", return_value="Linux-test"), \
                patch.object(bench.platform, "machine", return_value="x86_64"), \
                patch.object(bench.platform, "python_version", return_value="3.11.0"), \
                patch.object(bench.shutil, "which", return_value=None):
            env = bench.environment({"python": bench.LANGS["python"]})
        self.assertNotIn("arx_install", env)

    def test_ci_run_counts(self):
        """Prevents CI overrides and quick mode from resolving the wrong run counts."""
        normal = {"runs": 30, "warmup": 5}
        overridden = {"runs": 30, "warmup": 5, "ci": {"runs": 3, "warmup": 9}}
        partial = {"runs": 30, "warmup": 5, "ci": {"warmup": 0}}

        self.assertEqual(bench.resolve_run_counts(normal, ci=True), (30, 5))
        self.assertEqual(bench.resolve_run_counts(overridden, ci=True), (3, 9))
        self.assertEqual(bench.resolve_run_counts(partial, ci=True), (30, 0))
        self.assertEqual(bench.resolve_run_counts(normal, ci=False), (30, 5))
        self.assertEqual(bench.resolve_run_counts(overridden, ci=True, quick=True), (3, 1))


if __name__ == "__main__":
    unittest.main()
