/* ============================================================================
   AURORA · voice.js  —  Voice PROVIDER (real, browser-native, no keys)
   ----------------------------------------------------------------------------
   Speech-to-text via the Web Speech API (SpeechRecognition) and text-to-speech
   via SpeechSynthesis. This gives genuine *voice-to-voice* with zero setup in
   Chrome/Edge/Safari. To swap in a cloud STT/TTS later, replace the bodies of
   `listen()` and `speak()` — the app only depends on these signatures.
   ========================================================================== */
(function () {
  "use strict";
  const Aurora = (window.Aurora = window.Aurora || {});

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  const synth = window.speechSynthesis || null;

  let recog = null;
  let chosenVoice = null;

  function loadVoice() {
    if (!synth) return;
    const voices = synth.getVoices();
    if (!voices.length) return;
    // prefer a warm, natural English voice
    const wanted = ["Samantha", "Google US English", "Microsoft Aria", "Microsoft Jenny", "Karen", "Serena", "Google UK English Female"];
    for (const name of wanted) {
      const v = voices.find((x) => x.name === name);
      if (v) { chosenVoice = v; return; }
    }
    chosenVoice = voices.find((v) => /en[-_]/i.test(v.lang)) || voices[0];
  }
  if (synth) {
    loadVoice();
    synth.onvoiceschanged = loadVoice;
  }

  Aurora.Voice = {
    supportedSTT: !!SR,
    supportedTTS: !!synth,

    /** Listen for a single spoken command.
     *  cbs: { onInterim(text), onFinal(text), onEnd(), onError(e) } */
    listen(cbs = {}) {
      if (!SR) { cbs.onError && cbs.onError(new Error("speech-recognition-unsupported")); return false; }
      this.stop();
      recog = new SR();
      recog.lang = "en-US";
      recog.interimResults = true;
      recog.continuous = false;
      recog.maxAlternatives = 1;

      let finalText = "";
      recog.onresult = (e) => {
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i];
          if (r.isFinal) finalText += r[0].transcript;
          else interim += r[0].transcript;
        }
        if (interim) cbs.onInterim && cbs.onInterim(interim);
        if (finalText) cbs.onFinal && cbs.onFinal(finalText.trim());
      };
      recog.onerror = (e) => cbs.onError && cbs.onError(e);
      recog.onend = () => { cbs.onEnd && cbs.onEnd(finalText.trim()); recog = null; };
      try { recog.start(); return true; }
      catch (e) { cbs.onError && cbs.onError(e); return false; }
    },

    stop() {
      if (recog) { try { recog.stop(); } catch (_) {} recog = null; }
    },

    /** Speak text aloud. cbs: { onStart(), onEnd() } */
    speak(text, cbs = {}) {
      if (!synth) { cbs.onEnd && cbs.onEnd(); return false; }
      synth.cancel();
      // strip simple markdown/emoji for cleaner speech
      const clean = String(text).replace(/[*_`#>]/g, "").replace(/\s+/g, " ").trim();
      const u = new SpeechSynthesisUtterance(clean);
      if (chosenVoice) u.voice = chosenVoice;
      u.rate = 1.04; u.pitch = 1.0; u.volume = 1.0;
      u.onstart = () => cbs.onStart && cbs.onStart();
      u.onend = () => cbs.onEnd && cbs.onEnd();
      u.onerror = () => cbs.onEnd && cbs.onEnd();
      synth.speak(u);
      return true;
    },

    cancelSpeak() { if (synth) synth.cancel(); },
    speaking() { return synth ? synth.speaking : false; },
  };
})();
