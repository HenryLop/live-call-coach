import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from live_call_coach import adapters, cli, engine, overlay, reader, sim, text  # noqa: E402
from live_call_coach.knowledge import Knowledge  # noqa: E402


def events(name):
    return cli.load_events(os.path.join(ROOT, "data", name))


def interview(evs):
    kb = Knowledge.load(os.path.join(ROOT, "data", "profile.json"))
    return engine.run(engine.InterviewCoach(adapters.StubLLM(), kb), evs)


def meeting(evs):
    kb = Knowledge.load(os.path.join(ROOT, "data", "meeting_facts.json"))
    pipe = engine.MeetingBrain(adapters.StubLLM(), kb)
    return pipe, engine.run(pipe, evs)


class TextTests(unittest.TestCase):
    def test_question_detection(self):
        self.assertTrue(text.is_question("Tell me about a time you led a project."))
        self.assertTrue(text.is_question("Is this ready?"))
        self.assertFalse(text.is_question("Thanks everyone, let's begin."))

    def test_hard_flag(self):
        self.assertTrue(text.is_hard("What was your biggest mistake?"))
        self.assertFalse(text.is_hard("Why this role?"))

    def test_commitments(self):
        c = text.commitments("Sam", "I'll send the notes by tomorrow.")
        self.assertEqual((c[0]["who"], c[0]["when"]), ("Sam", "by tomorrow"))
        c = text.commitments("Dana", "Priya, can you share the file by end of day?")
        self.assertEqual((c[0]["who"], c[0]["what"]), ("Priya", "share the file by end of day"))


class InterviewTests(unittest.TestCase):
    def test_quick_tier_shape(self):
        recs = interview(events("interview.jsonl"))
        quick = [r for r in recs if r["kind"] == "card" and r["tier"] == "quick"]
        self.assertTrue(quick)
        for r in quick:
            self.assertEqual(round(r["t_ready"] - r["t_asked"], 2), 1.5)
            self.assertTrue(r["opening"])
            self.assertEqual(len(r["points"]), 3)

    def test_stale_answer_dropped(self):
        recs = interview(events("interview.jsonl"))
        dropped = [r for r in recs if r["kind"] == "dropped"]
        self.assertTrue(any("faster" in r["question"] for r in dropped))
        shown = [r["question"] for r in recs if r["kind"] == "card"]
        self.assertFalse(any("faster" in q for q in shown))

    def test_hard_question_gets_deep_tier_and_key_escalates(self):
        recs = interview(events("interview.jsonl"))
        deep = [r for r in recs if r["kind"] == "card" and r["tier"] == "deep"]
        self.assertTrue(any("mistake" in r["question"] for r in deep))
        # a non-hard question only gets a deep card through the escalate key
        evs = [{"t": 1, "speaker": "Interviewer", "text": "Why this company?"}]
        self.assertFalse([r for r in interview(evs) if r.get("tier") == "deep"])
        evs.append({"t": 3, "key": "escalate"})
        self.assertTrue([r for r in interview(evs) if r.get("tier") == "deep"])

    def test_own_lines_are_not_questions(self):
        evs = [{"t": 1, "speaker": "me", "text": "Is that clear?"}]
        self.assertEqual(interview(evs), [])

    def test_deep_answer_cites_stored_stories(self):
        recs = interview(events("interview.jsonl"))
        deep = [r for r in recs if r["kind"] == "card" and r["tier"] == "deep" and "mistake" in r["question"]][0]
        self.assertIn("story-outage", deep["cites"])


class MeetingTests(unittest.TestCase):
    def test_card_has_all_parts(self):
        _, recs = meeting(events("meeting.jsonl"))
        card = [r for r in recs if r["kind"] == "card" and "sign-on" in r["asked"]][0]
        self.assertTrue(card["say"])
        self.assertIn("docs/sso.md", card["sources"])
        self.assertTrue(card["facts"])

    def test_commitments_ledger(self):
        pipe, _ = meeting(events("meeting.jsonl"))
        pairs = {(c["who"], c["when"]) for c in pipe.ledger}
        self.assertIn(("me", "by tomorrow"), pairs)
        self.assertIn(("Priya", "by end of day"), pairs)

    def test_stale_card_dropped(self):
        _, recs = meeting(events("meeting.jsonl"))
        self.assertTrue(any(r["kind"] == "dropped" and "release" in r["question"] for r in recs))

    def test_overlay_renders_every_record(self):
        _, recs = meeting(events("meeting.jsonl"))
        for r in recs:
            self.assertTrue(overlay.render(r))
        path = os.path.join(tempfile.mkdtemp(), "p.html")
        overlay.write_html(recs, path)
        self.assertIn("refresh", open(path, encoding="utf-8").read())


class ReaderTests(unittest.TestCase):
    def test_only_click_is_captions(self):
        page = sim.SimulatedMeetingPage(events("meeting.jsonl"))
        out = tempfile.mkdtemp()
        reader.CaptionReader(page, out).run()
        self.assertEqual(page.clicks, ["Turn on captions"])

    def test_forbidden_click_refused(self):
        page = sim.SimulatedMeetingPage([])
        with self.assertRaises(reader.ForbiddenClick):
            reader.safe_click(page, "captions", "Leave call")
        with self.assertRaises(reader.ForbiddenClick):
            reader.safe_click(page, "mute", "Mute microphone")
        self.assertEqual(page.clicks, [])

    def test_source_has_no_input_or_send_calls(self):
        src = open(os.path.join(ROOT, "live_call_coach", "reader.py"), encoding="utf-8").read()
        code = src.split('"""', 2)[2]
        for bad in (".type(", ".fill(", ".press(", "keyboard", "mouse", "send_keys", "sendKeys", ".submit("):
            self.assertNotIn(bad, code)
        self.assertEqual(list(reader.ALLOWED_CLICKS), ["captions"])

    def test_session_roundtrip_and_replay(self):
        evs = events("meeting.jsonl")
        out = tempfile.mkdtemp()
        reader.CaptionReader(sim.SimulatedMeetingPage(evs), out).run()
        for name in ("events.jsonl", "live.json", "transcript.md"):
            self.assertTrue(os.path.exists(os.path.join(out, name)), name)
        saved = reader.load_session(out)
        self.assertEqual(saved, evs)
        _, a = meeting(saved)
        _, b = meeting(evs)
        self.assertEqual([r.get("say") for r in a], [r.get("say") for r in b])


class AdapterTests(unittest.TestCase):
    def test_parse_json_tolerates_chatter(self):
        self.assertEqual(adapters.parse_json('Sure! {"say": "hi"} done', "say"), {"say": "hi"})
        self.assertEqual(adapters.parse_json("plain words", "say"), {"say": "plain words"})

    def test_command_adapter_runs_a_local_command(self):
        cmd = [sys.executable, "-c", "import sys;sys.stdin.read();print('{\"opening\": \"ok\", \"points\": [\"a\"]}')"]
        kb = Knowledge.load(os.path.join(ROOT, "data", "profile.json"))
        recs = engine.run(engine.InterviewCoach(adapters.CommandLLM(cmd), kb),
                          [{"t": 1, "speaker": "Interviewer", "text": "Why this company?"}])
        self.assertEqual(recs[0]["opening"], "ok")

    def test_cli_runs(self):
        self.assertEqual(cli.main(["--mode", "interview"]), 0)
        self.assertEqual(cli.main(["--mode", "meeting", "--simulate", os.path.join(tempfile.mkdtemp(), "s")]), 0)


if __name__ == "__main__":
    unittest.main()
