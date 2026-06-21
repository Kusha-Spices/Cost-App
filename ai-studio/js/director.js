/* ============================================================================
   AURORA · director.js  —  The AI "Director" (brain)
   ----------------------------------------------------------------------------
   Turns a natural-language command (typed OR spoken) into (a) a conversational,
   opinionated reply and (b) real actions on the canvas. In DEMO mode this is a
   local intent engine — no network, no keys. The structure mirrors an agentic
   LLM loop so you can swap in a real model with tool-use later.

   ── REAL API (drop-in) ──────────────────────────────────────────────────────
   Replace `Director.handle` with a call to Claude (Anthropic Messages API),
   exposing the same canvas operations as *tools*:

     const res = await client.messages.create({
       model: "claude-opus-4-8",
       system: AURORA_PERSONA,                  // the persona below
       tools: CANVAS_TOOLS,                     // generate_image, add_text, apply_effect, animate …
       messages: [...history, { role: "user", content: command }],
     });
     // execute any tool_use blocks against Aurora.Engine, then return res' text.

   The persona + tool list below already describe that contract.
   ========================================================================== */
(function () {
  "use strict";
  const Aurora = (window.Aurora = window.Aurora || {});
  const E = Aurora.Engine, IG = Aurora.ImageGen, U = Aurora.util;
  const clamp = U.clamp, round = U.round;
  const pick = (a) => a[(Math.random() * a.length) | 0];

  /* The persona that defines the Director's voice (also the LLM system prompt). */
  const AURORA_PERSONA =
    "You are AURORA's Director: a confident, warm creative collaborator and editor. " +
    "You have real opinions and share them succinctly. You take initiative, make tasteful " +
    "choices, and always offer one concrete next step. You can generate images, add text and " +
    "shapes, apply colour grades and effects, animate layers, and assemble video reels.";

  /* ---- language helpers -------------------------------------------------- */
  function extractQuoted(raw) {
    const m = raw.match(/["'“”‘’]([^"'“”‘’]+)["'“”‘’]/);
    if (m) return m[1].trim();
    const s = raw.match(/\b(?:saying|says|that says|reading|read|:|titled|called)\s+(.+)$/i);
    return s ? s[1].replace(/["'.]+$/, "").trim() : null;
  }
  function extractSubject(raw) {
    let s = raw.replace(/^(please\s+|hey\s+|ok\s+|okay\s+)?/i, "");
    s = s.replace(/^(can you|could you|would you|i want you to|i'd like|please)\s+/i, "");
    s = s.replace(/^(generate|create|make|draw|paint|render|design|show me|give me|add|put|drop in)\s+/i, "");
    s = s.replace(/\b(a|an|the)\s+/i, "");
    s = s.replace(/\b(picture|image|photo|photograph|background|backdrop|scene|wallpaper|art|illustration|render)\s+(of\s+|showing\s+|with\s+)?/i, "");
    s = s.replace(/\b(for me|please|now)\b/gi, "");
    return s.trim() || "an abstract aurora gradient";
  }
  function has(t, ...words) { return words.some((w) => t.includes(w)); }

  /* ---- target resolution for effects/animation -------------------------- */
  function resolveTarget(t) {
    const layers = E.doc.layers;
    const texts = layers.filter((l) => l.type === "text");
    const imgs = layers.filter((l) => l.type === "image");
    if (has(t, "title", "heading", "headline")) return texts[0] || E.activeLayer();
    if (has(t, "caption", "subtitle", "subhead")) return texts[texts.length - 1] || E.activeLayer();
    if (has(t, "logo")) return texts.find((l) => /logo/i.test(l.name)) || texts[0] || E.activeLayer();
    if (has(t, "text", "words")) return texts[texts.length - 1] || E.activeLayer();
    if (has(t, "image", "picture", "photo", "background", "backdrop", "scene")) return imgs[imgs.length - 1] || E.activeLayer();
    return E.activeLayer();
  }

  /* ---- effects vocabulary ------------------------------------------------ */
  function applyEffects(t, layer) {
    const g = E.doc.grade, f = layer ? layer.filters : null;
    const did = [];
    const bump = (k, d, lo, hi) => { if (f) { f[k] = clamp(round(f[k] + d), lo, hi); } };

    if (has(t, "brighter", "brighten", "lighter")) { bump("brightness", 0.18, 0.2, 2.4); did.push(`brightness → ${pct(f.brightness)}`); }
    if (has(t, "darker", "darken")) { bump("brightness", -0.18, 0.2, 2.4); did.push(`brightness → ${pct(f.brightness)}`); }
    if (has(t, "more contrast", "punchy", "punch", "crisp")) { bump("contrast", 0.2, 0.2, 2.4); did.push(`contrast → ${pct(f.contrast)}`); }
    if (has(t, "less contrast", "flatter", "soft contrast")) { bump("contrast", -0.18, 0.2, 2.4); did.push(`contrast → ${pct(f.contrast)}`); }
    if (has(t, "more saturated", "vivid", "vibrant", "saturate", "pop", "richer", "colorful", "colourful")) { bump("saturate", 0.3, 0, 3); did.push(`saturation → ${pct(f.saturate)}`); }
    if (has(t, "desaturate", "muted", "less saturated", "wash", "faded", "pastel")) { bump("saturate", -0.3, 0, 3); did.push(`saturation → ${pct(f.saturate)}`); }
    if (has(t, "warmer", "warm", "golden", "cozy", "sunset tone")) { g.warmth = clamp(round(g.warmth + 0.35), -1, 1); did.push("warmer tone"); }
    if (has(t, "cooler", "cold", "icy", "blue tone")) { g.warmth = clamp(round(g.warmth - 0.35), -1, 1); did.push("cooler tone"); }
    if (has(t, "blur", "soften", "dreamy focus")) { bump("blur", 6, 0, 30); did.push(`blur → ${f.blur}px`); }
    if (has(t, "sharpen", "sharper", "crisper")) { bump("blur", -6, 0, 30); bump("contrast", 0.08, 0.2, 2.4); did.push("sharpened"); }
    if (has(t, "vignette")) { g.vignette = clamp(round(g.vignette + 0.5), 0, 1); did.push("vignette added"); }
    if (has(t, "black and white", "grayscale", "greyscale", "monochrome", "b&w")) { if (f) { f.grayscale = 1; f.saturate = 0; } did.push("black & white"); }
    if (has(t, "sepia", "vintage", "retro", "old film")) { if (f) { f.sepia = 0.5; f.contrast = round(f.contrast * 1.05); } g.warmth = clamp(g.warmth + 0.25, -1, 1); g.vignette = Math.max(g.vignette, 0.4); did.push("vintage sepia"); }
    if (has(t, "glow", "bloom", "halo", "ethereal")) { g.bloom = clamp(round(g.bloom + 0.5), 0, 1); did.push("dreamy bloom"); }
    if (has(t, "remove effect", "reset look", "reset grade", "clean look", "no filter", "remove filter", "neutral")) {
      if (f) Object.assign(f, { brightness: 1, contrast: 1, saturate: 1, blur: 0, hue: 0, sepia: 0, grayscale: 0 });
      Object.assign(g, { vignette: 0, warmth: 0, bloom: 0 }); did.push("look reset to neutral");
    }
    return did;
  }
  const pct = (v) => Math.round(v * 100) + "%";

  /* ---- mood / grade presets --------------------------------------------- */
  const PRESETS = {
    cinematic: (f, g) => { if (f) { f.contrast = 1.15; f.saturate = 1.08; } g.vignette = 0.6; g.warmth = 0.18; },
    sunset:    (f, g) => { if (f) { f.brightness = 1.05; f.saturate = 1.2; } g.warmth = 0.6; g.vignette = 0.35; },
    neon:      (f, g) => { if (f) { f.saturate = 1.7; f.contrast = 1.15; } g.bloom = 0.55; g.warmth = -0.2; },
    noir:      (f, g) => { if (f) { f.grayscale = 1; f.contrast = 1.3; f.saturate = 0; } g.vignette = 0.7; },
    vintage:   (f, g) => { if (f) { f.sepia = 0.55; f.contrast = 1.05; f.saturate = 0.85; } g.warmth = 0.3; g.vignette = 0.45; },
    dreamy:    (f, g) => { if (f) { f.brightness = 1.08; f.saturate = 0.9; f.blur = 1.2; } g.bloom = 0.6; },
    spice:     (f, g) => { if (f) { f.saturate = 1.25; f.contrast = 1.1; } g.warmth = 0.45; g.vignette = 0.4; },
    clean:     (f, g) => { if (f) Object.assign(f, { brightness: 1, contrast: 1.04, saturate: 1.05, blur: 0, sepia: 0, grayscale: 0 }); Object.assign(g, { vignette: 0.1, warmth: 0, bloom: 0 }); },
  };
  function presetName(t) {
    if (has(t, "cinematic", "filmic", "movie", "film look")) return "cinematic";
    if (has(t, "sunset", "golden hour", "warm vibe")) return "sunset";
    if (has(t, "neon", "synthwave", "cyberpunk", "vapor")) return "neon";
    if (has(t, "noir", "moody", "dramatic")) return "noir";
    if (has(t, "vintage", "retro", "analog", "film grain look")) return "vintage";
    if (has(t, "dreamy", "soft", "ethereal", "pastel")) return "dreamy";
    if (has(t, "spice", "kusha", "masala", "warm earthy")) return "spice";
    if (has(t, "clean", "corporate", "minimal", "crisp commercial")) return "clean";
    return null;
  }

  /* ---- animation vocabulary --------------------------------------------- */
  function animFor(t) {
    if (has(t, "fade out")) return { type: "fadeOut", dur: 1.6 };
    if (has(t, "fade")) return { type: "fadeIn", dur: 1.4 };
    if (has(t, "ken burns", "zoom in", "zoom")) return { type: "zoomIn", dur: 5 };
    if (has(t, "zoom out")) return { type: "zoomOut", dur: 5 };
    if (has(t, "pan")) return { type: "panR", dur: 5 };
    if (has(t, "slide")) return { type: "slideIn", dur: 1.2 };
    if (has(t, "rise", "up from", "lift")) return { type: "riseIn", dur: 1.3 };
    if (has(t, "spin", "rotate")) return { type: "spin", dur: 4, loop: true };
    if (has(t, "float", "bob", "hover")) return { type: "float", dur: 3.4, loop: true };
    if (has(t, "pulse", "beat", "throb")) return { type: "pulse", dur: 1.8, loop: true };
    return { type: "fadeIn", dur: 1.4 };
  }

  /* ---- opinion / critique ------------------------------------------------ */
  function critique() {
    const L = E.doc.layers, g = E.doc.grade;
    const texts = L.filter((l) => l.type === "text").length;
    const imgs = L.filter((l) => l.type === "image").length;
    const notes = [];
    if (!L.length) return { reply: "Blank canvas — a world of possibility. Want me to generate a hero background to build on?", tip: "Try: “generate a moody mountain sunrise”." };
    if (imgs && g.vignette < 0.2) notes.push("the frame could use a vignette to pull the eye inward");
    if (texts > 2) notes.push("there's a lot of text fighting for attention — I'd cut one line");
    if (g.warmth === 0 && imgs) notes.push("the grade is neutral; a touch of warmth would make it feel alive");
    if (g.bloom === 0 && imgs) notes.push("a hint of bloom would add atmosphere");
    const open = pick([
      "Honest take:", "Here's my read:", "Director's notes:", "What I'm seeing:",
    ]);
    if (!notes.length)
      return { reply: `${open} this is working. The balance is clean and the grade reads intentional. I'd leave it — or add subtle motion to bring it to life.`, tip: "Say “add a slow ken-burns zoom” to make it breathe." };
    const note = notes[0];
    return { reply: `${open} strong start. My one note — ${note}. Want me to fix that now?`, tip: `Say “yes” / “fix it”, or “surprise me” and I'll take it from here.` };
  }

  /* ---- autonomous improvement ("surprise me / improvise") --------------- */
  async function improvise() {
    E.snapshot();
    const did = [];
    let layer = E.activeLayer();
    if (!E.doc.layers.length) {
      const subj = pick(["a moody mountain range at golden hour", "a calm neon coastline at dusk", "an abstract aurora of violet and cyan", "warm spice tones swirling like smoke"]);
      const { src, styleName } = await IG.generate(subj, { width: E.doc.width, height: E.doc.height });
      const bg = Aurora.makeLayer("image", { name: "Background", x: 0, y: 0, w: E.doc.width, h: E.doc.height, src, anim: { type: "zoomIn", dur: 6 } });
      E.addLayer(bg, { snapshot: false }); E.doc.layers = [bg, ...E.doc.layers.filter((l) => l.id !== bg.id)];
      layer = bg; did.push(`generated a ${styleName} background`);
    }
    const choice = pick(["cinematic", "sunset", "dreamy"]);
    PRESETS[choice](layer && layer.filters, E.doc.grade);
    did.push(`applied a ${choice} grade`);
    if (layer && !layer.anim) { layer.anim = { type: "zoomIn", dur: 6 }; did.push("added a slow zoom"); }
    E.render();
    return {
      reply: pick([
        "I took the wheel. Pushed it toward something with mood and depth — trust me, it reads better in motion.",
        "Done — leaned into atmosphere over flatness. Hit play; the slow push is what sells it.",
        "Made a call: richer grade, a vignette, and a gentle zoom. It feels like a frame from a film now.",
      ]),
      did, tip: "Hit Play ▶ to feel it. Don't like a choice? Say “undo”.",
    };
  }

  /* ---- actions ----------------------------------------------------------- */
  async function doGenerateImage(raw, t) {
    const subject = extractSubject(raw);
    const asBg = has(t, "background", "backdrop", "scene", "wallpaper") || E.doc.layers.filter((l) => l.type === "image").length === 0;
    const { src, styleName } = await IG.generate(subject, { width: E.doc.width, height: E.doc.height });
    let layer;
    if (asBg) {
      layer = Aurora.makeLayer("image", { name: "Background", x: 0, y: 0, w: E.doc.width, h: E.doc.height, src });
      E.addLayer(layer, { snapshot: false });
      E.doc.layers = [layer, ...E.doc.layers.filter((l) => l.id !== layer.id)];
      E.render();
    } else {
      const w = Math.round(E.doc.width * 0.5), h = Math.round(w * 0.62);
      layer = Aurora.makeLayer("image", { name: "Picture", x: (E.doc.width - w) / 2, y: (E.doc.height - h) / 2, w, h, src, filters: { brightness: 1, contrast: 1, saturate: 1, blur: 0, hue: 0, sepia: 0, grayscale: 0 } });
      E.addLayer(layer, { snapshot: false });
    }
    return {
      reply: pick([
        `There it is — “${subject}”. I leaned into a ${styleName} palette; it's got real depth.`,
        `Generated “${subject}” with a ${styleName} look. Honestly? The light is the best part of this one.`,
        `“${subject}”, served. I went ${styleName} — feels cohesive. We can re-roll if you want a different mood.`,
      ]),
      did: [`generated image · ${styleName}`], tip: asBg ? "Now say “add a title that says …”." : "Say “center it” or drag it where you want.",
    };
  }

  function doAddText(raw, t) {
    const value = extractQuoted(raw) || (has(t, "title") ? "Headline" : "Your text here");
    const isTitle = has(t, "title", "heading", "headline", "logo") || value.length < 18;
    const isCaption = has(t, "caption", "subtitle", "subhead");
    const W = E.doc.width;
    const layer = Aurora.makeLayer("text", {
      name: isTitle ? "Title" : isCaption ? "Caption" : "Text",
      x: W * 0.1, y: isCaption ? E.doc.height * 0.62 : E.doc.height * 0.4,
      w: W * 0.8, h: 160,
      text: {
        value, size: isCaption ? 34 : isTitle ? 92 : 56,
        weight: isCaption ? 500 : 800, color: "#ffffff",
        font: "Inter", align: "center", italic: false, shadow: true, lineHeight: 1.05, letter: isTitle ? 1 : 0,
      },
    });
    E.addLayer(layer, { snapshot: false });
    return {
      reply: pick([
        `Set “${value}”. I'd keep it bold and let the image do the talking underneath.`,
        `“${value}” is in. Big, confident, centered — it earns the space.`,
        `Added “${value}”. Want it animated in? A fade or rise reads premium.`,
      ]),
      did: [`text layer · “${value}”`], tip: "Say “animate the title with a rise”.",
    };
  }

  function doAddShape(t) {
    const kind = has(t, "circle", "ellipse", "round") ? "ellipse" : "rect";
    const fill = has(t, "banner", "bar") ? "rgba(0,0,0,0.45)" : pick(["#7c5cff", "#2dd4ff", "#ff5cf0", "#ffcf6b"]);
    const W = E.doc.width;
    const layer = Aurora.makeLayer("shape", {
      name: kind === "ellipse" ? "Circle" : "Shape",
      x: W * 0.36, y: E.doc.height * 0.34, w: 300, h: kind === "ellipse" ? 300 : 200,
      shape: { kind, fill, radius: 22, stroke: 0, strokeColor: "#ffffff" },
      opacity: has(t, "banner", "bar") ? 0.9 : 0.85,
    });
    E.addLayer(layer, { snapshot: false });
    return { reply: `Dropped in a ${kind === "ellipse" ? "circle" : "shape"}. Good for grounding text or adding a pop of colour.`, did: [`shape · ${kind}`], tip: "Drag it around, or say “make it a banner behind the title”." };
  }

  function doEffects(raw, t, alsoPreset) {
    const layer = resolveTarget(t);
    let did = [];
    const p = presetName(t);
    if (p && alsoPreset) { PRESETS[p](layer && layer.filters, E.doc.grade); did.push(`${p} grade`); }
    did = did.concat(applyEffects(t, layer));
    E.render();
    if (!did.length) return null;
    return {
      reply: pick([
        `Done. ${capitalize(did.join(", "))}. ${pick(["Reads richer already.", "That's the move.", "Subtle but it lands.", "Much more intentional now."])}`,
        `Graded it — ${did.join(", ")}. ${pick(["I like where this is going.", "Let it breathe before adding more.", "We can push further if you want."])}`,
      ]),
      did, tip: pick(["Say “a touch more contrast”.", "Want a vignette to finish it?", "Say “surprise me” for a full pass."]),
    };
  }

  function doAnimate(raw, t) {
    const layer = resolveTarget(t);
    if (!layer) return { reply: "Nothing to animate yet — generate or add a layer first.", did: [], tip: "Try “generate a sunrise” then “add a ken-burns zoom”." };
    const a = animFor(t);
    layer.anim = Object.assign({ delay: 0.1, loop: false }, a);
    E.render();
    return {
      reply: pick([
        `Animated ${layer.name} — a ${a.type.replace(/([A-Z])/g, " $1").toLowerCase()}. Hit play; motion changes everything.`,
        `${layer.name} now moves with a ${a.type.replace(/([A-Z])/g, " $1").toLowerCase()}. It feels alive.`,
      ]),
      did: [`${layer.name} · ${a.type}`], tip: "Press Play ▶ (or Space) to preview.", play: true,
    };
  }

  async function doVideo(raw, t) {
    E.snapshot();
    const subject = extractSubject(raw.replace(/\b(video|reel|montage|clip|trailer|movie|edit)\b/gi, "").trim()) ;
    const base = subject && subject !== "an abstract aurora gradient" ? subject : pick(["a cinematic mountain journey", "a neon city at night", "a golden coastline"]);
    // duration
    const dm = raw.match(/(\d+)\s*(?:s|sec|secs|seconds)/i);
    E.doc.duration = dm ? clamp(parseInt(dm[1]), 3, 20) : 8;

    // generate a short sequence of stills with staggered ken-burns + crossfades
    const variants = [base, base + ", wide establishing shot", base + ", close detail, dramatic light"];
    const per = E.doc.duration / variants.length;
    E.doc.layers = []; E.els.forEach((n) => n.remove()); E.els.clear();
    for (let i = 0; i < variants.length; i++) {
      const { src } = await IG.generate(variants[i], { width: E.doc.width, height: E.doc.height });
      const layer = Aurora.makeLayer("image", {
        name: `Shot ${i + 1}`, x: 0, y: 0, w: E.doc.width, h: E.doc.height, src,
        anim: { type: i % 2 ? "panR" : "zoomIn", dur: per + 0.8, delay: i * per, loop: false },
      });
      E.doc.layers.push(layer);
    }
    // cinematic grade + a title card
    PRESETS.cinematic(E.doc.layers[0].filters, E.doc.grade);
    const title = Aurora.makeLayer("text", {
      name: "Title", x: E.doc.width * 0.1, y: E.doc.height * 0.42, w: E.doc.width * 0.8, h: 160,
      text: { value: titleCase(base), size: 84, weight: 800, color: "#fff", font: "Inter", align: "center", italic: false, shadow: true, lineHeight: 1.05, letter: 1 },
      anim: { type: "riseIn", dur: 1.4, delay: 0.4, loop: false },
    });
    E.doc.layers.push(title);
    E.render(); E._changed();
    return {
      reply: pick([
        `Cut a ${E.doc.duration}s reel from “${base}” — three shots, ken-burns and pans, cinematic grade, title on the open. Rolling it now.`,
        `Built you a ${E.doc.duration}-second sequence: establishing → motion → detail, graded for mood, with a title card. Take a look.`,
      ]),
      did: [`${variants.length}-shot reel · ${E.doc.duration}s`, "cinematic grade", "title card"],
      tip: "This is a real in-browser edit. Export → MP4 is where a video-gen provider plugs in.",
      play: true,
    };
  }

  /* ---- helpers ----------------------------------------------------------- */
  const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const titleCase = (s) => s.replace(/\b\w/g, (c) => c.toUpperCase());

  /* ---- the dispatcher ---------------------------------------------------- */
  const Director = (Aurora.Director = {
    persona: AURORA_PERSONA,

    greeting() {
      return {
        reply: "Hey — I'm your Director. Tell me what you want and I'll build it: generate images, write titles, grade the look, animate, even cut a reel. Type it or hold the mic and just talk.",
        tip: "Try “generate a golden-hour mountain scene”, then “add a title that says AURORA”, then “make it cinematic”.",
      };
    },

    /** handle(text) -> Promise<{ reply, did?, tip?, play? }> and performs actions */
    async handle(rawIn) {
      const raw = (rawIn || "").trim();
      const t = raw.toLowerCase();
      if (!raw) return { reply: "I'm listening — what should we make?" };

      // conversational, non-mutating
      if (/^(hi|hey|hello|yo|sup|hiya|good (morning|evening|afternoon))\b/.test(t))
        return { reply: pick(["Hey! Ready when you are. What are we creating?", "Hi — let's make something good. Give me a scene or a vibe."]), tip: "e.g. “generate a neon city at night”." };
      if (has(t, "who are you", "what can you do", "help", "what do you do"))
        return { reply: "I'm AURORA's Director. I generate images, add text & shapes, grade colour, build effects, animate layers and assemble video reels — all from plain language, typed or spoken. I'll also give you honest opinions.", tip: "Say “surprise me” and I'll just run with it." };
      if (has(t, "thank")) return { reply: pick(["Anytime. What's next?", "Of course — want to push it further?"]) };

      // opinions / improvisation
      if (has(t, "what do you think", "your opinion", "thoughts", "feedback", "critique", "is it good", "how does it look", "rate it"))
        return critique();
      if (has(t, "surprise me", "your call", "you decide", "improvise", "make it better", "do your thing", "take over", "make it pop more") && !has(t, "saturat"))
        return await improvise();
      if (/^(yes|yeah|yep|sure|do it|go ahead|fix it|please do)\b/.test(t))
        return await improvise();

      // transport
      if (/^(play|preview|run it|roll it|start)\b/.test(t) || has(t, "press play", "hit play")) { E.play(); return { reply: pick(["Rolling. ▶", "Playing it back.", "Here it goes."]), play: false }; }
      if (/^(stop|pause|halt)\b/.test(t)) { E.stop(); return { reply: "Stopped." }; }

      // destructive
      if (has(t, "clear", "start over", "wipe", "blank canvas", "delete everything", "reset canvas")) { E.clearLayers(); return { reply: "Cleared the canvas. Fresh start — what's the vision?", did: ["canvas cleared"] }; }
      if (/^(delete|remove)\b/.test(t) && has(t, "this", "it", "selected", "that")) {
        const l = E.activeLayer(); if (l) { E.removeLayer(l.id); return { reply: `Removed ${l.name}.`, did: ["layer deleted"] }; }
        return { reply: "Nothing selected to remove — click a layer first." };
      }
      if (has(t, "undo")) { const ok = E.undo(); return { reply: ok ? "Undone." : "Nothing left to undo." }; }

      // VIDEO / reel (check before generic image)
      if (has(t, "video", "reel", "montage", "trailer", "clip") && has(t, "make", "generate", "create", "cut", "build", "assemble", "edit"))
        return await doVideo(raw, t);

      // ANIMATE
      if (has(t, "animate", "animation", "motion", "ken burns", "zoom", "pan", "fade", "slide", "spin", "rise up", "float", "pulse") &&
          (has(t, "animate", "animation", "motion", "ken burns") || has(t, "add", "give", "make", "apply")))
        return doAnimate(raw, t);

      // mood preset (explicit "vibe/look/grade/mood")
      if (presetName(t) && has(t, "vibe", "look", "mood", "grade", "feel", "style", "tone")) {
        const r = doEffects(raw, t, true); if (r) return r;
      }

      // IMAGE generation
      if ((has(t, "generate", "create", "make", "draw", "paint", "render", "design", "show me", "give me") &&
           has(t, "image", "picture", "photo", "background", "scene", "wallpaper", "art", "illustration")) ||
          /^(generate|create|paint|draw|render)\b/.test(t))
        return await doGenerateImage(raw, t);

      // TEXT
      if (has(t, "add text", "add a title", "add title", "write", "caption", "heading", "headline", "subtitle", "type out") ||
          (has(t, "add") && has(t, "text", "title")))
        return doAddText(raw, t);

      // SHAPE
      if (has(t, "shape", "circle", "rectangle", "square", "box", "ellipse", "banner", "bar") && has(t, "add", "draw", "put", "drop"))
        return doAddShape(t);

      // EFFECTS / grade (broad)
      {
        const r = doEffects(raw, t, true);
        if (r) return r;
      }

      // FALLBACK — be agentic: treat it as something to create
      const subject = extractSubject(raw);
      const r = await doGenerateImage("generate background of " + subject, t);
      r.reply = `I read that as a scene to create, so I made it: ${r.reply} If you meant something else, just say the word.`;
      return r;
    },
  });
})();
