import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(ROOT, "ui")


def read(name):
    with open(os.path.join(UI, name), encoding="utf-8") as f:
        return f.read()


class UiTests(unittest.TestCase):
    def test_index_exists_and_loads_local_files_only(self):
        self.assertTrue(os.path.isfile(os.path.join(UI, "index.html")))
        for name in os.listdir(UI):
            if name.endswith((".html", ".css", ".js")):
                self.assertNotRegex(read(name), r"https?://", name + " must not reference a URL")
        refs = re.findall(r'(?:src|href)="([^"]+)"', read("index.html"))
        for ref in refs:
            if ref.startswith("data:"):
                continue
            self.assertTrue(os.path.isfile(os.path.join(UI, ref)), "missing local file: " + ref)

    def test_ui_data_is_in_sync_with_data_folder(self):
        script = os.path.join(ROOT, "tools", "export_ui_data.py")
        r = subprocess.run([sys.executable, script, "--check"], cwd=ROOT)
        self.assertEqual(r.returncode, 0, "run: python tools/export_ui_data.py")

    def test_both_views_and_the_controls_exist(self):
        html = read("index.html")
        for needle in ('id="tab-interview"', 'id="tab-meeting"', 'id="play"', 'id="restart"', 'id="speed"', 'id="esc"'):
            self.assertIn(needle, html)
        self.assertIn("prefers-reduced-motion", read("style.css"))
        self.assertIn("prefers-reduced-motion", read("app.js"))


if __name__ == "__main__":
    unittest.main()
