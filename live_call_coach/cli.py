import argparse
import json
import os
import statistics
import sys
import tempfile
import time

from . import adapters, engine, overlay, reader, sim
from .knowledge import Knowledge

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def load_events(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def build(mode, llm):
    if mode == "interview":
        return engine.InterviewCoach(llm, Knowledge.load(os.path.join(DATA, "profile.json")))
    return engine.MeetingBrain(llm, Knowledge.load(os.path.join(DATA, "meeting_facts.json")))


def run_mode(mode, events, llm, html=None, out=print):
    pipe = build(mode, llm)
    records = engine.run(pipe, events)
    for r in records:
        out(overlay.render(r))
        out("")
    if html:
        overlay.write_html(records, html)
    return pipe, records


def summary(pipe, records):
    cards = [r for r in records if r["kind"] == "card"]
    drops = [r for r in records if r["kind"] == "dropped"]
    ms = pipe.stats
    line = "%d cards, %d dropped as stale" % (len(cards), len(drops))
    if ms:
        line += ", pipeline compute median %.2f ms, max %.2f ms" % (statistics.median(ms), max(ms))
    return line


def main(argv=None):
    ap = argparse.ArgumentParser(prog="live_call_coach")
    ap.add_argument("--mode", choices=["interview", "meeting"], required=True)
    ap.add_argument("--transcript", help="JSONL of {t, speaker, text}; default is the bundled sample")
    ap.add_argument("--session", help="replay a saved session folder (events.jsonl) instead")
    ap.add_argument("--audio", help="transcribe this file with faster-whisper (optional extra)")
    ap.add_argument("--simulate", metavar="DIR", help="run the read-only reader against the offline "
                    "simulator, save the session to DIR, then coach from it")
    ap.add_argument("--llm", choices=["stub", "ollama", "cmd"], default="stub")
    ap.add_argument("--model")
    ap.add_argument("--cmd", help="shell command that reads a prompt on stdin, e.g. 'ollama run llama3.2'")
    ap.add_argument("--html", help="also write a self-refreshing prompter page here")
    a = ap.parse_args(argv)

    default = "interview.jsonl" if a.mode == "interview" else "meeting.jsonl"
    if a.audio:
        from . import whisper_source
        events = whisper_source.transcribe(a.audio)
    elif a.session:
        events = reader.load_session(a.session)
    else:
        events = load_events(a.transcript or os.path.join(DATA, default))

    if a.simulate:
        page = sim.SimulatedMeetingPage(events)
        saved = reader.CaptionReader(page, a.simulate).run()
        print("reader saved %d final captions to %s (clicks made: %s)\n" % (len(saved), os.path.basename(a.simulate) or a.simulate, page.clicks))
        events = reader.load_session(a.simulate)

    llm = adapters.make(a.llm, a.model, a.cmd)
    pipe, records = run_mode(a.mode, events, llm, a.html)
    print(summary(pipe, records))
    return 0
