"""LLM adapters. The pipeline only calls ``complete(prompt, tier) -> str``.

StubLLM is deterministic and offline: demo and tests use it. CommandLLM pipes the prompt to any
local CLI (for example ``ollama run llama3.2``). OllamaLLM talks to a local Ollama server. Nothing
here carries a key, and nothing calls a hosted API.
"""
import json
import re
import subprocess
import urllib.request

from .text import overlap

TIER_LATENCY = {"quick": 1.5, "deep": 5.0, "meeting": 2.0}


class StubLLM:
    """Reads the 'Question:' and context bullet lines of the prompt and answers from them."""

    real = False

    def latency_hint(self, tier):
        return TIER_LATENCY.get(tier, 2.0)

    def complete(self, prompt, tier):
        q = _field(prompt, "Question")
        ctx = [l[2:] for l in prompt.splitlines() if l.startswith("- ")]
        ranked = sorted(ctx, key=lambda c: -overlap(q, c))
        top = [c for c in ranked if overlap(q, c)][:3] or ranked[:1]
        if tier == "meeting":
            facts = [c.split(" | ")[0] for c in top]
            say = "Good question. " + (facts[0] if facts else "I will check and come back to you.")
            return json.dumps({"say": say, "facts": facts})
        points = [c.split(" | ")[0] for c in top]
        opening = ("Yes, I have a concrete example for this; lead with the result."
                   if points else "No stored example matches; answer from general experience.")
        if tier == "quick":
            filler = [c.split(" | ")[0] for c in ranked if c.split(" | ")[0] not in points]
            return json.dumps({"opening": opening, "points": (points + filler)[:3]})
        body = " ".join(points) if points else "No stored story matches; answer from general experience."
        return json.dumps({"answer": "Start with the situation, then the action, then the result. " + body,
                           "cites": [c.split(" | ")[1] for c in top if " | " in c]})


class CommandLLM:
    """Runs a local command, writes the prompt to its stdin, reads the answer from stdout."""

    real = True

    def __init__(self, command, timeout=60):
        self.command, self.timeout = command, timeout

    def complete(self, prompt, tier):
        p = subprocess.run(self.command, input=prompt, capture_output=True, text=True,
                           shell=isinstance(self.command, str), timeout=self.timeout)
        if p.returncode:
            raise RuntimeError("command failed: " + p.stderr.strip()[:200])
        return p.stdout


class OllamaLLM:
    """Local Ollama server on localhost. Pick the model with --model."""

    real = True

    def __init__(self, model="llama3.2", url="http://127.0.0.1:11434", timeout=60):
        self.model, self.url, self.timeout = model, url.rstrip("/"), timeout

    def complete(self, prompt, tier):
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(self.url + "/api/generate", body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())["response"]


def make(kind="stub", model=None, command=None):
    if kind == "stub":
        return StubLLM()
    if kind == "ollama":
        return OllamaLLM(model or "llama3.2")
    if kind == "cmd":
        if not command:
            raise SystemExit("--llm cmd needs --cmd, for example --cmd 'ollama run llama3.2'")
        return CommandLLM(command)
    raise SystemExit("unknown --llm " + kind)


def _field(prompt, name):
    m = re.search(r"^%s: (.*)$" % name, prompt, re.M)
    return m.group(1) if m else ""


def parse_json(raw, fallback_key):
    """Real models drift: take the first JSON object, else treat the whole text as one field."""
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except ValueError:
            pass
    return {fallback_key: raw.strip()}
