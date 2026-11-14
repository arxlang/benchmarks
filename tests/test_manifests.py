import tomllib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import bench


ROOT = Path(__file__).resolve().parent.parent


class ManifestTests(unittest.TestCase):
    def test_real_manifests_are_well_formed(self):
        """Prevents malformed manifests from reaching benchmark execution."""
        manifests = sorted(bench.SUITES.glob("*/benchmark.toml"))
        self.assertTrue(manifests)
        for manifest in manifests:
            with self.subTest(manifest=manifest):
                data = tomllib.loads(manifest.read_text())
                ids = []
                for case in data["case"]:
                    self.assertIn("id", case)
                    self.assertIn("args", case)
                    self.assertIn("expected", case)
                    self.assertIsInstance(case["expected"], str)
                    self.assertIsInstance(case["runs"], int)
                    self.assertGreaterEqual(case["runs"], 1)
                    self.assertIsInstance(case["warmup"], int)
                    self.assertGreaterEqual(case["warmup"], 1)
                    ids.append(case["id"])
                    for source in case.get("arx", {}).values():
                        self.assertTrue((manifest.parent / source).is_file())
                self.assertEqual(len(ids), len(set(ids)))
                for language, source in data.get("references", {}).items():
                    self.assertIn(language, bench.LANGS)
                    self.assertTrue((manifest.parent / source).is_file())

    def test_language_baselines_exist(self):
        """Prevents selected languages from lacking their startup baseline."""
        for language in bench.LANGS.values():
            with self.subTest(language=language.name):
                self.assertTrue((bench.BASELINES / language.baseline).is_file())

    def test_label_families(self):
        """Prevents report baseline matching from using the wrong label family."""
        self.assertEqual(bench.family("arx"), "arx")
        self.assertEqual(bench.family("arx-variant"), "arx")
        self.assertEqual(bench.family("python-checked"), "python")

    def test_unknown_language_exits(self):
        """Prevents typos in explicit language selections from being ignored."""
        with self.assertRaises(SystemExit):
            bench.select_langs("unknown")

    def test_unknown_suite_exits(self):
        """Prevents typos in explicit suite selections from running nothing."""
        with self.assertRaises(SystemExit):
            bench.load_suites(["unknown"])
