/* ============================================================================
   AURORA · engine.js
   The creative document model + DOM stage renderer + animation/timeline player.
   Everything is real and runs in the browser with no dependencies.
   ========================================================================== */
(function () {
  "use strict";
  const Aurora = (window.Aurora = window.Aurora || {});

  /* ---- tiny utilities ---------------------------------------------------- */
  const util = (Aurora.util = {
    uid: () => "L" + Math.random().toString(36).slice(2, 9),
    clamp: (v, a, b) => Math.max(a, Math.min(b, v)),
    lerp: (a, b, t) => a + (b - a) * t,
    round: (v, d = 2) => Math.round(v * 10 ** d) / 10 ** d,
    hash(str) {
      let h = 2166136261;
      for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
      return (h >>> 0);
    },
    easeInOutCubic: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    easeOutCubic: (t) => 1 - Math.pow(1 - t, 3),
    deep: (o) => JSON.parse(JSON.stringify(o)),
  });

  /* ---- layer factory ----------------------------------------------------- */
  function makeLayer(type, props = {}) {
    const base = {
      id: util.uid(),
      type,
      name: props.name || (type[0].toUpperCase() + type.slice(1)),
      x: props.x ?? 120, y: props.y ?? 120,
      w: props.w ?? 360, h: props.h ?? 200,
      rot: props.rot ?? 0,
      opacity: props.opacity ?? 1,
      visible: true,
      filters: Object.assign(
        { brightness: 1, contrast: 1, saturate: 1, blur: 0, hue: 0, sepia: 0, grayscale: 0 },
        props.filters || {}
      ),
      anim: props.anim || null,
    };
    if (type === "image") base.src = props.src || "";
    if (type === "text")
      base.text = Object.assign(
        { value: "Text", size: 64, weight: 800, color: "#ffffff", font: "Inter",
          align: "center", italic: false, shadow: true, lineHeight: 1.05, letter: 0 },
        props.text || {}
      );
    if (type === "shape")
      base.shape = Object.assign(
        { kind: "rect", fill: "#7c5cff", radius: 18, stroke: 0, strokeColor: "#ffffff" },
        props.shape || {}
      );
    return Object.assign(base, props.extra || {});
  }
  Aurora.makeLayer = makeLayer;

  /* ---- the engine -------------------------------------------------------- */
  const Engine = (Aurora.Engine = {
    doc: null,
    stageEl: null,
    els: new Map(), // layerId -> DOM node
    state: { scale: 1, selectedId: null, playing: false, time: 0, raf: 0, last: 0 },
    history: [],
    _onChange: null,

    init(stageEl) {
      this.stageEl = stageEl;
      stageEl.style.boxShadow = "0 50px 130px -30px rgba(0,0,0,.92)";
      this.newDoc();
      window.addEventListener("resize", () => this.fitStage());
      return this;
    },

    onChange(fn) { this._onChange = fn; },
    _changed() { if (this._onChange) this._onChange(); },

    newDoc(opts = {}) {
      this.doc = {
        width: opts.width || 1280,
        height: opts.height || 720,
        duration: opts.duration || 6,
        layers: [],
        grade: { vignette: 0, warmth: 0, bloom: 0 }, // -1..1 warmth, 0..1 others
      };
      // wipe DOM layers
      this.els.forEach((n) => n.remove());
      this.els.clear();
      this.state.selectedId = null;
      this.fitStage();
      this.render();
    },

    /* -- layer ops -- */
    addLayer(layer, { snapshot = true } = {}) {
      if (snapshot) this.snapshot();
      this.doc.layers.push(layer);
      this.render();
      this.select(layer.id);
      this._changed();
      return layer;
    },
    getLayer(id) { return this.doc.layers.find((l) => l.id === id); },
    removeLayer(id, { snapshot = true } = {}) {
      if (snapshot) this.snapshot();
      this.doc.layers = this.doc.layers.filter((l) => l.id !== id);
      const n = this.els.get(id); if (n) { n.remove(); this.els.delete(id); }
      if (this.state.selectedId === id) this.select(null);
      this.render(); this._changed();
    },
    duplicateLayer(id) {
      const l = this.getLayer(id); if (!l) return;
      this.snapshot();
      const copy = util.deep(l);
      copy.id = util.uid(); copy.x += 28; copy.y += 28; copy.name = l.name + " copy";
      this.doc.layers.push(copy); this.render(); this.select(copy.id); this._changed();
      return copy;
    },
    clearLayers() {
      this.snapshot();
      this.doc.layers = [];
      this.doc.grade = { vignette: 0, warmth: 0, bloom: 0 };
      this.els.forEach((n) => n.remove()); this.els.clear();
      this.select(null); this.render(); this._changed();
    },

    /* the "active" layer commands operate on: selection, else top-most image, else top layer */
    activeLayer() {
      if (this.state.selectedId) return this.getLayer(this.state.selectedId);
      const imgs = this.doc.layers.filter((l) => l.type === "image");
      if (imgs.length) return imgs[imgs.length - 1];
      return this.doc.layers[this.doc.layers.length - 1] || null;
    },

    select(id) {
      this.state.selectedId = id;
      this.els.forEach((n, lid) => n.classList.toggle("selected", lid === id && !this.state.playing));
      this._changed();
    },

    /* -- rendering -- */
    fitStage() {
      const wrap = this.stageEl.parentElement;
      if (!wrap) return;
      const pad = 40;
      const aw = wrap.clientWidth - pad, ah = wrap.clientHeight - pad;
      const s = Math.min(aw / this.doc.width, ah / this.doc.height);
      this.state.scale = util.clamp(s, 0.05, 4);
      this.stageEl.style.width = this.doc.width + "px";
      this.stageEl.style.height = this.doc.height + "px";
      this.stageEl.style.transform = `scale(${this.state.scale})`;
    },

    render() {
      const doc = this.doc;
      // create / update layer nodes (in document order = stacking order)
      doc.layers.forEach((l, i) => {
        let n = this.els.get(l.id);
        if (!n) {
          n = document.createElement("div");
          n.className = "layer " + l.type;
          n.dataset.id = l.id;
          // keep grade overlays on top: insert before first .grade
          const firstGrade = this.stageEl.querySelector(".grade");
          this.stageEl.insertBefore(n, firstGrade);
          this.els.set(l.id, n);
        }
        n.className = "layer " + l.type + (l.id === this.state.selectedId && !this.state.playing ? " selected" : "");
        n.style.zIndex = i + 1;
        n.style.display = l.visible ? "" : "none";
        this._applyLayerStatic(n, l);
      });
      // remove orphans
      this.els.forEach((n, id) => { if (!doc.layers.find((l) => l.id === id)) { n.remove(); this.els.delete(id); } });
      this._applyGrade();
    },

    _filterStr(f) {
      return `brightness(${f.brightness}) contrast(${f.contrast}) saturate(${f.saturate}) ` +
             `blur(${f.blur}px) hue-rotate(${f.hue}deg) sepia(${f.sepia}) grayscale(${f.grayscale})`;
    },

    _applyLayerStatic(n, l) {
      n.style.left = "0px"; n.style.top = "0px";
      n.style.width = l.w + "px"; n.style.height = l.h + "px";
      n.style.transform = `translate(${l.x}px, ${l.y}px) rotate(${l.rot}deg)`;
      n.style.opacity = l.opacity;
      n.style.filter = this._filterStr(l.filters);

      if (l.type === "image") {
        n.style.backgroundImage = `url("${l.src}")`;
      } else if (l.type === "text") {
        const t = l.text;
        n.style.display = "flex";
        n.style.alignItems = "center";
        n.style.justifyContent = t.align === "left" ? "flex-start" : t.align === "right" ? "flex-end" : "center";
        n.style.textAlign = t.align;
        n.style.color = t.color;
        n.style.fontFamily = t.font + ", Inter, sans-serif";
        n.style.fontWeight = t.weight;
        n.style.fontSize = t.size + "px";
        n.style.lineHeight = t.lineHeight;
        n.style.fontStyle = t.italic ? "italic" : "normal";
        n.style.letterSpacing = (t.letter || 0) + "px";
        n.style.textShadow = t.shadow ? "0 4px 24px rgba(0,0,0,.55)" : "none";
        n.textContent = t.value;
      } else if (l.type === "shape") {
        const s = l.shape;
        n.style.background = s.fill;
        n.style.borderRadius = s.kind === "ellipse" ? "50%" : s.radius + "px";
        n.style.border = s.stroke ? `${s.stroke}px solid ${s.strokeColor}` : "none";
      }
    },

    _applyGrade() {
      const g = this.doc.grade;
      const vg = document.getElementById("gradeVignette");
      const tn = document.getElementById("gradeTint");
      const bl = document.getElementById("gradeBloom");
      if (vg) vg.style.boxShadow = `inset 0 0 ${120 + g.vignette * 260}px ${20 + g.vignette * 120}px rgba(0,0,0,${0.0 + g.vignette * 0.85})`;
      if (tn) {
        const warm = g.warmth; // -1 cool .. +1 warm
        tn.style.opacity = Math.abs(warm) * 0.55;
        tn.style.background = warm >= 0
          ? "linear-gradient(0deg, rgba(255,150,40,1), rgba(255,90,160,.6))"
          : "linear-gradient(0deg, rgba(40,120,255,1), rgba(40,220,255,.6))";
      }
      if (bl) {
        bl.style.opacity = g.bloom * 0.6;
        bl.style.background = "radial-gradient(circle at 50% 42%, rgba(255,255,255,.9), transparent 60%)";
      }
    },

    setGrade(patch) { Object.assign(this.doc.grade, patch); this._applyGrade(); this._changed(); },

    /* -- animation / timeline -- */
    _animFrame(l, t) {
      // returns {dx,dy,scale,rot,op}; identity if no anim or out of window
      const a = l.anim;
      const id = { dx: 0, dy: 0, scale: 1, rot: 0, op: 1 };
      if (!a) return id;
      const loopT = a.loop ? (t % a.dur) : util.clamp(t - (a.delay || 0), 0, a.dur);
      const dur = a.dur || 1;
      let p = util.clamp((t - (a.delay || 0)) / dur, 0, 1);
      const e = util.easeInOutCubic(p);
      switch (a.type) {
        case "fadeIn":  return { ...id, op: e };
        case "fadeOut": return { ...id, op: 1 - e };
        case "zoomIn":  return { ...id, scale: util.lerp(1, 1.14, e), op: util.clamp(p * 3, 0, 1) };
        case "zoomOut": return { ...id, scale: util.lerp(1.14, 1, e), op: util.clamp(p * 3, 0, 1) };
        case "panR":    return { ...id, dx: util.lerp(-40, 40, e), scale: 1.08 };
        case "panL":    return { ...id, dx: util.lerp(40, -40, e), scale: 1.08 };
        case "panU":    return { ...id, dy: util.lerp(40, -40, e), scale: 1.08 };
        case "slideIn": return { ...id, dx: util.lerp(70, 0, e), op: e };
        case "riseIn":  return { ...id, dy: util.lerp(40, 0, e), op: e };
        case "spin": {  const r = (a.loop ? (t / dur) : e) * 360; return { ...id, rot: r % 360 }; }
        case "pulse": { const ph = Math.sin((a.loop ? t : t) * Math.PI * 2 / (a.dur || 2)); return { ...id, scale: 1 + ph * 0.05 }; }
        case "float": { const ph = Math.sin(t * Math.PI * 2 / (a.dur || 3)); return { ...id, dy: ph * 14 }; }
        default: return id;
      }
    },

    applyFrame(t) {
      this.doc.layers.forEach((l) => {
        const n = this.els.get(l.id); if (!n) return;
        const fr = this._animFrame(l, t);
        n.style.transform = `translate(${l.x + fr.dx}px, ${l.y + fr.dy}px) rotate(${l.rot + fr.rot}deg) scale(${fr.scale})`;
        n.style.opacity = l.opacity * fr.op;
      });
    },

    play() {
      if (this.state.playing) return;
      this.state.playing = true;
      this.els.forEach((n) => n.classList.remove("selected"));
      this.state.last = performance.now();
      const loop = (now) => {
        if (!this.state.playing) return;
        const dt = (now - this.state.last) / 1000; this.state.last = now;
        this.state.time += dt;
        if (this.state.time >= this.doc.duration) this.state.time = 0; // loop preview
        this.applyFrame(this.state.time);
        this._changed();
        this.state.raf = requestAnimationFrame(loop);
      };
      this.state.raf = requestAnimationFrame(loop);
      this._changed();
    },
    pause() {
      this.state.playing = false;
      cancelAnimationFrame(this.state.raf);
      this.render();
      this._changed();
    },
    stop() {
      this.state.playing = false;
      cancelAnimationFrame(this.state.raf);
      this.state.time = 0;
      this.render();
      this._changed();
    },
    seek(t) {
      this.state.time = util.clamp(t, 0, this.doc.duration);
      if (this.state.playing) this.applyFrame(this.state.time);
      else { /* preview the scrubbed frame */ this.applyFrame(this.state.time); }
      this._changed();
    },

    /* -- history -- */
    snapshot() {
      this.history.push(util.deep({ layers: this.doc.layers, grade: this.doc.grade, duration: this.doc.duration }));
      if (this.history.length > 40) this.history.shift();
    },
    undo() {
      const prev = this.history.pop();
      if (!prev) return false;
      this.doc.layers = prev.layers; this.doc.grade = prev.grade; this.doc.duration = prev.duration;
      this.els.forEach((n) => n.remove()); this.els.clear();
      this.select(null); this.render(); this._changed();
      return true;
    },
  });
})();
