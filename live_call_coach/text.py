"""Small text helpers: question detection, hard-question flag, commitments, keyword overlap."""
import re

WH = ("what", "why", "how", "when", "where", "who", "which", "can", "could", "would",
      "do", "does", "did", "is", "are", "have", "tell me", "walk me through", "describe",
      "explain", "give me an example")
HARD_WORDS = ("weakness", "failure", "failed", "conflict", "disagree", "gap", "leave", "left",
              "salary", "compensation", "rate", "mistake", "fired", "trade-off", "tradeoff",
              "biggest", "hardest")
STOP = set("a an the of to in on for and or is are was were be been it this that with as at by "
           "from you your i we our my me do does did have has had can could would about what "
           "how why when where who which tell give any some more not no yes so if then than".split())

PROMISE = re.compile(r"\b(i'll|i will|we'll|we will|let me|i can send|i'm going to)\b", re.I)
REQUEST = re.compile(r"^(?:(?P<name>[A-Z][a-z]+),?\s+)?(?:can|could|would) you\b", re.I)
WHEN = re.compile(r"\b(by (?:end of day|eod|tomorrow|monday|tuesday|wednesday|thursday|friday|"
                  r"next week|the \d{1,2}(?:st|nd|rd|th))|tomorrow|today|this week|next week|"
                  r"on (?:monday|tuesday|wednesday|thursday|friday)|end of day|eod)\b", re.I)


def tokens(text):
    out = []
    for w in re.findall(r"[a-z0-9']+", text.lower()):
        w = w.strip("'")
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        if w and w not in STOP:
            out.append(w)
    return out


def overlap(query, text):
    q, t = set(tokens(query)), set(tokens(text))
    return len(q & t)


def is_question(text):
    t = text.strip().lower()
    if not t:
        return False
    if t.endswith("?"):
        return True
    return any(t.startswith(w + " ") or t == w for w in WH) and len(t.split()) >= 4


def is_hard(text):
    t = text.lower()
    return len(t.split()) > 28 or sum(t.count(c) for c in "?,") >= 3 or any(w in t for w in HARD_WORDS)


def commitments(speaker, text, t=None):
    """Return [{who, what, when}] found in one utterance."""
    found = []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        when = WHEN.search(sent)
        when = when.group(0).lower() if when else None
        m = REQUEST.match(sent)
        if m:
            what = re.sub(r"^.*?\byou\b\s*", "", sent, count=1, flags=re.I).rstrip("?. ")
            found.append({"who": m.group("name") or "unassigned", "what": what, "when": when,
                          "asked_by": speaker, "t": t})
        elif PROMISE.search(sent):
            what = PROMISE.split(sent, maxsplit=1)[-1].strip(" ,.")
            found.append({"who": speaker, "what": what, "when": when, "asked_by": None, "t": t})
    return found
