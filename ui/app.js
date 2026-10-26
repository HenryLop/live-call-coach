/* live-call-coach UI demo. A scripted, deterministic replay of data/*.jsonl: no network, no backend.
   The clock below is simulated time. Gaps between lines are compressed; card latencies are not. */
(function () {
  "use strict";
  var D = window.COACH_DATA;
  var WPS = 4.6;        // words per second while a line streams in
  var SCALE = 0.4;      // transcript gaps are shortened to 40% so a call fits in under a minute
  var GAP = 0.35;       // pause between lines
  var LEAD = 0.9;       // silence before the first line
  var DROP_HOLD = 1.7;  // seconds a dropped card stays visible before it leaves
  var TAIL = parseFloat(new URLSearchParams(location.search).get("tail")) || 2.5;  // hold after the last card

  var qs = new URLSearchParams(location.search);
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (id) { return document.getElementById(id); };
  var el = {
    app: $("app"), main: $("main"), tx: $("tx"), stack: $("stack"), side: $("side"), status: $("status"),
    statusTxt: $("status-txt"), play: $("play"), playTxt: $("play-txt"), playIco: $("play-ico"),
    restart: $("restart"), speed: $("speed"), speedTxt: $("speed-txt"), clock: $("clock"), prog: $("prog"),
    esc: $("esc"), hint: $("hint"), cardfoot: $("cardfoot"), cardsNote: $("cards-note")
  };
  var ICON_PLAY = "M4 2l10 6-10 6z";
  var ICON_PAUSE = "M3 2h4v12H3zM9 2h4v12H9z";
  var ICON_REPLAY = "M8 2a6 6 0 1 0 5.7 4.2l-1.9.6A4 4 0 1 1 8 4v2.5L12 3.2 8 0z";

  function h(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt != null) n.textContent = txt;
    return n;
  }
  function fmt(s) { s = Math.max(0, Math.floor(s)); return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2); }

  var view = "interview", S = null, playing = true, speed = 1, lastTs = 0, plan = null;

  /* ---------- plan: when each line starts and ends ---------- */
  function buildPlan(v) {
    var evs = D[v].events, prevEnd = LEAD - GAP, items = [], end = 0, extra = 0;
    evs.forEach(function (e, i) {
      if (e.key) {
        items.push({ kind: "key", at: Math.max(e.t * SCALE, prevEnd), key: e.key });
        return;
      }
      var words = e.text.split(/\s+/);
      var start = Math.max(e.t * SCALE, prevEnd + GAP);
      var stop = start + words.length / WPS;
      prevEnd = stop;
      items.push({ kind: "utt", e: e, words: words, start: start, end: stop, idx: i });
      end = Math.max(end, stop);
      if (e.q) {
        var lat = v === "meeting" ? e.q.latency : (e.q.autoDeep ? e.q.deep.latency : e.q.quick.latency);
        extra = Math.max(extra, stop + lat);
      }
    });
    return { items: items, total: Math.max(end, extra) + TAIL };
  }

  /* ---------- simulated clock ---------- */
  function insertAct(a) {
    a.seq = S.seq++;
    var i = S.acts.length;
    while (i > S.ai && (S.acts[i - 1].at > a.at)) i--;
    S.acts.splice(i, 0, a);
  }
  function at(t, fn) { insertAct({ at: t, run: fn }); }

  function reset() {
    el.tx.innerHTML = ""; el.stack.innerHTML = ""; el.hint.textContent = "";
    plan = buildPlan(view);
    S = { now: 0, acts: [], ai: 0, seq: 0, slots: [], cur: null, stream: null, pend: [], ledger: [],
          ended: false, notes: {}, reader: null };
    buildSide();
    var empty = h("p", "empty", view === "meeting"
      ? "The first card appears after the first question."
      : "The first card appears after the first question.");
    empty.id = "empty"; el.stack.appendChild(empty);
    setStatus("live", view === "meeting" ? "Reading captions" : "Listening to the interviewer");
    el.status.className = "status";
    plan.items.forEach(function (it) {
      if (it.kind === "utt") {
        at(it.start, function () { startUtt(it); });
        at(it.end, function () { endUtt(it); });
      } else {
        at(it.at, function () { keyLine(it.key); });
      }
    });
    if (view === "meeting") {
      at(0.4, function () { reader("click"); });
      at(1.2, function () { reader("on"); });
    }
    at(plan.total, function () { finish(); });
    updateUi();
  }

  function advance(dt) {
    var target = S.now + dt;
    while (S.ai < S.acts.length && S.acts[S.ai].at <= target) {
      var a = S.acts[S.ai++];
      S.now = a.at;
      a.run();
    }
    S.now = target;
    frame();
  }

  function seek(t) {
    document.documentElement.classList.add("noanim");
    reset();
    advance(t);
    document.documentElement.classList.remove("noanim");
    updateUi();
  }

  /* ---------- transcript ---------- */
  function startUtt(it) {
    var e = it.e, me = e.speaker === "me";
    var ln = h("div", "ln cur " + (me ? "me" : "other"));
    ln.appendChild(h("span", "sp", me ? "You" : e.speaker));
    var p = h("p");
    it.spans = it.words.map(function (w, i) {
      var s = h("span", "w", w + (i < it.words.length - 1 ? " " : ""));
      p.appendChild(s);
      return s;
    });
    ln.appendChild(p);
    el.tx.appendChild(ln);
    it.ln = ln; it.shown = 0;
    S.stream = it;
    if (reduce) showWords(it, it.words.length);
    if (e.q && !me) newQuestion(it);
    el.tx.scrollTop = el.tx.scrollHeight;
  }
  function showWords(it, n) {
    for (; it.shown < n && it.shown < it.spans.length; it.shown++) it.spans[it.shown].classList.add("on");
  }
  function endUtt(it) {
    showWords(it, it.words.length);
    it.ln.classList.remove("cur");
    if (S.stream === it) S.stream = null;
    var e = it.e;
    if (e.commitments) e.commitments.forEach(addCommitment);
    if (e.confirms) e.confirms.forEach(confirmCommitment);
    if (e.q && e.speaker !== "me") questionEnded(it);
    el.tx.scrollTop = el.tx.scrollHeight;
  }
  function keyLine(key) {
    if (key !== "escalate") return;
    var ln = h("div", "ln key");
    ln.appendChild(h("kbd", null, "E"));
    ln.appendChild(h("span", null, "You asked for depth"));
    el.tx.appendChild(ln);
    el.tx.scrollTop = el.tx.scrollHeight;
    escalate();
  }

  /* ---------- question slots and cards ---------- */
  function collapse(node, done) {
    node.classList.remove("in");
    setTimeout(function () { if (node.parentNode) node.parentNode.removeChild(node); if (done) done(); }, document.documentElement.classList.contains("noanim") || reduce ? 0 : 460);
  }
  function reveal(node) {
    if (document.documentElement.classList.contains("noanim") || reduce) { node.classList.add("in"); return; }
    requestAnimationFrame(function () { requestAnimationFrame(function () { node.classList.add("in"); }); });
  }
  function wrap(cls) {
    var n = h("div", cls), inner = h("div", "inner");
    n.appendChild(inner);
    return { node: n, inner: inner };
  }

  function newQuestion(it) {
    var prev = S.cur;
    var empty = $("empty"); if (empty) empty.parentNode.removeChild(empty);
    if (prev) {
      prev.node.classList.add("old");
      // anything still being built for the previous question is stale now
      prev.blocks.forEach(function (b) { if (b.state === "pending") dropBlock(b, prev); });
      S.slots.forEach(function (s) {
        if (s !== prev && !s.gone) { s.gone = true; collapse(s.node); }
      });
    }
    S.notes.hit = null;
    clearHits();
    var n = S.slots.length + 1;
    var w = wrap("slot");
    var head = h("div", "qh");
    head.appendChild(h("span", "qn", "Q" + n));
    var qt = h("p", "qt wait", "Question coming in");
    head.appendChild(qt);
    w.inner.appendChild(head);
    var slot = { node: w.node, inner: w.inner, qt: qt, it: it, q: it.e.q, blocks: [], n: n, deep: null, quick: null, ended: false };
    S.slots.push(slot); S.cur = slot;
    el.stack.insertBefore(w.node, el.stack.firstChild);
    reveal(w.node);
    updateUi();
  }

  function questionEnded(it) {
    var slot = S.cur; if (!slot || slot.it !== it) return;
    slot.ended = true;
    slot.qt.textContent = it.e.text; slot.qt.className = "qt";
    if (view === "meeting") {
      var b = pendingBlock(slot, "meet", "Meeting card", slot.q.latency);
      at(S.now + slot.q.latency, function () { meetingCard(slot, b); });
    } else {
      var qb = pendingBlock(slot, "quick", "Quick card", slot.q.quick.latency);
      slot.quick = qb;
      at(S.now + slot.q.quick.latency, function () { quickCard(slot, qb); });
      if (slot.q.autoDeep) {
        var db = pendingBlock(slot, "deep", "Deep card", slot.q.deep.latency, "A hard question gets this on its own.");
        slot.deep = db;
        at(S.now + slot.q.deep.latency, function () { deepCard(slot, db); });
      }
    }
    updateUi();
  }

  function pendingBlock(slot, kind, label, lat, sub) {
    var w = wrap("blk " + kind);
    var pend = h("div", "pend");
    var row = h("div", "row");
    row.appendChild(h("span", null, label));
    var cd = h("span", "cd", lat.toFixed(1) + " s");
    row.appendChild(cd);
    pend.appendChild(row);
    var msg = h("p", null, sub || "Building from your notes");
    if (view === "meeting") msg.textContent = "Looking up the facts";
    pend.appendChild(msg);
    var bar = h("div", "bar2"); var fill = h("i"); bar.appendChild(fill); pend.appendChild(bar);
    w.inner.appendChild(pend);
    var b = { node: w.node, inner: w.inner, state: "pending", t0: S.now, lat: lat, cd: cd, fill: fill, msg: msg, pend: pend, kind: kind };
    slot.blocks.push(b); S.pend.push(b);
    slot.inner.appendChild(w.node);
    reveal(w.node);
    return b;
  }
  function settle(b, cls) {
    b.state = cls;
    S.pend = S.pend.filter(function (x) { return x !== b; });
  }
  function fill(b, content) {
    b.inner.innerHTML = "";
    b.inner.appendChild(content);
    b.node.classList.add("arrive");
  }

  function dropBlock(b, slot) {
    settle(b, "dropped");
    b.node.classList.add("dropped");
    b.cd.textContent = "dropped";
    b.msg.textContent = "A new question started first, so this card never shows.";
    slot.node.classList.add("dropping");
    at(S.now + DROP_HOLD, function () {
      collapse(b.node);
      var live = slot.blocks.some(function (x) { return x.state === "ready"; });
      if (!live && !slot.gone) { slot.gone = true; collapse(slot.node); }
      slot.node.classList.remove("dropping");
    });
  }

  function card() { return h("div", "card"); }

  function quickCard(slot, b) {
    if (b.state !== "pending") return;
    settle(b, "ready");
    var q = slot.q, c = card();
    var bh = h("div", "bh");
    bh.appendChild(h("span", null, "Quick card"));
    bh.appendChild(h("span", "lat", q.quick.latency.toFixed(1) + " s"));
    if (q.hard) bh.appendChild(h("span", "flag", "Hard question"));
    c.appendChild(bh);
    c.appendChild(h("p", "opening", q.quick.opening));
    var ul = h("ul", "pts");
    q.quick.points.forEach(function (id, i) {
      var li = h("li"); li.appendChild(h("b", null, String(i + 1))); li.appendChild(h("span", null, noteGist(id)));
      ul.appendChild(li);
    });
    c.appendChild(ul);
    if (q.hard && q.autoDeep) c.appendChild(h("p", "hardnote", "Flagged hard: the deep card is already on its way."));
    fill(b, c);
    if (!q.hard && slot === S.cur) say("Not flagged hard, so no deep card unless you ask. Press E.");
    updateUi();
  }

  function deepCard(slot, b) {
    if (b.state !== "pending") return;
    settle(b, "ready");
    var q = slot.q, c = card();
    var bh = h("div", "bh");
    bh.appendChild(h("span", null, "Deep card"));
    bh.appendChild(h("span", "lat", (b.lat).toFixed(1) + " s, from your notes"));
    c.appendChild(bh);
    c.appendChild(h("p", "answer", q.deep.answer));
    var cites = h("div", "cites");
    q.deep.cites.forEach(function (id) {
      var r = h("div", "cite");
      r.appendChild(h("code", null, id));
      r.appendChild(h("span", null, noteText(id)));
      cites.appendChild(r);
    });
    c.appendChild(cites);
    fill(b, c);
    slot.node.classList.add("deepin");
    markHits(q.deep.cites);
    updateUi();
  }

  function meetingCard(slot, b) {
    if (b.state !== "pending") return;
    settle(b, "ready");
    var q = slot.q, c = card();
    var bh = h("div", "bh");
    bh.appendChild(h("span", null, "Meeting card"));
    bh.appendChild(h("span", "lat", q.latency.toFixed(1) + " s"));
    c.appendChild(bh);
    var f2 = h("div", "fld"); f2.appendChild(h("label", null, "Say")); f2.appendChild(h("p", "say", q.say)); c.appendChild(f2);
    var f3 = h("div", "fld"); f3.appendChild(h("label", null, "Facts"));
    var ul = h("ul", "facts");
    q.facts.forEach(function (f) {
      var li = h("li", null, f.text + " ");
      li.appendChild(h("span", "src", f.source));
      ul.appendChild(li);
    });
    f3.appendChild(ul); c.appendChild(f3);
    c.appendChild(h("p", "ctx", S.ledger.length + (S.ledger.length === 1 ? " commitment" : " commitments") + " so far"));
    fill(b, c);
    updateUi();
  }

  /* ---------- escalate (interview) ---------- */
  function say(msg, flash) {
    el.hint.textContent = msg;
    el.hint.className = "hint" + (flash ? " flash" : "");
  }
  function escalate() {
    if (view !== "interview") return;
    var slot = S.cur;
    if (!slot || !slot.ended) { say("Wait for the question to finish."); return; }
    if (slot.deep) { say(slot.deep.state === "pending" ? "Depth is already on its way." : "This question already has a deep card.", true); return; }
    var db = pendingBlock(slot, "deep", "Deep card", slot.q.deep.latency, "Asked for with the E key.");
    slot.deep = db;
    at(S.now + slot.q.deep.latency, function () { deepCard(slot, db); });
    say("");
    updateUi();
  }

  /* ---------- side panels ---------- */
  var noteMap = {};
  function noteGist(id) { return noteMap[id] ? noteMap[id].gist : id; }
  function noteText(id) { return noteMap[id] ? noteMap[id].text : id; }
  function clearHits() {
    var lis = el.side.querySelectorAll(".notes li.hit");
    for (var i = 0; i < lis.length; i++) lis[i].classList.remove("hit");
  }
  function markHits(ids) {
    clearHits();
    ids.forEach(function (id) {
      var li = el.side.querySelector('.notes li[data-id="' + id + '"]');
      if (li) { li.classList.remove("hit"); void li.offsetWidth; li.classList.add("hit"); }
    });
  }

  function buildSide() {
    el.side.innerHTML = "";
    if (view === "interview") {
      noteMap = {};
      D.interview.notes.forEach(function (n) { noteMap[n.id] = n; });
      var h2 = h("h2"); h2.appendChild(h("span", null, "Your notes")); h2.appendChild(h("span", "note", "profile.json"));
      el.side.appendChild(h2);
      var ul = h("ul", "notes");
      D.interview.notes.forEach(function (n) {
        var li = h("li"); li.dataset.id = n.id;
        li.appendChild(h("code", null, n.id)); li.appendChild(h("span", null, n.gist));
        ul.appendChild(li);
      });
      el.side.appendChild(ul);
      el.side.appendChild(h("div", "sidenote", "Notes a deep card cites light up here."));
    } else {
      var h2m = h("h2"); h2m.appendChild(h("span", null, "Reader")); h2m.appendChild(h("span", "note", "read-only"));
      el.side.appendChild(h2m);
      var rd = h("div", "reader"); rd.id = "reader";
      var pill = h("div", "pill"); pill.appendChild(h("i", "dot")); pill.appendChild(h("span", null, "Captions only, read-only"));
      rd.appendChild(pill);
      var rows = h("div", "rrows");
      var r1 = h("div"); r1.appendChild(h("b", null, "Captions")); r1.appendChild(h("span", "ok pending", "Off"));
      var r2 = h("div"); r2.appendChild(h("b", null, "Only click")); r2.appendChild(h("span", null, "Turn on captions"));
      var r3 = h("div"); r3.appendChild(h("b", null, "Never")); r3.appendChild(h("span", null, "Mute, leave, chat, typing"));
      rows.appendChild(r1); rows.appendChild(r2); rows.appendChild(r3);
      rd.appendChild(rows); el.side.appendChild(rd);
      S.reader = { box: rd, cap: r1.lastChild, only: r2.lastChild };
      var lg = h("div", "ledger");
      var lh = h("div", "lh"); lh.appendChild(h("span", null, "Commitments")); var cnt = h("span", null, "0"); lh.appendChild(cnt);
      lg.appendChild(lh);
      var lw = h("div", "lwrap");
      var none = h("div", "none", "Nothing promised yet."); lw.appendChild(none);
      var tb = h("table"); tb.hidden = true;
      var thead = h("thead"), tr = h("tr");
      ["Who", "What", "When"].forEach(function (t) { tr.appendChild(h("th", null, t)); });
      thead.appendChild(tr); tb.appendChild(thead);
      var tbody = h("tbody"); tb.appendChild(tbody); lw.appendChild(tb); lg.appendChild(lw);
      el.side.appendChild(lg);
      S.ledgerUi = { cnt: cnt, none: none, tb: tb, tbody: tbody, wrap: lw };
    }
  }

  function reader(step) {
    var r = S.reader; if (!r) return;
    if (step === "click") { r.only.textContent = "Turn on captions: clicked"; r.only.className = "ok"; }
    if (step === "on") {
      r.cap.textContent = "On, reading"; r.cap.className = "ok";
      r.box.classList.add("on");
    }
  }

  function addCommitment(c) {
    var L = S.ledgerUi; if (!L) return;
    c = { who: c.who, what: c.what, when: c.when, asked_by: c.asked_by };  // the data stays untouched across replays
    S.ledger.push(c);
    L.none.hidden = true; L.tb.hidden = false;
    var tr = h("tr", "new");
    c.tr = tr;
    var who = h("td", "who", c.who === "me" ? "You" : c.who);
    if (c.asked_by) who.appendChild(h("small", null, "asked by " + c.asked_by));
    tr.appendChild(who);
    tr.appendChild(h("td", null, c.what));
    c.whenTd = h("td", "when", c.when ? c.when.replace(/^by /, "") : "no date");
    tr.appendChild(c.whenTd);
    L.tbody.appendChild(tr);
    L.cnt.textContent = String(S.ledger.length);
    L.wrap.scrollTop = L.wrap.scrollHeight;
  }

  /* a promise that answers a request already in the ledger updates that row */
  function confirmCommitment(u) {
    for (var i = 0; i < S.ledger.length; i++) {
      var c = S.ledger[i];
      if (c.who === u.who && c.asked_by === u.asked_by && !c.confirmed) {
        c.confirmed = true;
        if (u.when) c.when = u.when;
        c.whenTd.textContent = c.when ? c.when.replace(/^by /, "") : "no date";
        c.whenTd.appendChild(h("small", null, "confirmed"));
        c.tr.classList.remove("new"); void c.tr.offsetWidth; c.tr.classList.add("upd");
        return;
      }
    }
  }

  /* ---------- per-frame work ---------- */
  function frame() {
    var it = S.stream;
    if (it && !reduce) showWords(it, Math.floor((S.now - it.start) * WPS) + 1);
    if (it) el.tx.scrollTop = el.tx.scrollHeight;
    S.pend.forEach(function (b) {
      var left = Math.max(0, b.lat - (S.now - b.t0));
      b.cd.textContent = left.toFixed(1) + " s";
      b.fill.style.transform = "scaleX(" + Math.min(1, (S.now - b.t0) / b.lat).toFixed(3) + ")";
    });
    el.prog.style.transform = "scaleX(" + Math.min(1, S.now / plan.total).toFixed(4) + ")";
    el.clock.textContent = fmt(S.now) + " / " + fmt(plan.total);
  }

  function finish() {
    S.ended = true; playing = false;
    setStatus("", "Call ended");
    updateUi();
  }
  function setStatus(cls, txt) {
    el.status.className = "status" + (cls ? " " + cls : "");
    el.statusTxt.textContent = txt;
  }

  /* ---------- controls ---------- */
  function updateUi() {
    var label = S.ended ? "Replay" : (playing ? "Pause" : "Play");
    el.playTxt.textContent = label;
    el.play.setAttribute("aria-label", label);
    el.playIco.setAttribute("d", S.ended ? ICON_REPLAY : (playing ? ICON_PAUSE : ICON_PLAY));
    el.speedTxt.textContent = speed + "x";
    el.speed.setAttribute("aria-label", "Playback speed " + speed + "x");
    if (!S.ended) el.status.className = "status" + (playing ? " live" : "");
    var s = S.cur;
    var can = view === "interview" && s && s.ended && !s.deep;
    el.cardfoot.style.display = view === "interview" ? "" : "none";
    el.esc.disabled = !can;
    el.cardsNote.textContent = view === "interview"
      ? "Opening line, key points, then your notes" : "What to say, with its source";
  }
  function togglePlay() {
    if (S.ended) { restart(); return; }
    playing = !playing; updateUi();
  }
  function restart() {
    reset(); playing = true; updateUi();
  }
  function toggleSpeed() { speed = speed === 1 ? 2 : 1; updateUi(); }

  function setView(v, focus) {
    view = v;
    el.main.className = "view-" + v;
    ["interview", "meeting"].forEach(function (k) {
      var t = $("tab-" + k);
      t.setAttribute("aria-selected", String(k === v));
      t.tabIndex = k === v ? 0 : -1;
      if (focus && k === v) t.focus();
    });
    try { history.replaceState(null, "", "#" + v); } catch (e) { /* file: pages may refuse */ }
    restart();
  }

  el.play.addEventListener("click", togglePlay);
  el.restart.addEventListener("click", restart);
  el.speed.addEventListener("click", toggleSpeed);
  el.esc.addEventListener("click", function () {
    var ln = h("div", "ln key");
    ln.appendChild(h("kbd", null, "E")); ln.appendChild(h("span", null, "You asked for depth"));
    if (view === "interview" && S.cur && S.cur.ended && !S.cur.deep) { el.tx.appendChild(ln); el.tx.scrollTop = el.tx.scrollHeight; }
    escalate();
  });
  document.querySelectorAll(".tabs button").forEach(function (b) {
    b.addEventListener("click", function () { if (b.dataset.view !== view) setView(b.dataset.view); });
    b.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        setView(view === "interview" ? "meeting" : "interview", true);
      }
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var k = e.key.toLowerCase();
    var onBtn = e.target.closest && e.target.closest("button,[role=tab]");
    if (e.key === " ") { if (onBtn) return; e.preventDefault(); togglePlay(); }
    else if (k === "r") restart();
    else if (k === "s") toggleSpeed();
    else if (k === "e") {
      if (view === "interview" && S.cur && S.cur.ended && !S.cur.deep) el.esc.click(); else escalate();
    }
  });

  var last = 0;
  function loop(ts) {
    var running = (playing && !S.ended) || (S.ended && S.pend.length);
    if (running && last) advance(Math.min((ts - last) / 1000, 0.1) * speed);
    last = ts;
    requestAnimationFrame(loop);
  }

  /* hooks for tests and recordings */
  window.__demo = {
    seek: function (t) { playing = false; seek(t); updateUi(); },
    play: function () { playing = true; updateUi(); },
    pause: function () { playing = false; updateUi(); },
    setView: function (v) { setView(v); },
    state: function () { return { view: view, now: S.now, total: plan.total, ended: S.ended }; },
    pressE: function () { el.esc.click(); },
    escalateAt: function (t) { at(t, function () { keyLine("escalate"); }); }
  };

  /* start */
  var want = qs.get("view") || location.hash.replace("#", "");
  if (want === "meeting") view = "meeting";
  el.main.className = "view-" + view;
  ["interview", "meeting"].forEach(function (k) {
    $("tab-" + k).setAttribute("aria-selected", String(k === view));
    $("tab-" + k).tabIndex = k === view ? 0 : -1;
  });
  speed = qs.get("speed") === "2" ? 2 : 1;
  reset();
  playing = !reduce && qs.get("paused") !== "1";
  if (qs.get("esc")) window.__demo.escalateAt(parseFloat(qs.get("esc")));
  if (qs.get("t")) { playing = false; seek(parseFloat(qs.get("t"))); }
  updateUi();
  requestAnimationFrame(loop);
})();
