/* ============================================================================
   AURORA · app.js  —  UI wiring: chat, voice-to-voice loop, stage interaction,
   tool rail, inspector, timeline + transport, keyboard, and the boot scene.
   ========================================================================== */
(function () {
  "use strict";
  const Aurora = window.Aurora;
  const E = Aurora.Engine, IG = Aurora.ImageGen, V = Aurora.Voice, Director = Aurora.Director, U = Aurora.util;
  const $ = (id) => document.getElementById(id);

  /* refs */
  const stage = $("stage"), chat = $("chat"), composer = $("composerInput");
  const btnSend = $("btnSend"), btnMic = $("btnMic"), btnVoiceMode = $("btnVoiceMode");
  const statusEl = $("status"), statusText = $("statusText"), aiAvatar = $("aiAvatar");
  const inspector = $("inspector");
  const ruler = $("ruler"), trackRows = $("trackRows"), playhead = $("playhead"), tlTime = $("tlTime");
  const btnPlayTop = $("btnPlay"), tlPlay = $("tlPlay"), tlStop = $("tlStop");
  const stageHint = $("stageHint");

  let speakReplies = false;   // Voice toggle: Director speaks every reply
  let micActive = false;      // a voice turn is in progress / loop armed

  /* ---------- status + toast ---------- */
  function setStatus(state, text) { statusEl.dataset.state = state; statusText.textContent = text; }
  function toast(msg) {
    const wrap = $("toasts");
    const el = document.createElement("div");
    el.className = "toast"; el.innerHTML = `<span class="dot"></span>${msg}`;
    wrap.appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateY(6px)"; setTimeout(() => el.remove(), 300); }, 2600);
  }

  /* ---------- chat ---------- */
  function bubbleHTML(res) {
    let h = escapeHTML(res.reply);
    if (res.did && res.did.length) h += `<span class="did">✦ <b>Done:</b> ${escapeHTML(res.did.join(" · "))}</span>`;
    if (res.tip) h += `<span class="did tip">→ ${escapeHTML(res.tip)}</span>`;
    return h;
  }
  function addDirMsg(res) {
    const m = document.createElement("div");
    m.className = "msg dir";
    m.innerHTML = `<div class="av">A</div><div class="bubble">${bubbleHTML(res)}</div>`;
    chat.appendChild(m); scrollChat();
  }
  function addUserMsg(text) {
    const m = document.createElement("div");
    m.className = "msg user";
    m.innerHTML = `<div class="av">You</div><div class="bubble">${escapeHTML(text)}</div>`;
    chat.appendChild(m); scrollChat();
  }
  function showTyping() {
    const m = document.createElement("div");
    m.className = "msg dir"; m.id = "typingMsg";
    m.innerHTML = `<div class="av">A</div><div class="bubble"><span class="typing"><i></i><i></i><i></i></span></div>`;
    chat.appendChild(m); scrollChat();
  }
  function removeTyping() { const t = $("typingMsg"); if (t) t.remove(); }
  function scrollChat() { chat.scrollTop = chat.scrollHeight; }
  function escapeHTML(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

  /* ---------- run a command through the Director ---------- */
  async function runCommand(text, fromVoice = false) {
    if (!text || !text.trim()) return;
    addUserMsg(text);
    showTyping(); setStatus("thinking", "Thinking…"); aiAvatar.classList.add("busy");
    let res;
    try { res = await Director.handle(text); }
    catch (e) { res = { reply: "Hm, that one tripped me up — try rephrasing?" }; console.error(e); }
    removeTyping(); aiAvatar.classList.remove("busy");
    addDirMsg(res);
    if (res.play) E.play();
    updateTransport();

    const shouldSpeak = (fromVoice || speakReplies) && V.supportedTTS;
    if (shouldSpeak) {
      setStatus("speaking", "Speaking…");
      const speech = res.reply + (res.tip ? " " + res.tip : "");
      V.speak(speech, {
        onEnd: () => {
          if (speakReplies && fromVoice && micActive) startMic();   // voice-to-voice loop
          else { micActive = false; setStatus("ready", "Director ready"); }
        },
      });
    } else {
      setStatus("ready", "Director ready");
    }
  }

  /* ---------- voice (speech-to-text in) ---------- */
  function startMic() {
    if (!V.supportedSTT) { toast("Voice input needs Chrome, Edge or Safari"); return; }
    micActive = true; btnMic.classList.add("live"); setStatus("listening", "Listening…");
    composer.placeholder = "Listening… speak now";
    V.listen({
      onInterim: (txt) => { composer.value = txt; },
      onError: (e) => {
        btnMic.classList.remove("live"); micActive = false;
        composer.placeholder = defaultPlaceholder;
        const err = (e && (e.error || e.message)) || "error";
        if (err !== "no-speech" && err !== "aborted") toast("Mic: " + err + (err === "not-allowed" ? " — allow microphone access" : ""));
        setStatus("ready", "Director ready");
      },
      onEnd: (finalText) => {
        btnMic.classList.remove("live"); composer.placeholder = defaultPlaceholder;
        const txt = (finalText || composer.value || "").trim();
        composer.value = "";
        if (txt) { runCommand(txt, true); }
        else { micActive = false; setStatus("ready", "Director ready"); }
      },
    });
  }
  function stopMic() { micActive = false; V.stop(); V.cancelSpeak(); btnMic.classList.remove("live"); composer.placeholder = defaultPlaceholder; setStatus("ready", "Director ready"); }

  /* ---------- stage interaction (select / drag / edit) ---------- */
  let drag = null;
  stage.addEventListener("mousedown", (e) => {
    if (E.state.playing) return;
    const node = e.target.closest(".layer");
    if (!node) { E.select(null); inspector.classList.remove("show"); return; }
    const id = node.dataset.id; E.select(id); syncInspector();
    const l = E.getLayer(id); if (!l) return;
    E.snapshot();
    drag = { id, sx: e.clientX, sy: e.clientY, ox: l.x, oy: l.y };
    node.classList.add("dragging");
  });
  window.addEventListener("mousemove", (e) => {
    if (!drag) return;
    const l = E.getLayer(drag.id); if (!l) return;
    l.x = drag.ox + (e.clientX - drag.sx) / E.state.scale;
    l.y = drag.oy + (e.clientY - drag.sy) / E.state.scale;
    E.render(); syncInspector();
  });
  window.addEventListener("mouseup", () => {
    if (drag) { const n = E.els.get(drag.id); if (n) n.classList.remove("dragging"); drag = null; }
  });
  stage.addEventListener("dblclick", (e) => {
    const node = e.target.closest(".layer"); if (!node) return;
    const l = E.getLayer(node.dataset.id); if (!l || l.type !== "text") return;
    const v = window.prompt("Edit text:", l.text.value);
    if (v != null) { E.snapshot(); l.text.value = v; E.render(); }
  });

  /* ---------- inspector ---------- */
  function syncInspector() {
    const l = E.activeLayer();
    if (!l || E.state.playing) { inspector.classList.remove("show"); return; }
    if (!E.state.selectedId) { inspector.classList.remove("show"); return; }
    inspector.classList.add("show");
    $("inspName").textContent = l.name;
    $("inspType").textContent = l.type;
    setSlider("rOpacity", "vOpacity", Math.round(l.opacity * 100), "%");
    setSlider("rBright", "vBright", Math.round(l.filters.brightness * 100), "%");
    setSlider("rContrast", "vContrast", Math.round(l.filters.contrast * 100), "%");
    setSlider("rSat", "vSat", Math.round(l.filters.saturate * 100), "%");
    setSlider("rBlur", "vBlur", Math.round(l.filters.blur), "px");
  }
  function setSlider(rid, vid, val, unit) { $(rid).value = val; $(vid).textContent = val + unit; }
  function bindSlider(rid, vid, unit, apply) {
    const r = $(rid);
    r.addEventListener("pointerdown", () => { if (E.activeLayer()) E.snapshot(); });
    r.addEventListener("input", () => {
      const l = E.activeLayer(); if (!l) return;
      apply(l, +r.value); $(vid).textContent = r.value + unit; E.render();
    });
  }
  bindSlider("rOpacity", "vOpacity", "%", (l, v) => (l.opacity = v / 100));
  bindSlider("rBright", "vBright", "%", (l, v) => (l.filters.brightness = v / 100));
  bindSlider("rContrast", "vContrast", "%", (l, v) => (l.filters.contrast = v / 100));
  bindSlider("rSat", "vSat", "%", (l, v) => (l.filters.saturate = v / 100));
  bindSlider("rBlur", "vBlur", "px", (l, v) => (l.filters.blur = v));
  $("btnDuplicate").onclick = () => { const l = E.activeLayer(); if (l) E.duplicateLayer(l.id); };
  $("btnDelete").onclick = () => { const l = E.activeLayer(); if (l) { E.removeLayer(l.id); inspector.classList.remove("show"); } };

  /* ---------- tool rail ---------- */
  const railActions = {
    select: () => {},
    image: () => runCommand("generate a " + pickScene()),
    text: () => runCommand('add a title that says "Double-click to edit"'),
    shape: () => runCommand("add a shape"),
    effects: () => runCommand("make it cinematic"),
    animate: () => runCommand("add a slow ken-burns zoom"),
    video: () => runCommand("make an 8 second reel of a cinematic mountain journey"),
    clear: () => { if (confirm("Clear the entire canvas?")) runCommand("clear canvas"); },
  };
  function pickScene() { return ["golden-hour mountain background", "neon city skyline at night", "calm ocean coastline at dusk", "abstract aurora of violet and cyan"][(Math.random() * 4) | 0]; }
  document.querySelectorAll(".tool").forEach((el) => {
    el.addEventListener("click", () => {
      document.querySelectorAll(".tool").forEach((t) => t.classList.remove("active"));
      el.classList.add("active");
      const a = railActions[el.dataset.tool]; if (a) a();
      if (el.dataset.tool !== "select") setTimeout(() => { document.querySelector('.tool[data-tool="select"]').classList.add("active"); el.classList.remove("active"); }, 600);
    });
  });

  /* ---------- timeline ---------- */
  function renderTimeline() {
    const dur = E.doc.duration;
    ruler.innerHTML = "";
    for (let s = 0; s <= Math.round(dur); s++) {
      const tick = document.createElement("div"); tick.className = "tick"; tick.style.left = (s / dur * 100) + "%";
      if (s < dur) { const sp = document.createElement("span"); sp.textContent = s + "s"; tick.appendChild(sp); }
      ruler.appendChild(tick);
    }
    trackRows.innerHTML = "";
    E.doc.layers.forEach((l) => {
      const row = document.createElement("div"); row.className = "track-row";
      const clip = document.createElement("div"); clip.className = "clip";
      if (l.anim) {
        const start = l.anim.delay || 0;
        const len = l.anim.loop ? dur - start : Math.min(l.anim.dur, dur - start);
        clip.style.left = (start / dur * 100) + "%";
        clip.style.width = (Math.max(0.04, len / dur) * 100) + "%";
        clip.textContent = l.name + " · " + l.anim.type;
      } else {
        clip.style.left = "0%"; clip.style.width = "100%"; clip.style.opacity = ".5"; clip.textContent = l.name;
      }
      clip.onclick = () => { E.select(l.id); syncInspector(); };
      row.appendChild(clip); trackRows.appendChild(row);
    });
    updatePlayhead();
  }
  function updatePlayhead() {
    playhead.style.left = (E.state.time / E.doc.duration * 100) + "%";
    tlTime.textContent = E.state.time.toFixed(1) + "s / " + E.doc.duration.toFixed(1) + "s";
  }
  document.querySelector(".tracks").addEventListener("click", (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = U.clamp((e.clientX - rect.left) / rect.width, 0, 1);
    E.seek(ratio * E.doc.duration);
  });

  /* ---------- transport ---------- */
  function togglePlay() { if (E.state.playing) E.pause(); else E.play(); updateTransport(); }
  function updateTransport() {
    const playing = E.state.playing;
    btnPlayTop.innerHTML = playing
      ? `<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg><span>Pause</span>`
      : `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg><span>Play</span>`;
    tlPlay.innerHTML = playing
      ? `<svg viewBox="0 0 24 24" fill="currentColor" width="14"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>`
      : `<svg viewBox="0 0 24 24" fill="currentColor" width="14"><path d="M8 5v14l11-7z"/></svg>`;
  }
  btnPlayTop.onclick = togglePlay;
  tlPlay.onclick = togglePlay;
  tlStop.onclick = () => { E.stop(); updateTransport(); };

  /* ---------- top bar ---------- */
  $("btnUndo").onclick = () => { if (!E.undo()) toast("Nothing to undo"); };
  $("btnExport").onclick = () => {
    toast("Rendering preview… (demo) — plug a video provider here to write MP4");
    E.stop(); updateTransport(); E.play(); updateTransport();
  };

  /* ---------- composer ---------- */
  function send() { const v = composer.value.trim(); if (!v) return; composer.value = ""; autoSize(); runCommand(v, false); }
  btnSend.onclick = send;
  composer.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
  function autoSize() { composer.style.height = "auto"; composer.style.height = Math.min(composer.scrollHeight, 110) + "px"; }
  composer.addEventListener("input", autoSize);
  const defaultPlaceholder = composer.placeholder;

  btnMic.onclick = () => { if (micActive) stopMic(); else startMic(); };
  if (!V.supportedSTT) btnMic.title = "Voice input needs Chrome/Edge/Safari — you can type instead";

  btnVoiceMode.onclick = () => {
    if (!V.supportedTTS) { toast("Speech output not supported in this browser"); return; }
    speakReplies = !speakReplies;
    btnVoiceMode.classList.toggle("primary", speakReplies);
    $("voiceModeLabel").textContent = speakReplies ? "Voice on" : "Voice";
    toast(speakReplies ? "Voice replies on — I'll speak, and after a mic command I'll keep the conversation going" : "Voice replies off");
  };

  /* ---------- quick chips ---------- */
  const CHIPS = [
    "Generate a neon city at night", 'Add a title that says "Kusha Spices"',
    "Make it cinematic", "Add a slow ken-burns zoom",
    "Make an 8s reel of a mountain journey", "What do you think?",
  ];
  (function renderChips() {
    const wrap = $("chips");
    CHIPS.forEach((c) => {
      const el = document.createElement("div"); el.className = "chip"; el.textContent = c;
      el.onclick = () => runCommand(c, false);
      wrap.appendChild(el);
    });
  })();

  /* ---------- keyboard ---------- */
  window.addEventListener("keydown", (e) => {
    const typing = /INPUT|TEXTAREA/.test(document.activeElement.tagName);
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); if (!E.undo()) toast("Nothing to undo"); return; }
    if (typing) return;
    if (e.code === "Space") { e.preventDefault(); togglePlay(); }
    if (e.key === "Delete" || e.key === "Backspace") { const l = E.activeLayer(); if (l && E.state.selectedId) { E.removeLayer(l.id); inspector.classList.remove("show"); } }
  });

  /* ---------- engine change hook ---------- */
  let lastPlaying = null;
  E.onChange(() => {
    if (E.state.playing) { updatePlayhead(); }
    else { renderTimeline(); syncInspector(); }
    stageHint.style.display = E.doc.layers.length ? "none" : "grid";
    if (E.state.playing !== lastPlaying) { updateTransport(); lastPlaying = E.state.playing; }
  });

  /* ---------- boot: a cinematic demo scene ---------- */
  async function boot() {
    E.init(stage);                       // bind engine to the stage, create the doc
    setStatus("thinking", "Setting the scene…"); aiAvatar.classList.add("busy");
    E.fitStage();
    const { src } = await IG.generate("an abstract aurora of violet, cyan and magenta light", { width: E.doc.width, height: E.doc.height });
    const bg = Aurora.makeLayer("image", { name: "Background", x: 0, y: 0, w: E.doc.width, h: E.doc.height, src, anim: { type: "zoomIn", dur: 6, delay: 0, loop: false } });
    const title = Aurora.makeLayer("text", {
      name: "Title", x: E.doc.width * 0.1, y: E.doc.height * 0.34, w: E.doc.width * 0.8, h: 170,
      text: { value: "AURORA", size: 124, weight: 800, color: "#ffffff", font: "Inter", align: "center", italic: false, shadow: true, lineHeight: 1, letter: 8 },
      anim: { type: "riseIn", dur: 1.4, delay: 0.5, loop: false },
    });
    const sub = Aurora.makeLayer("text", {
      name: "Caption", x: E.doc.width * 0.1, y: E.doc.height * 0.56, w: E.doc.width * 0.8, h: 60,
      text: { value: "AI CREATIVE STUDIO", size: 30, weight: 500, color: "#e3eaff", font: "Inter", align: "center", italic: false, shadow: true, lineHeight: 1, letter: 10 },
      anim: { type: "fadeIn", dur: 1.6, delay: 1.0, loop: false },
    });
    E.doc.layers.push(bg, title, sub);
    E.doc.grade.warmth = 0.05; E.doc.grade.vignette = 0.3; E.doc.grade.bloom = 0.18;
    E.doc.duration = 6;
    E.render(); E._changed();
    aiAvatar.classList.remove("busy"); setStatus("ready", "Director ready");
    addDirMsg(Director.greeting());
    if (!V.supportedSTT) addDirMsg({ reply: "Heads up: this browser doesn't expose speech-to-text, so the mic is disabled — but everything works by typing. Chrome, Edge or Safari unlock voice-to-voice." });
  }

  // kick off once fonts/layout settle
  requestAnimationFrame(() => requestAnimationFrame(boot));
})();
