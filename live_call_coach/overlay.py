"""Teleprompter output: a plain-text card for the terminal and a self-refreshing HTML page."""
import html
import os
import textwrap


def render(rec, width=72):
    """One record from the pipeline -> printable text."""
    k = rec["kind"]
    if k == "dropped":
        return "[%5.1fs] dropped %s answer (a new question started)" % (rec["t"], rec["tier"])
    if k == "commitment":
        return "[%5.1fs] commitment: %s -> %s%s" % (rec["t"], rec["who"], rec["what"],
                                                   " (%s)" % rec["when"] if rec["when"] else "")
    if k == "commitment_update":
        return "[%5.1fs] confirmed: %s -> %s%s" % (rec["t"], rec["who"], rec["what"],
                                                  " (%s)" % rec["when"] if rec["when"] else "")
    head = "[%5.1fs] %s tier, question #%d: %s" % (rec["t_ready"], rec["tier"].upper(), rec["qid"], rec["question"])
    body = []
    if rec["tier"] == "quick":
        body.append("SAY: " + rec["opening"])
        body += ["  %d. %s" % (i + 1, p) for i, p in enumerate(rec["points"])]
        if rec["hard"]:
            body.append("  !! hard question: deep tier is on the way")
    elif rec["tier"] == "deep":
        body.append("ANSWER: " + rec["answer"])
        if rec["cites"]:
            body.append("  from: " + ", ".join(rec["cites"]))
    else:
        body.append("SAY: " + rec["say"])
        body += ["  fact: " + f for f in rec["facts"]]
        body.append("  sources: " + (", ".join(rec["sources"]) or "none"))
        open_ = [c for c in rec["commitments"]]
        if open_:
            body.append("  open commitments: " + "; ".join("%s: %s" % (c["who"], c["what"]) for c in open_))
    wrap = lambda s: textwrap.fill(s, width, subsequent_indent="    ")
    return "\n".join([wrap(head)] + [wrap(b) for b in body])


def write_html(records, path):
    """Write the latest card of each tier to a page that reloads itself every second."""
    cards = [r for r in records if r["kind"] == "card"][-3:]
    blocks = "".join("<pre>%s</pre>" % html.escape(render(c)) for c in cards) or "<p>waiting</p>"
    page = ("<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=1>"
            "<title>Prompter</title><style>body{background:#111;color:#eee;font:20px monospace;padding:1em}"
            "pre{white-space:pre-wrap}</style>" + blocks)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
