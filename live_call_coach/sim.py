"""Offline simulator: a fake meeting page that plays a transcript as live captions.

Each utterance first appears as growing partial captions (what the page shows while someone
speaks), then as a final caption. The page also has other buttons (mute, leave, chat) so tests can
prove the reader never touches them.
"""

BUTTONS = ["Mute microphone", "Turn off camera", "Leave call", "Chat with everyone", "Turn on captions"]


class SimulatedMeetingPage:
    def __init__(self, events, partials=2):
        self._queue = []
        for ev in events:
            words = ev["text"].split()
            for i in range(1, partials + 1):
                cut = max(1, len(words) * i // (partials + 1))
                self._queue.append({"speaker": ev["speaker"], "text": " ".join(words[:cut]),
                                    "final": False, "t": ev["t"]})
            self._queue.append({"speaker": ev["speaker"], "text": ev["text"], "final": True, "t": ev["t"]})
        self.clicks = []
        self.captions_on = False

    def click(self, name):
        if name not in BUTTONS:
            raise ValueError("no such button: " + name)
        self.clicks.append(name)
        if name == "Turn on captions":
            self.captions_on = True

    def poll(self):
        if not self.captions_on or not self._queue:
            return None
        return self._queue.pop(0)

    @property
    def closed(self):
        return self.captions_on and not self._queue
