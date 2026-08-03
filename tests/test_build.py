import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)


class BuildTests(unittest.TestCase):
    def test_setlist_order_main_then_encores(self):
        fixture = json.loads((ROOT / "tests/fixtures/setlistfm_sample.json").read_text(encoding="utf-8"))["setlist"][0]
        songs = mod.api_song_list(fixture)
        self.assertEqual([s["section"] for s in songs], ["Mainset", "Mainset", "Encore 1", "Encore 2"])

    def test_build_fixture_updates_existing_concert(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "index.html"
            stats = mod.build(
                ROOT / "site-template/index.html",
                output,
                api_key=None,
                years=2,
                fixture=ROOT / "tests/fixtures/setlistfm_sample.json",
            )
            text = output.read_text(encoding="utf-8")
            match = mod.DATA_RE.search(text)
            self.assertIsNotNone(match)
            concerts = json.loads(match.group(2))
            target = [c for c in concerts if c.get("date") == "2026-07-26" and c.get("city") == "Nîmes"]
            self.assertEqual(len(target), 1)
            self.assertEqual(target[0]["setlist"][0]["section"], "Mainset")
            self.assertEqual(target[0]["setlist"][-1]["section"], "Encore 2")
            self.assertEqual(target[0]["setlistFmId"], "test123")
            self.assertIn("setlist.fm", text)
            self.assertEqual(stats["created"], 0)


if __name__ == "__main__":
    unittest.main()
