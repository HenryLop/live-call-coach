"""Write ui/data.js from data/ and the offline pipeline, so the static UI replays the same calls.

    python tools/export_ui_data.py          # rewrite ui/data.js
    python tools/export_ui_data.py --check  # exit 1 when ui/data.js is out of date

Timings, hard flags, stale drops, retrieved notes and the commitments ledger come from the
engine run on the bundled transcripts. The wording of opening lines and deep answers is
written here for the demo (the stub model's own wording is a placeholder), and says only
what the bundled notes say.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from live_call_coach import adapters, cli, engine, text  # noqa: E402
from live_call_coach.knowledge import Knowledge  # noqa: E402

OUT = os.path.join(ROOT, "ui", "data.js")

GIST = {
    "story-batch": "Nightly pipeline: 6 hours down to 90 minutes",
    "story-outage": "Stale-report incident, contract test added",
    "story-conflict": "Deadline dispute, two-option cost table",
    "story-mentor": "Mentored two juniors through on-call",
    "story-migration": "Warehouse migration, 140 tables",
    "story-gap": "Four months: streaming course, open-source tool",
    "skills": "Python, SQL, Airflow, dbt, Kafka",
    "goal": "Wants ownership of data quality",
}

# Wording written for the demo, keyed by the question's line number in the transcript.
INTERVIEW_COPY = {
    0: dict(opening="Say it plainly: you want to own data quality, and this posting describes that job.",
            answer="You want ownership of data quality for a product team, and the posting describes exactly that. "
                   "Back it with the stack you use every day: Python, SQL, Airflow and dbt.",
            cites=["goal", "skills"]),
    2: dict(opening="Yes, you have one. Lead with the result: six hours down to ninety minutes.",
            answer="The nightly order pipeline went from 6 hours to 90 minutes. Say how: the load was "
                   "partitioned and the dimension lookups were cached.",
            cites=["story-batch"]),
    3: dict(opening="Name the tools first, then tie them to the pipeline work.",
            answer="Python, SQL, Airflow and dbt day to day, with Kafka for streaming work. In the pipeline story, "
                   "the caching sat in front of the dimension tables.",
            cites=["skills", "story-batch"]),
    5: dict(opening="Own it first: a schema change shipped a stale report. Then the fix.",
            answer="A schema change broke a report. Name it, then the repair: a contract test and a dry-run step "
                   "so it cannot happen again.",
            cites=["story-outage"]),
    8: dict(opening="Yes. A deadline clash with a product lead, and how it was settled.",
            answer="You disagreed with a product lead about a deadline. A two-option cost table led to a smaller "
                   "first release that both sides accepted.",
            cites=["story-conflict"]),
    10: dict(opening="Short and calm: four months, used on a streaming course and a small tool.",
             answer="Four months between roles, spent finishing a streaming course and building a small "
                    "open-source ingestion tool. Close on what you learned from it.",
             cites=["story-gap"]),
}

MEETING_COPY = {
    1: "The export times out above 50,000 rows. A paged fix is merged and waits for the next release.",
    3: "The next release is planned for Thursday 29 October, with a rollback plan attached.",
    4: "Twelve per seat per month, billed annually, with a ten-seat minimum.",
    6: "Yes. Single sign-on works over SAML 2.0 and is included in the team plan.",
    7: "That one is for Priya. The template is in the shared drive. Listen, and her answer goes in the ledger.",
    9: "Support lead first, then the platform on-call. The export fix is merged and waits for release.",
}


def lat(card):
    return round(card["t_ready"] - card["t_asked"], 2)


def interview(events):
    kb = Knowledge.load(os.path.join(ROOT, "data", "profile.json"))
    notes = [{"id": i["id"], "gist": GIST[i["id"]], "text": i["text"]} for i in kb.items]
    by_text = {i["text"]: i["id"] for i in kb.items}
    base = engine.run(engine.InterviewCoach(adapters.StubLLM(), kb), events)
    quick = {c["t_asked"]: c for c in base if c["kind"] == "card" and c["tier"] == "quick"}
    deep = {c["t_asked"]: c for c in base if c["kind"] == "card" and c["tier"] == "deep"}
    dropped = {r["question"] for r in base if r["kind"] == "dropped"}
    out = []
    for n, ev in enumerate(events):
        row = {"t": ev["t"]}
        if "key" in ev:
            row["key"] = ev["key"]
        else:
            row.update(speaker=ev["speaker"], text=ev["text"])
            if ev["speaker"] != "me" and text.is_question(ev["text"]):
                c = quick.get(ev["t"])
                if c is None:  # dropped before its card was shown: build the card for the record
                    c = engine.run(engine.InterviewCoach(adapters.StubLLM(), kb), [ev])[0]
                copy = INTERVIEW_COPY[n]
                row["q"] = {
                    "hard": text.is_hard(ev["text"]),
                    "quick": {"latency": 1.5, "opening": copy["opening"],
                              "points": [by_text[p] for p in c["points"]]},
                    "deep": {"latency": lat(deep[ev["t"]]) if ev["t"] in deep else 5.0,
                             "answer": copy["answer"], "cites": copy["cites"]},
                    "autoDeep": ev["t"] in deep,
                    "staleInEngine": ev["text"] in dropped,
                }
        out.append(row)
    return {"notes": notes, "events": out}


def meeting(events):
    kb = Knowledge.load(os.path.join(ROOT, "data", "meeting_facts.json"))
    recs = engine.run(engine.MeetingBrain(adapters.StubLLM(), kb), events)
    dropped = {r["question"] for r in recs if r["kind"] == "dropped"}
    out = []
    for n, ev in enumerate(events):
        row = {"t": ev["t"], "speaker": ev["speaker"], "text": ev["text"]}
        found = [r for r in recs if r["kind"] == "commitment" and r["t"] == ev["t"]]
        if found:
            row["commitments"] = [{"who": c["who"], "what": c["what"], "when": c["when"],
                                   "asked_by": c["asked_by"]} for c in found]
        upd = [r for r in recs if r["kind"] == "commitment_update" and r["t"] == ev["t"]]
        if upd:
            row["confirms"] = [{"who": c["who"], "asked_by": c["asked_by"], "when": c["when"]} for c in upd]
        if ev["speaker"] != "me" and text.is_question(ev["text"]):
            def score(h):
                return text.overlap(ev["text"], h["text"] + " " + " ".join(h.get("tags", [])))
            found_hits = kb.search(ev["text"], 3)
            top = max(score(h) for h in found_hits)
            # a card shows only facts that answer its own question, not weak keyword matches
            hits = sorted([h for h in found_hits if score(h) * 3 >= top * 2],
                          key=lambda h: -text.overlap(MEETING_COPY[n], h["text"]))
            row["q"] = {
                "latency": 2.0,
                "say": MEETING_COPY[n],
                "facts": [{"text": h["text"], "source": h["source"]} for h in hits[:2]],
                "staleInEngine": ev["text"] in dropped,
            }
        out.append(row)
    return {"events": out}


def build():
    data = {
        "interview": interview(cli.load_events(os.path.join(ROOT, "data", "interview.jsonl"))),
        "meeting": meeting(cli.load_events(os.path.join(ROOT, "data", "meeting.jsonl"))),
    }
    body = json.dumps(data, indent=1, ensure_ascii=False)
    return ("// Generated by tools/export_ui_data.py from data/ and the offline pipeline. Do not edit.\n"
            "window.COACH_DATA = " + body + ";\n")


if __name__ == "__main__":
    new = build()
    if "--check" in sys.argv:
        old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        sys.exit(0 if old == new else 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print("wrote", OUT)
