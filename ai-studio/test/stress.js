/* ============================================================================
   AURORA · test/stress.js  —  headless stress + correctness harness (no deps)
   ----------------------------------------------------------------------------
   Stubs a minimal DOM + canvas, loads the real engine/imagegen/voice/director,
   and hammers them:
     1. targeted intent checks   (each command produces the right mutation)
     2. effects + presets         (full vocabulary, invariants hold)
     3. animation                 (every type; frames never produce NaN)
     4. engine direct             (mass add/remove/duplicate/undo/seek/play)
     5. randomized fuzz           (1200 rounds incl. malformed/emoji/huge input)
     6. image-gen real paint      (every palette/scene branch)
     7. voice provider            (graceful when unsupported)
   Exits non-zero on any failure.  Run:  node test/stress.js   (or npm test)
   ========================================================================== */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");
const JSDIR = path.join(__dirname, "..", "js");

/* ---------------- minimal DOM + canvas stub ---------------- */
function makeCtx() {
  const grad = { addColorStop() {} };
  return {
    createLinearGradient: () => grad, createRadialGradient: () => grad,
    fillRect() {}, beginPath() {}, arc() {}, fill() {}, moveTo() {}, lineTo() {},
    closePath() {}, drawImage() {}, save() {}, restore() {},
    createImageData: (w, h) => ({ data: new Uint8ClampedArray(w * h * 4) }),
    putImageData() {}, set fillStyle(v) {}, set globalCompositeOperation(v) {}, set globalAlpha(v) {},
  };
}
function makeNode(tag) {
  return {
    tag, style: {}, dataset: {}, children: [], textContent: "", className: "",
    width: 1280, height: 720,
    classList: { _s: new Set(), add(c){this._s.add(c);}, remove(c){this._s.delete(c);},
      toggle(c,f){ f=(f===undefined)?!this._s.has(c):f; f?this._s.add(c):this._s.delete(c); return f; },
      contains(c){return this._s.has(c);} },
    appendChild(c){ this.children.push(c); return c; },
    insertBefore(c){ this.children.push(c); return c; },
    remove(){}, querySelector(){ return makeNode("div"); }, querySelectorAll(){ return []; },
    addEventListener(){}, getBoundingClientRect: () => ({ left:0, top:0, width:1280, height:720 }),
    getContext: () => makeCtx(), toDataURL: () => "data:image/jpeg;base64,/9j/STUBDATA",
  };
}
const elements = {};
["gradeVignette","gradeTint","gradeBloom"].forEach(id => elements[id] = makeNode("div"));
const win = { addEventListener(){}, removeEventListener(){} };
const sandbox = {
  window: win,
  document: {
    createElement: (t) => makeNode(t),
    getElementById: (id) => elements[id] || (elements[id] = makeNode("div")),
    querySelector: () => makeNode("div"), querySelectorAll: () => [], addEventListener(){},
  },
  performance: { now: () => Date.now() },
  requestAnimationFrame: () => 0, cancelAnimationFrame: () => {},
  setTimeout: (fn) => { fn(); return 0; },          // immediate → fast generation
  clearTimeout, Promise, console, Math, Date, JSON, Uint8ClampedArray, parseInt, parseFloat, isNaN,
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
for (const f of ["engine.js","imagegen.js","voice.js","director.js"]) {
  vm.runInContext(fs.readFileSync(path.join(JSDIR, f), "utf8"), sandbox, { filename: f });
}
const A = win.Aurora, E = A.Engine, D = A.Director, IG = A.ImageGen, V = A.Voice;

/* ---------------- assertions + invariants ---------------- */
let pass = 0, fail = 0; const fails = [];
function ok(cond, msg) { if (cond) pass++; else { fail++; fails.push(msg); } }

function invariants(label) {
  const d = E.doc;
  ok(Array.isArray(d.layers), `${label}: layers is array`);
  ok(Number.isFinite(d.duration) && d.duration > 0, `${label}: duration finite>0 (${d.duration})`);
  const g = d.grade;
  ok(["vignette","warmth","bloom"].every(k => Number.isFinite(g[k])), `${label}: grade finite`);
  ok(g.vignette >= 0 && g.vignette <= 1, `${label}: vignette in range (${g.vignette})`);
  ok(g.warmth >= -1 && g.warmth <= 1, `${label}: warmth in range (${g.warmth})`);
  ok(g.bloom >= 0 && g.bloom <= 1, `${label}: bloom in range (${g.bloom})`);
  for (const l of d.layers) {
    ok(typeof l.id === "string", `${label}: layer id`);
    ok(["image","text","shape"].includes(l.type), `${label}: layer type ${l.type}`);
    ok(["x","y","w","h","rot","opacity"].every(k => Number.isFinite(l[k])), `${label}: ${l.type} numeric fields`);
    ok(l.opacity >= 0 && l.opacity <= 1, `${label}: opacity range`);
    ok(["brightness","contrast","saturate","blur","hue","sepia","grayscale"].every(k => Number.isFinite(l.filters[k])), `${label}: filters finite`);
    ok(l.anim === null || typeof l.anim.type === "string", `${label}: anim shape`);
  }
  E.render();
  ok(E.els.size === d.layers.length, `${label}: els match layers (${E.els.size}/${d.layers.length})`);
}
function noNaNFrame(t) {
  E.applyFrame(t);
  for (const [, n] of E.els) {
    ok(!String(n.style.transform).includes("NaN"), `frame@${t}: transform no NaN (${n.style.transform})`);
    ok(!String(n.style.opacity).includes("NaN") && Number.isFinite(+n.style.opacity || 0), `frame@${t}: opacity no NaN`);
  }
}

(async () => {
  E.init(makeNode("stage"));

  /* 1 — targeted intent checks */
  await D.handle("generate a golden hour mountain scene");
  ok(E.doc.layers.some(l => l.type === "image"), "intent: image created");
  await D.handle('add a title that says "Kusha Spices"');
  ok(E.doc.layers.some(l => l.type === "text" && l.text.value === "Kusha Spices"), "intent: title text correct");
  await D.handle("add a circle");
  ok(E.doc.layers.some(l => l.type === "shape" && l.shape.kind === "ellipse"), "intent: circle shape");
  const before = JSON.stringify(E.doc.grade);
  await D.handle("make it cinematic");
  ok(JSON.stringify(E.doc.grade) !== before, "intent: cinematic changed grade");
  invariants("after targeted");

  /* 2 — effects + presets vocabulary */
  const fx = ["brighter","darker","more contrast","vivid","muted","warmer","cooler","blur it",
    "sharpen","add a vignette","black and white","sepia vintage","add glow","reset look",
    "give it a neon vibe","make it noir","dreamy look","sunset vibe","spice mood","clean corporate look"];
  for (const c of fx) { await D.handle(c); invariants("fx:" + c); }

  /* 3 — animation: every type, frames must be NaN-free across the timeline */
  const anims = ["fade in","fade out","ken burns zoom","zoom out","pan","slide in","rise up","spin","float","pulse"];
  for (const a of anims) {
    await D.handle("animate the title with a " + a);
    invariants("anim:" + a);
    for (const t of [0, 0.5, 1, E.doc.duration / 2, E.doc.duration, E.doc.duration + 1]) noNaNFrame(t);
  }
  E.stop();

  /* 4 — engine direct stress */
  E.clearLayers();
  for (let i = 0; i < 250; i++) {
    const t = ["image","text","shape"][i % 3];
    E.addLayer(A.makeLayer(t, { src: "data:image/jpeg;base64,X" }), { snapshot: i % 5 === 0 });
  }
  ok(E.doc.layers.length === 250, "engine: 250 layers added");
  invariants("mass-add");
  for (let i = 0; i < 60; i++) { const l = E.doc.layers[(Math.random()*E.doc.layers.length)|0]; if (l) E.duplicateLayer(l.id); }
  for (let i = 0; i < 80; i++) { const l = E.doc.layers[(Math.random()*E.doc.layers.length)|0]; if (l) E.removeLayer(l.id); }
  invariants("mass-edit");
  E.play(); noNaNFrame(2.2); E.seek(3.3); E.pause(); E.stop();
  let u = 0; while (E.undo()) { if (++u > 500) break; }
  ok(u > 0, "engine: undo chain ran (" + u + ")");
  invariants("post-undo");

  /* 5 — randomized fuzz with malformed input (gen stubbed for speed) */
  const realGen = IG.generate.bind(IG);
  IG.generate = () => Promise.resolve({ src: "data:image/jpeg;base64,X", styleName: "stub" });
  const huge = "z".repeat(600);
  const pool = ["", "   ", "!!!", "😀🎬🔥", "a", "12345", huge, "generate", "make it", "add",
    "generate a neon city at night", "generate a forest at dawn", "generate space nebula",
    'add a title that says "Hello, World 123 ✦"', "add text", "add a banner", "add a square",
    "brighter","warmer","cooler","vignette","black and white","sepia","glow","reset look","vivid","muted",
    "give it a cinematic vibe","make it noir","dreamy","sunset look","clean look",
    "animate the title with a fade","add a ken burns zoom","spin it","make it float","pulse the logo",
    "make a 3 second reel of a mountain","make an 8s montage of the ocean","cut a trailer",
    "what do you think","surprise me","improvise","make it better","yes","no thanks",
    "undo","clear canvas","play","stop","center it","delete this","hello there","thanks","who are you"];
  function rnd(a){ return a[(Math.random()*a.length)|0]; }
  for (let i = 0; i < 1200; i++) {
    try {
      const roll = Math.random();
      if (roll < 0.7) {
        await D.handle(rnd(pool));
      } else if (roll < 0.8) {
        const l = E.doc.layers[(Math.random()*E.doc.layers.length)|0]; if (l) E.select(l.id);
      } else if (roll < 0.86) {
        E.seek(Math.random() * (E.doc.duration + 2) - 1);
      } else if (roll < 0.92) {
        E.setGrade({ vignette: Math.random()*2-0.5, warmth: Math.random()*3-1.5, bloom: Math.random()*2-0.5 });
      } else if (roll < 0.96) {
        const l = E.doc.layers[(Math.random()*E.doc.layers.length)|0]; if (l) E.duplicateLayer(l.id);
      } else { E.undo(); }
    } catch (e) { fail++; fails.push("FUZZ THREW @" + i + ": " + (e.stack || e)); }
    if (i % 50 === 0) invariants("fuzz#" + i);
  }
  invariants("post-fuzz");
  IG.generate = realGen;

  /* 6 — image-gen real paint over every palette + scene branch */
  const prompts = ["golden sunset","ocean beach waves","forest jungle trees","neon cyberpunk city",
    "space galaxy nebula stars","desert sand dunes","kusha spice masala","black and white noir",
    "dreamy pastel candy","a plain abstract gradient","mountain at dawn","random gibberish xyzzy"];
  for (const p of prompts) {
    try { const r = await realGen(p, { width: 320, height: 200 });
      ok(r && typeof r.src === "string" && r.src.startsWith("data:"), "imagegen: src for «" + p + "»");
    } catch (e) { fail++; fails.push("IMAGEGEN THREW «" + p + "»: " + (e.stack || e)); }
  }

  /* 7 — voice provider graceful when unsupported */
  ok(V.supportedSTT === false && V.supportedTTS === false, "voice: unsupported flags in headless");
  ok(V.speak("hello", {}) === false, "voice: speak returns false gracefully");
  ok(V.listen({ onError: () => {} }) === false, "voice: listen returns false gracefully");
  let errCalled = false; V.listen({ onError: () => { errCalled = true; } }); ok(errCalled, "voice: listen invokes onError");

  /* ---- report ---- */
  console.log(`\n──────────── AURORA stress test ────────────`);
  console.log(`checks: ${pass} passed, ${fail} failed`);
  if (fail) { console.log("\nFAILURES:"); fails.slice(0, 25).forEach(f => console.log("  ✗ " + f)); }
  console.log(`${fail === 0 ? "✓ ALL GREEN — no errors across all functions" : "✗ FAILURES DETECTED"}`);
  process.exit(fail === 0 ? 0 : 1);
})().catch((e) => { console.error("HARNESS CRASH:", e.stack || e); process.exit(2); });
