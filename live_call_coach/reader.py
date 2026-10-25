"""Read-only meeting reader.

It watches a call through a page driver and writes what it sees to a session folder:

    events.jsonl    one line per final caption (t, speaker, text)
    live.json       the caption being spoken right now (overwritten)
    transcript.md   written when the call ends

The only click it may ever make is turning on captions. ``safe_click`` looks the button name up in
ALLOWED_CLICKS and refuses anything else; tests/test_readonly.py also scans this file's source for
typing, key presses, form filling and sending. A driver only has to provide:

    page.click(button_name)  -> None
    page.poll()              -> {"speaker", "text", "final": bool, "t": float} or None
    page.closed              -> bool
"""
import json
import os
import re

ALLOWED_CLICKS = {
    "captions": re.compile(r"^(Turn on captions|Activate captions)( \(c\))?$", re.I),
}


class ForbiddenClick(Exception):
    pass


def safe_click(page, key, button_name):
    pattern = ALLOWED_CLICKS.get(key)
    if pattern is None or not pattern.match(button_name):
        raise ForbiddenClick("click %r (%r) is not on the allow-list" % (key, button_name))
    page.click(button_name)


class CaptionReader:
    def __init__(self, page, out_dir, button_name="Turn on captions"):
        self.page, self.out_dir, self.button_name = page, out_dir, button_name
        os.makedirs(out_dir, exist_ok=True)
        self.events = []

    def run(self, max_polls=100000):
        safe_click(self.page, "captions", self.button_name)
        for _ in range(max_polls):
            if self.page.closed:
                break
            cap = self.page.poll()
            if cap is None:
                continue
            if cap["final"]:
                ev = {"t": cap["t"], "speaker": cap["speaker"], "text": cap["text"]}
                self.events.append(ev)
                with open(os.path.join(self.out_dir, "events.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps(ev) + "\n")
            else:
                with open(os.path.join(self.out_dir, "live.json"), "w", encoding="utf-8") as f:
                    json.dump({"speaker": cap["speaker"], "text": cap["text"], "t": cap["t"]}, f)
        self._transcript()
        return self.events

    def _transcript(self):
        lines = ["# Transcript", ""] + ["**%s** (%.0fs): %s" % (e["speaker"], e["t"], e["text"]) for e in self.events]
        with open(os.path.join(self.out_dir, "transcript.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def load_session(out_dir):
    """Read a saved session folder back as pipeline events (replay instead of a live call)."""
    with open(os.path.join(out_dir, "events.jsonl"), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]
