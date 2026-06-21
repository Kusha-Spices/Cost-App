/* ============================================================================
   AURORA · imagegen.js  —  Image-generation PROVIDER (demo implementation)
   ----------------------------------------------------------------------------
   In demo mode this synthesises tasteful, deterministic scene art from a prompt
   (so the canvas always looks intentional, never broken). It mirrors the shape
   of a real text-to-image API so you can swap providers without touching the
   rest of the app — see `Aurora.ImageGen.generate` and the REAL-API note below.
   ========================================================================== */
(function () {
  "use strict";
  const Aurora = (window.Aurora = window.Aurora || {});
  const { hash, clamp } = Aurora.util;

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // keyword → palette + scene cues
  const STYLES = [
    { k: ["sunset", "golden", "dusk", "warm", "sunrise", "dawn"], name: "golden-hour", top: "#2a1a3a", mid: "#ff7a59", bot: "#ffd27a", sun: "#fff0b8", scene: "mountains" },
    { k: ["ocean", "sea", "beach", "water", "wave", "coast"], name: "coastal blue", top: "#06283d", mid: "#1f6f8b", bot: "#9bd7d5", sun: "#fdf6c4", scene: "water" },
    { k: ["forest", "jungle", "tree", "green", "nature", "woods"], name: "verdant", top: "#06231a", mid: "#1b6e4a", bot: "#9fe0a0", sun: "#eafff0", scene: "mountains" },
    { k: ["night", "neon", "cyber", "city", "synthwave", "vapor"], name: "neon night", top: "#0b0220", mid: "#5b1e8a", bot: "#16d3ff", sun: "#ff4fd8", scene: "city" },
    { k: ["space", "galaxy", "star", "cosmic", "nebula", "universe"], name: "deep space", top: "#02030a", mid: "#1a1340", bot: "#3a2a7a", sun: "#bfd4ff", scene: "stars" },
    { k: ["desert", "sand", "dune", "canyon"], name: "desert", top: "#3a1f12", mid: "#b5642e", bot: "#f0c478", sun: "#fff1c2", scene: "mountains" },
    { k: ["spice", "kusha", "masala", "chili", "turmeric", "saffron"], name: "spice warmth", top: "#2a0a06", mid: "#b3261e", bot: "#f4a93a", sun: "#ffe39a", scene: "abstract" },
    { k: ["mono", "noir", "black and white", "grayscale", "greyscale"], name: "noir", top: "#0a0a0a", mid: "#3a3a3a", bot: "#cfcfcf", sun: "#ffffff", scene: "mountains" },
    { k: ["dream", "pastel", "soft", "candy"], name: "dreamy pastel", top: "#2a2350", mid: "#a98bff", bot: "#ffc7e6", sun: "#fffbe6", scene: "abstract" },
  ];
  const DEFAULT_STYLE = { name: "aurora", top: "#0b0d18", mid: "#7c5cff", bot: "#2dd4ff", sun: "#e9f6ff", scene: "abstract" };

  function pickStyle(prompt) {
    const p = (prompt || "").toLowerCase();
    for (const s of STYLES) if (s.k.some((w) => p.includes(w))) return s;
    return DEFAULT_STYLE;
  }

  function lerpHex(a, b, t) {
    const pa = [parseInt(a.slice(1, 3), 16), parseInt(a.slice(3, 5), 16), parseInt(a.slice(5, 7), 16)];
    const pb = [parseInt(b.slice(1, 3), 16), parseInt(b.slice(3, 5), 16), parseInt(b.slice(5, 7), 16)];
    const c = pa.map((v, i) => Math.round(v + (pb[i] - v) * t));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }

  function paint(prompt, w, h) {
    const style = pickStyle(prompt);
    const rnd = mulberry32(hash(prompt || "aurora"));
    const cv = document.createElement("canvas");
    cv.width = w; cv.height = h;
    const ctx = cv.getContext("2d");

    // sky gradient
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, style.top);
    g.addColorStop(0.55, style.mid);
    g.addColorStop(1, style.bot);
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);

    // sun / light source
    const sx = w * (0.25 + rnd() * 0.5), sy = h * (0.28 + rnd() * 0.2);
    const sr = Math.min(w, h) * (0.18 + rnd() * 0.12);
    const sg = ctx.createRadialGradient(sx, sy, 0, sx, sy, sr * 2.4);
    sg.addColorStop(0, style.sun); sg.addColorStop(0.18, style.sun);
    sg.addColorStop(1, "rgba(0,0,0,0)");
    ctx.globalCompositeOperation = "screen";
    ctx.fillStyle = sg; ctx.beginPath(); ctx.arc(sx, sy, sr * 2.4, 0, 7); ctx.fill();
    ctx.globalCompositeOperation = "source-over";

    if (style.scene === "stars" || style.scene === "city") {
      for (let i = 0; i < 240; i++) {
        const x = rnd() * w, y = rnd() * h * 0.8, r = rnd() * 1.6;
        ctx.fillStyle = `rgba(255,255,255,${0.3 + rnd() * 0.7})`;
        ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
      }
    }

    if (style.scene === "mountains" || style.scene === "desert") {
      for (let layer = 0; layer < 4; layer++) {
        const baseY = h * (0.5 + layer * 0.12);
        const shade = lerpHex("#000000", style.bot, 0.12 + layer * 0.16);
        ctx.fillStyle = shade;
        ctx.beginPath(); ctx.moveTo(0, h);
        let x = 0;
        ctx.lineTo(0, baseY);
        while (x < w) {
          const peak = baseY - (rnd() * 0.5 + 0.15) * h * (0.4 - layer * 0.07);
          const nx = x + w * (0.12 + rnd() * 0.16);
          ctx.lineTo((x + nx) / 2, peak);
          ctx.lineTo(nx, baseY - rnd() * 20);
          x = nx;
        }
        ctx.lineTo(w, h); ctx.closePath(); ctx.fill();
      }
    }

    if (style.scene === "water") {
      ctx.fillStyle = "rgba(0,0,0,0.18)";
      ctx.fillRect(0, h * 0.62, w, h * 0.38);
      ctx.globalCompositeOperation = "screen";
      for (let i = 0; i < 60; i++) {
        const y = h * (0.64 + rnd() * 0.34);
        ctx.fillStyle = `rgba(255,255,255,${0.04 + rnd() * 0.07})`;
        ctx.fillRect(rnd() * w, y, 30 + rnd() * 160, 2);
      }
      ctx.globalCompositeOperation = "source-over";
    }

    if (style.scene === "abstract" || style.scene === "city") {
      ctx.globalCompositeOperation = "screen";
      for (let i = 0; i < 6; i++) {
        const bx = rnd() * w, by = rnd() * h, br = (0.1 + rnd() * 0.3) * Math.min(w, h);
        const bg = ctx.createRadialGradient(bx, by, 0, bx, by, br);
        bg.addColorStop(0, lerpHex(style.mid, style.bot, rnd()));
        bg.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = bg; ctx.beginPath(); ctx.arc(bx, by, br, 0, 7); ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
    }

    // film grain
    const grain = ctx.createImageData(w, h);
    for (let i = 0; i < grain.data.length; i += 4) {
      const v = (rnd() * 255) | 0;
      grain.data[i] = grain.data[i + 1] = grain.data[i + 2] = v;
      grain.data[i + 3] = 8;
    }
    ctx.putImageData(grain, 0, 0);

    // gentle vignette
    const vg = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.3, w / 2, h / 2, Math.max(w, h) * 0.72);
    vg.addColorStop(0, "rgba(0,0,0,0)"); vg.addColorStop(1, "rgba(0,0,0,0.45)");
    ctx.fillStyle = vg; ctx.fillRect(0, 0, w, h);

    return { dataURL: cv.toDataURL("image/jpeg", 0.88), styleName: style.name };
  }

  Aurora.ImageGen = {
    lastStyle: "",
    /**
     * generate(prompt, opts) -> Promise<{ src, styleName }>
     *
     * ── REAL API (drop-in) ────────────────────────────────────────────────
     *   const r = await fetch("/api/image", {            // your backend route
     *     method: "POST",
     *     headers: { "Content-Type": "application/json" },
     *     body: JSON.stringify({ prompt, width: w, height: h })
     *   });
     *   const { url } = await r.json();
     *   return { src: url, styleName: "" };
     * The rest of AURORA only depends on this returning { src, styleName }.
     */
    generate(prompt, opts = {}) {
      const w = opts.width || 1280, h = opts.height || 720;
      return new Promise((resolve) => {
        // simulate model latency so the "generating…" UX feels real
        setTimeout(() => {
          const { dataURL, styleName } = paint(prompt, w, h);
          this.lastStyle = styleName;
          resolve({ src: dataURL, styleName });
        }, 420 + Math.random() * 360);
      });
    },
  };
})();
