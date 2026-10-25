"""A tiny retrieval layer over a JSON list of {id, text, source, tags}."""
import json

from .text import overlap


class Knowledge:
    def __init__(self, items):
        self.items = items

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def search(self, query, k=3):
        scored = [(overlap(query, i["text"] + " " + " ".join(i.get("tags", []))), i) for i in self.items]
        return [i for s, i in sorted(scored, key=lambda x: -x[0]) if s][:k]
