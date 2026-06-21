// =====================================================================
// noise.js — seedable 2D simplex noise + fractal helpers.
//
// Everything in Aetherion's terrain comes from these functions. Because
// the noise is deterministic for a given seed, the same world coordinates
// always produce the same land — which is what lets us stream an
// effectively infinite world without ever storing it.
// =====================================================================

// Small, fast seedable PRNG (Mulberry32).
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Deterministic 2D integer hash → 32-bit seed (used for per-chunk RNG).
export function hash2(x, y) {
  let h = (x | 0) * 374761393 + (y | 0) * 668265263;
  h = (h ^ (h >>> 13)) * 1274126177;
  return (h ^ (h >>> 16)) >>> 0;
}

// 12 gradient directions (only x,y used in 2D; z kept for the classic layout).
const GRAD = new Float32Array([
  1, 1, 0, -1, 1, 0, 1, -1, 0, -1, -1, 0,
  1, 0, 1, -1, 0, 1, 1, 0, -1, -1, 0, -1,
  0, 1, 1, 0, -1, 1, 0, 1, -1, 0, -1, -1,
]);

const F2 = 0.5 * (Math.sqrt(3) - 1);
const G2 = (3 - Math.sqrt(3)) / 6;

export class Noise2D {
  constructor(seed = 1337) {
    const rand = mulberry32(seed);
    const p = new Uint8Array(256);
    for (let i = 0; i < 256; i++) p[i] = i;
    // Fisher–Yates shuffle for a seed-dependent permutation table.
    for (let i = 255; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1));
      const t = p[i];
      p[i] = p[j];
      p[j] = t;
    }
    this.perm = new Uint8Array(512);
    this.permMod12 = new Uint8Array(512);
    for (let i = 0; i < 512; i++) {
      this.perm[i] = p[i & 255];
      this.permMod12[i] = this.perm[i] % 12;
    }
  }

  // Classic 2D simplex noise, output roughly in [-1, 1].
  noise(xin, yin) {
    const perm = this.perm;
    const permMod12 = this.permMod12;
    let n0 = 0, n1 = 0, n2 = 0;

    const s = (xin + yin) * F2;
    const i = Math.floor(xin + s);
    const j = Math.floor(yin + s);
    const t = (i + j) * G2;
    const x0 = xin - (i - t);
    const y0 = yin - (j - t);

    let i1, j1;
    if (x0 > y0) { i1 = 1; j1 = 0; } else { i1 = 0; j1 = 1; }

    const x1 = x0 - i1 + G2;
    const y1 = y0 - j1 + G2;
    const x2 = x0 - 1 + 2 * G2;
    const y2 = y0 - 1 + 2 * G2;

    const ii = i & 255;
    const jj = j & 255;

    let tt = 0.5 - x0 * x0 - y0 * y0;
    if (tt >= 0) {
      const gi = permMod12[ii + perm[jj]] * 3;
      tt *= tt;
      n0 = tt * tt * (GRAD[gi] * x0 + GRAD[gi + 1] * y0);
    }
    tt = 0.5 - x1 * x1 - y1 * y1;
    if (tt >= 0) {
      const gi = permMod12[ii + i1 + perm[jj + j1]] * 3;
      tt *= tt;
      n1 = tt * tt * (GRAD[gi] * x1 + GRAD[gi + 1] * y1);
    }
    tt = 0.5 - x2 * x2 - y2 * y2;
    if (tt >= 0) {
      const gi = permMod12[ii + 1 + perm[jj + 1]] * 3;
      tt *= tt;
      n2 = tt * tt * (GRAD[gi] * x2 + GRAD[gi + 1] * y2);
    }
    return 70 * (n0 + n1 + n2);
  }

  // Fractal Brownian motion — layered octaves for natural detail. ~[-1, 1].
  fbm(x, y, octaves = 4, lacunarity = 2.0, gain = 0.5) {
    let amp = 1, freq = 1, sum = 0, norm = 0;
    for (let o = 0; o < octaves; o++) {
      sum += amp * this.noise(x * freq, y * freq);
      norm += amp;
      amp *= gain;
      freq *= lacunarity;
    }
    return sum / norm;
  }

  // Ridged multifractal — sharp mountain ridges. ~[0, 1].
  ridged(x, y, octaves = 5, lacunarity = 2.0, gain = 0.5) {
    let amp = 1, freq = 1, sum = 0, norm = 0;
    for (let o = 0; o < octaves; o++) {
      const n = 1 - Math.abs(this.noise(x * freq, y * freq));
      sum += amp * n * n;
      norm += amp;
      amp *= gain;
      freq *= lacunarity;
    }
    return sum / norm;
  }
}
