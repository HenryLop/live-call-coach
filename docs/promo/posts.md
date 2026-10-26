# Post copy

Ready to paste. `<REPO_URL>` is this repository's address. Videos are in this folder: attach the 16:9 file to LinkedIn, X and Dev.to, and the vertical file to YouTube Shorts.

## Interview mode

Video: `interview-16x9.mp4` (feed), `interview-9x16.mp4` (Shorts). Poster image: `../social-preview.png`.

### LinkedIn Page

A job interview moves faster than memory.

This is a small coach that listens to the interviewer and shows a card while the question is still fresh. The quick card lands about 1.5 seconds after the question ends: an opening line, three points to hit, and a flag when the question is a hard one. Hard questions also get a deeper card that cites your own notes. Any other question gets that card when you press a key.

When a new question starts before a card is ready, the old card is dropped instead of showing up late.

It runs offline against a stub model, and you can plug in a local one. Python, standard library only, MIT licensed. The repo has a UI demo that opens with a double-click.

Code and demo: <REPO_URL>
Write-up: https://made-by-asking.pages.dev/showcase/interview-copilot/

### X

A job interview moves faster than memory. This coach listens to the interviewer and shows a card about 1.5 s after each question: an opening line, three points, a flag for hard ones. A new question drops the old card instead of showing it late. Python, offline, MIT. <REPO_URL>

### YouTube Shorts

Title: A coach that shows a card 1.5 seconds after the interviewer's question #Shorts

Description:
It listens to the interviewer and shows an opening line, three points and a hard-question flag. Hard questions get a deeper card that cites your own notes; press E to get one on any other question. A card that is not ready when the next question starts is dropped.

Open source, Python, runs offline: <REPO_URL>

### Dev.to intro

In an interview, the right example is somewhere in your head and it surfaces five minutes late. `live-call-coach` is a small package that listens to the other side of a call and shows tiered hints while the question is still fresh.

The quick tier answers in about 1.5 seconds with an opening line, three key points and a hard-question flag. The deep tier is grounded in your own notes and cites them. When a new question starts before a card is ready, the stale card is dropped. The whole pipeline runs on a simulated clock, so replays are instant and the tests are deterministic.

There is a UI demo in `ui/` that needs no server: open `index.html` and watch a scripted interview play through. The demo and the tests use an offline stub, so nothing here calls a paid API.

Repository: <REPO_URL>

## Meeting mode

Video: `meeting-16x9.mp4` (feed), `meeting-9x16.mp4` (Shorts). Poster image: `../social-preview.png`.

### LinkedIn Page

In a work call, the answer is usually in a ticket, a doc or an email, and there is no time to look.

This helper follows the call and, about two seconds after a question, shows a line you could say and the facts behind it, each with its source. It keeps a ledger of commitments: who promised what, and by when. A card that is not ready when the next question starts is dropped, so you never read an answer to the wrong question.

The reader that watches the call is read-only. Its only click is turning on captions, and a test checks the source for typing, key presses and form filling.

Python, standard library only, MIT licensed. The repo has a UI demo that opens with a double-click.

Code and demo: <REPO_URL>
Write-up: https://made-by-asking.pages.dev/showcase/meeting-helper/

### X

In a work call the answer is usually in a ticket or a doc. This helper shows a line to say and the facts, each with its source, about 2 s after a question. It keeps a ledger of who promised what by when. Its reader can only turn on captions. Python, offline, MIT. <REPO_URL>

### YouTube Shorts

Title: A call helper that shows what to say and where the fact came from #Shorts

Description:
About two seconds after a question it shows a line to say and the facts behind it, each with its source. A ledger tracks who promised what, and by when. The reader is read-only: its one click is turning on captions.

Open source, Python, runs offline: <REPO_URL>

### Dev.to intro

Work calls ask for facts you own but cannot look up in the moment. `live-call-coach` has a meeting mode for that: for each question it builds a card with a line to say and the facts behind it, with their sources, and it keeps a running ledger of commitments (who, what, when).

Two details carry most of the design. A card that is still being built when the next question starts is dropped rather than shown late. And the reader that follows the call is read-only: it has an allow-list with one entry, turning on captions, and a test scans the source for anything that types or sends.

The UI demo in `ui/` replays an invented call with no server, so you can see the cards arrive, a stale card leave and the ledger fill. The code runs offline against a stub model.

Repository: <REPO_URL>
