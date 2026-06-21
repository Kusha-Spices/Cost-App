// =====================================================================
// heightfield.js — the shape of the world.
//
// `heightAt(x, z)` is the single source of truth for elevation. The terrain
// mesh, the player's footing, the water, props and the minimap all read from
// it, so the world is always self-consistent no matter where you wander.
// =====================================================================

import { Noise2D } from "./noise.js";

export const SEED = 20260621;
export const WATER_LEVEL = 4.0;
export const SNOW_LINE = 72.0;

const base = new Noise2D(SEED);
const warp = new Noise2D(SEED + 9171);

// Biome region IDs (also used for naming the area in the HUD).
export const Biome = {
  OCEAN: 0,
  BEACH: 1,
  PLAINS: 2,
  FOREST: 3,
  HIGHLANDS: 4,
  PEAKS: 5,
};

export const BIOME_NAMES = [
  "Azure Sea",
  "Golden Shore",
  "Windswept Plains",
  "Whispering Woods",
  "Dragonspine Highlands",
  "Frostpeak Summit",
];

/**
 * Elevation in world units at world coordinate (x, z).
 * Combines continents, rolling hills, ridged mountains and fine detail,
 * with domain warping so coastlines and ranges look organic rather than grid-like.
 */
export function heightAt(x, z) {
  // Domain warp — push the sample point around to break up regular patterns.
  const wxn = warp.fbm(x * 0.0014, z * 0.0014, 2);
  const wzn = warp.fbm(x * 0.0014 + 5.7, z * 0.0014 - 3.1, 2);
  const wx = x + wxn * 70;
  const wz = z + wzn * 70;

  // Continents: large, slow undulation deciding land vs. sea.
  const continent = base.fbm(wx * 0.00085, wz * 0.00085, 4);

  // Rolling hills at a medium scale.
  const hills = base.fbm(wx * 0.0065, wz * 0.0065, 4);

  // Ridged mountains, only allowed to rise where the continent is high.
  const ridge = base.ridged(wx * 0.0034, wz * 0.0034, 5);
  const mountainMask = Math.max(0, continent + 0.05);

  // Assemble.
  let h = (continent + 0.28) * 42; // bias upward → more land than ocean
  h += hills * 13;
  h += Math.pow(ridge, 2.1) * mountainMask * 135;

  // Flatten shallow land a touch near the waterline for nicer beaches.
  if (h > WATER_LEVEL - 3 && h < WATER_LEVEL + 6) {
    h = WATER_LEVEL + (h - WATER_LEVEL) * 0.7;
  }

  // Fine surface detail.
  h += base.fbm(wx * 0.03, wz * 0.03, 3) * 2.3;

  return h;
}

/** Surface normal via finite differences. Returns a unit [nx, ny, nz]. */
export function normalAt(x, z, eps = 1.3) {
  const hL = heightAt(x - eps, z);
  const hR = heightAt(x + eps, z);
  const hD = heightAt(x, z - eps);
  const hU = heightAt(x, z + eps);
  let nx = hL - hR;
  let ny = 2 * eps;
  let nz = hD - hU;
  const inv = 1 / (Math.hypot(nx, ny, nz) || 1);
  return [nx * inv, ny * inv, nz * inv];
}

/** 0 = perfectly flat ground, →1 = a vertical cliff. */
export function slopeAt(x, z) {
  return 1 - normalAt(x, z)[1];
}

/** Classify the terrain at a point into a Biome id (used for naming + props). */
export function biomeAt(x, z) {
  const h = heightAt(x, z);
  if (h < WATER_LEVEL - 0.5) return Biome.OCEAN;
  if (h < WATER_LEVEL + 1.6) return Biome.BEACH;
  if (h > SNOW_LINE) return Biome.PEAKS;
  if (h > 46) return Biome.HIGHLANDS;
  // Forest vs. open plains decided by a slow moisture field.
  const moist = base.fbm(x * 0.0021 + 100, z * 0.0021 - 40, 3);
  return moist > 0.05 ? Biome.FOREST : Biome.PLAINS;
}
