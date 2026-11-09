import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))
import bench  # noqa: E402


def make(root, name, env=None, marker=None):
    d = root / name
    d.mkdir()
    if env is not None:
        (d / "environment.json").write_text(json.dumps(env))
    if marker is not None:
        (d / "complete.json").write_text(marker if isinstance(marker, str) else json.dumps(marker))
    return d


class RunCompletion(unittest.TestCase):
    def test_completion_and_latest_selection(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            ok = {"status": "complete", "timestamp_utc": "2026-11-08T002839Z"}
            new = make(root, "2026-11-08T002839Z_darwin-arm64_arx-1.28.0", {"timestamp_utc": "2026-11-08T002839Z"}, ok)
            old = make(root, "2026-11-08_darwin-arm64_arx-1.27.0", {"date": "2026-11-08"},
                       {"status": "complete", "timestamp_utc": "2026-11-08T000000Z"})
            no_marker = make(root, "2026-11-09T010101Z_x", {"timestamp_utc": "2026-11-09T010101Z"})
            partial = make(root, ".2026-11-10T010101Z_x.partial", {"timestamp_utc": "x"}, ok)
            corrupt = make(root, "corrupt", {}, "{not json")
            legacy = make(root, "legacy", {"date": "2026-11-05"})

            self.assertTrue(bench.is_complete(new))
            self.assertTrue(bench.is_complete(old))
            self.assertFalse(bench.is_complete(no_marker))
            self.assertFalse(bench.is_complete(partial))
            self.assertFalse(bench.is_complete(corrupt))
            self.assertEqual(bench.run_timestamp(legacy), "2026-11-05T000000Z")

            complete = [p for p in root.glob("*") if bench.is_complete(p)]
            self.assertEqual(max(complete, key=bench.run_timestamp), new)
            self.assertEqual(sorted(complete, key=lambda p: p.name)[-1], old)  # name sorting is wrong


if __name__ == "__main__":
    unittest.main()