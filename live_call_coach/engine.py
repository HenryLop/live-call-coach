"""The coaching pipeline for both modes.

Events come in with a clock ``t`` (seconds). Each tier has a latency: the stub reports a fixed hint
(quick 1.5 s, deep 5 s, meeting 2 s), a real model reports the time its call took. A card is shown
once its ready time has passed; if a new question starts first, the old card is dropped and a
``dropped`` record is emitted instead. The clock is simulated, so replays are instant and repeatable.
"""
import time

from . import adapters, text
from .knowledge import Knowledge


class Pipeline:
    def __init__(self, llm, knowledge, me="me"):
        self.llm, self.kb, self.me = llm, knowledge, me
        self.qid = 0
        self.pending = []      # dicts with ready_t, qid, card
        self.question = ""
        self.ledger = []       # meeting mode: commitments
        self.stats = []        # wall-clock ms of the stub/real call per card

    # -- clock -------------------------------------------------------------
    def _flush(self, upto):
        due = sorted([p for p in self.pending if p["ready_t"] <= upto], key=lambda p: p["ready_t"])
        self.pending = [p for p in self.pending if p["ready_t"] > upto]
        return [p["card"] for p in due]

    def _drop_stale(self, t):
        out = [{"kind": "dropped", "tier": p["card"]["tier"], "qid": p["qid"], "t": t,
                "question": p["card"]["question"]} for p in self.pending]
        self.pending = []
        return out

    def finish(self):
        return self._flush(float("inf"))

    def _call(self, prompt, tier):
        t0 = time.perf_counter()
        raw = self.llm.complete(prompt, tier)
        ms = (time.perf_counter() - t0) * 1000
        self.stats.append(ms)
        hint = self.llm.latency_hint(tier) if hasattr(self.llm, "latency_hint") else ms / 1000
        return raw, ms, hint

    def _schedule(self, t, tier, build):
        card = build()
        card.update({"kind": "card", "tier": tier, "qid": self.qid, "question": self.question,
                     "t_asked": t, "t_ready": round(t + card.pop("_latency"), 2)})
        self.pending.append({"ready_t": card["t_ready"], "qid": self.qid, "card": card})


class InterviewCoach(Pipeline):
    """Tiers: quick (opening line, three points, hard flag) and deep (grounded answer with cites)."""

    def feed(self, ev):
        out = self._flush(ev["t"])
        if ev.get("key") == "escalate":
            if self.question and not any(p["card"]["tier"] == "deep" for p in self.pending) \
                    and not self._deep_done:
                self._schedule(ev["t"], "deep", lambda: self._deep(self.question))
            return out + self._flush(ev["t"])
        if ev.get("speaker") == self.me or not text.is_question(ev.get("text", "")):
            return out
        out += self._drop_stale(ev["t"])
        self.qid += 1
        self.question = ev["text"]
        self._deep_done = False
        hard = text.is_hard(ev["text"])
        self._schedule(ev["t"], "quick", lambda: self._quick(self.question, hard))
        if hard:
            self._deep_done = True
            self._schedule(ev["t"], "deep", lambda: self._deep(self.question))
        return out

    _deep_done = False

    def _context(self, q, k, fill=False):
        hits = self.kb.search(q, k)
        if fill:  # the quick tier always wants k items, relevant ones first
            hits += [i for i in self.kb.items if i not in hits][:k - len(hits)]
        return "\n".join("- %s | %s" % (i["text"], i["id"]) for i in hits)

    def _quick(self, q, hard):
        prompt = ("You are a live interview coach. Reply as JSON with opening and points (3 items).\n"
                  "Question: %s\nContext:\n%s\n" % (q, self._context(q, 3, fill=True)))
        raw, ms, lat = self._call(prompt, "quick")
        d = adapters.parse_json(raw, "opening")
        pts = [p for p in d.get("points", []) if p][:3]
        return {"opening": d.get("opening", ""), "points": pts, "hard": hard,
                "_latency": lat, "compute_ms": round(ms, 2)}

    def _deep(self, q):
        prompt = ("You are a live interview coach. Give a grounded answer using only the context. "
                  "Reply as JSON with answer and cites.\nQuestion: %s\nContext:\n%s\n" % (q, self._context(q, 5)))
        raw, ms, lat = self._call(prompt, "deep")
        d = adapters.parse_json(raw, "answer")
        return {"answer": d.get("answer", ""), "cites": d.get("cites", []),
                "_latency": lat, "compute_ms": round(ms, 2)}


class MeetingBrain(Pipeline):
    """One card per question: what was asked, a line to say, key facts, sources, open commitments."""

    def feed(self, ev):
        out = self._flush(ev["t"])
        if "text" not in ev:
            return out
        for c in text.commitments(ev["speaker"], ev["text"], ev["t"]):
            key = (c["who"].lower(), c["what"].lower())
            if all((x["who"].lower(), x["what"].lower()) != key for x in self.ledger):
                self.ledger.append(c)
                out.append(dict(c, kind="commitment"))
        if ev["speaker"] != self.me and text.is_question(ev["text"]):
            out += self._drop_stale(ev["t"])
            self.qid += 1
            self.question = ev["text"]
            self._schedule(ev["t"], "meeting", lambda: self._card(self.question))
        return out

    def _card(self, q):
        hits = self.kb.search(q, 3)
        ctx = "\n".join("- %s | %s" % (i["text"], i["source"]) for i in hits)
        prompt = ("You assist in a meeting. Reply as JSON with say and facts.\nQuestion: %s\nContext:\n%s\n" % (q, ctx))
        raw, ms, lat = self._call(prompt, "meeting")
        d = adapters.parse_json(raw, "say")
        return {"asked": q, "say": d.get("say", ""), "facts": d.get("facts", []),
                "sources": sorted({i["source"] for i in hits}),
                "commitments": [dict(c) for c in self.ledger],
                "_latency": lat, "compute_ms": round(ms, 2)}


def run(pipeline, events):
    """Feed all events, return every output record in order."""
    out = []
    for ev in events:
        out += pipeline.feed(ev)
    return out + pipeline.finish()
