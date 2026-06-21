// =====================================================================
// hud.js — heads-up display: status panel, stamina, party switch, minimap.
//
// The minimap is rendered straight from heightAt() into a small offscreen
// canvas (a few times per second) and composited each frame with a rotating
// "you are here" arrow.
// =====================================================================

import { heightAt, WATER_LEVEL, SNOW_LINE, BIOME_NAMES } from "../world/heightfield.js";
import { PRESETS } from "../player/character.js";

const STATE_LABEL = {
  idle: "EXPLORING",
  walk: "WALKING",
  run: "SPRINTING",
  jump: "LEAPING",
  fall: "FALLING",
  glide: "GLIDING",
  swim: "SWIMMING",
  fly: "FLYING",
};

export class HUD {
  constructor() {
    this.biome = document.getElementById("biome");
    this.coords = document.getElementById("coords");
    this.altitude = document.getElementById("altitude");
    this.clock = document.getElementById("clock");
    this.fpsEl = document.getElementById("fps");
    this.staminaFill = document.getElementById("stamina-fill");
    this.stateLabel = document.getElementById("state-label");
    this.mapCoords = document.getElementById("map-coords");

    this.canvas = document.getElementById("minimap");
    this.ctx = this.canvas.getContext("2d");
    this.MS = 72; // offscreen sample resolution
    this.off = document.createElement("canvas");
    this.off.width = this.off.height = this.MS;
    this.offCtx = this.off.getContext("2d");
    this.img = this.offCtx.createImageData(this.MS, this.MS);
    this.mapSpan = 380; // world units shown across the minimap
    this.mapTimer = 1;

    this.onSwitch = null;
    this._buildParty();
  }

  _buildParty() {
    const party = document.getElementById("party");
    this.heroNodes = PRESETS.map((p, i) => {
      const el = document.createElement("div");
      el.className = "hero" + (i === 0 ? " active" : "");
      el.style.setProperty("--hero-color", p.hud);
      el.innerHTML =
        `<span class="num">${i + 1}</span>` +
        `<span class="glyph">${p.glyph}</span>` +
        `<span class="name">${p.key}</span>`;
      el.addEventListener("click", () => this.onSwitch && this.onSwitch(i));
      party.appendChild(el);
      return el;
    });
  }

  setActive(i) {
    this.heroNodes.forEach((n, k) => n.classList.toggle("active", k === i));
  }

  update(dt, character, clockStr, fps) {
    const info = character.describe();
    this.biome.textContent = BIOME_NAMES[info.biome];
    this.coords.textContent = `${info.x}, ${info.z}`;
    this.altitude.textContent = `${info.altitude} m`;
    this.clock.textContent = clockStr;
    this.fpsEl.textContent = Math.round(fps);
    this.mapCoords.textContent = `${info.x}, ${info.z}`;

    const pct = Math.round(info.stamina * 100);
    this.staminaFill.style.width = pct + "%";
    this.staminaFill.classList.toggle("low", info.stamina < 0.3);
    this.stateLabel.textContent = STATE_LABEL[info.state] || "EXPLORING";

    // Refresh the sampled map a few times per second.
    this.mapTimer += dt;
    if (this.mapTimer > 0.25) {
      this.mapTimer = 0;
      this._renderMap(character.position.x, character.position.z);
    }
    this._composite(character.facing);
  }

  _renderMap(px, pz) {
    const N = this.MS;
    const span = this.mapSpan;
    const step = span / N;
    const data = this.img.data;
    let o = 0;
    for (let j = 0; j < N; j++) {
      const wz = pz + (j - N / 2) * step;
      for (let i = 0; i < N; i++) {
        const wx = px + (i - N / 2) * step;
        const h = heightAt(wx, wz);
        let r, g, b;
        if (h < WATER_LEVEL - 0.3) { r = 26; g = 70; b = 110; }
        else if (h < WATER_LEVEL + 1.4) { r = 196; g = 178; b = 130; }
        else if (h > SNOW_LINE) { r = 232; g = 238; b = 245; }
        else if (h > 46) { r = 120; g = 112; b = 100; }
        else {
          // grass, brightened slightly with altitude
          const t = Math.min(1, (h - WATER_LEVEL) / 44);
          r = 70 + t * 40; g = 120 + t * 20; b = 56 + t * 20;
        }
        data[o++] = r; data[o++] = g; data[o++] = b; data[o++] = 255;
      }
    }
    this.offCtx.putImageData(this.img, 0, 0);
  }

  _composite(facing) {
    const ctx = this.ctx;
    const W = this.canvas.width;
    ctx.imageSmoothingEnabled = true;
    ctx.clearRect(0, 0, W, W);
    ctx.drawImage(this.off, 0, 0, W, W);

    // Player marker (arrow) at the centre, pointing where the hero faces.
    const cx = W / 2, cy = W / 2;
    const fx = -Math.sin(facing), fz = -Math.cos(facing);
    const ang = Math.atan2(fz, fx);
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(ang + Math.PI / 2);
    ctx.fillStyle = "#ffe9a8";
    ctx.strokeStyle = "rgba(0,0,0,0.5)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(0, -8);
    ctx.lineTo(5, 6);
    ctx.lineTo(0, 3);
    ctx.lineTo(-5, 6);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();

    // Cardinal "N".
    ctx.fillStyle = "rgba(255,255,255,0.7)";
    ctx.font = "bold 11px Segoe UI, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("N", cx, 13);
  }
}
