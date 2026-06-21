// =====================================================================
// terrain.js — streaming, "infinite" chunked terrain.
//
// The world is divided into square chunks. As the player moves we make sure
// every chunk within VIEW_RADIUS exists, building new ones a few per frame
// (so there's no stutter) and disposing chunks that fall behind. Because the
// height comes from heightAt(), chunks tile together seamlessly and the world
// stretches on forever in every direction.
// =====================================================================

import * as THREE from "three";
import {
  heightAt,
  normalAt,
  WATER_LEVEL,
  SNOW_LINE,
  SEED,
} from "./heightfield.js";
import { Noise2D } from "./noise.js";
import { Scatter } from "./scatter.js";

export const CHUNK_SIZE = 96;
const SEGMENTS = 36;
const VIEW_RADIUS = 5; // in chunks

const mottle = new Noise2D(SEED + 4242);

// Biome palette.
const C_SAND = new THREE.Color(0xcdba86);
const C_GRASS = new THREE.Color(0x5e8b3e);
const C_DRY = new THREE.Color(0x8a8a47);
const C_ROCK = new THREE.Color(0x6f685c);
const C_SNOW = new THREE.Color(0xeef2f7);
const C_MUD = new THREE.Color(0x584a32);

const sstep = THREE.MathUtils.smoothstep;
const _col = new THREE.Color();

function colorFor(h, slope, x, z, out) {
  if (h < WATER_LEVEL + 1.4) {
    out.copy(C_SAND);
    if (h < WATER_LEVEL - 0.4) out.lerp(C_MUD, sstep(h, WATER_LEVEL - 0.4, WATER_LEVEL - 8));
  } else {
    out.copy(C_GRASS).lerp(C_DRY, sstep(h, 20, 54));
  }
  const rockT = sstep(slope, 0.33, 0.66);
  out.lerp(C_ROCK, rockT);
  const snowT = sstep(h, SNOW_LINE - 6, SNOW_LINE + 12) * (1 - rockT * 0.45);
  out.lerp(C_SNOW, snowT);

  // Gentle mottling so large surfaces aren't flat-coloured.
  const v = 1 + mottle.noise(x * 0.08, z * 0.08) * 0.06;
  out.multiplyScalar(v);
}

export class World {
  constructor(scene) {
    this.scene = scene;
    this.chunks = new Map(); // key -> { mesh, props }
    this.pending = new Set(); // keys queued but not yet built
    this.queue = [];
    this.scatter = new Scatter();
    this.ccx = 0;
    this.ccz = 0;

    this.material = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.95,
      metalness: 0.0,
    });

    this.group = new THREE.Group();
    scene.add(this.group);
  }

  key(cx, cz) {
    return cx + "," + cz;
  }

  buildChunk(cx, cz) {
    const geo = new THREE.PlaneGeometry(CHUNK_SIZE, CHUNK_SIZE, SEGMENTS, SEGMENTS);
    geo.rotateX(-Math.PI / 2);

    const pos = geo.attributes.position;
    const count = pos.count;
    const normals = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const ox = cx * CHUNK_SIZE;
    const oz = cz * CHUNK_SIZE;

    for (let i = 0; i < count; i++) {
      const x = pos.getX(i) + ox;
      const z = pos.getZ(i) + oz;
      const h = heightAt(x, z);
      pos.setY(i, h);

      const n = normalAt(x, z);
      normals[i * 3] = n[0];
      normals[i * 3 + 1] = n[1];
      normals[i * 3 + 2] = n[2];

      colorFor(h, 1 - n[1], x, z, _col);
      colors[i * 3] = _col.r;
      colors[i * 3 + 1] = _col.g;
      colors[i * 3 + 2] = _col.b;
    }

    geo.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geo.computeBoundingSphere();

    const mesh = new THREE.Mesh(geo, this.material);
    mesh.position.set(ox, 0, oz);
    mesh.receiveShadow = true;
    this.group.add(mesh);

    const props = this.scatter.populate(cx, cz, CHUNK_SIZE);
    if (props) this.group.add(props);

    return { mesh, props };
  }

  disposeChunk(chunk) {
    if (!chunk) return;
    this.group.remove(chunk.mesh);
    chunk.mesh.geometry.dispose();
    if (chunk.props) {
      this.group.remove(chunk.props);
      chunk.props.traverse((o) => {
        if (o.isInstancedMesh) o.dispose();
      });
    }
  }

  /** Queue/keep chunks around (px, pz); drop the ones too far away. */
  update(px, pz) {
    const ccx = Math.round(px / CHUNK_SIZE);
    const ccz = Math.round(pz / CHUNK_SIZE);
    this.ccx = ccx;
    this.ccz = ccz;

    const R = VIEW_RADIUS;
    for (let dz = -R; dz <= R; dz++) {
      for (let dx = -R; dx <= R; dx++) {
        if (dx * dx + dz * dz > (R + 0.5) * (R + 0.5)) continue;
        const cx = ccx + dx;
        const cz = ccz + dz;
        const k = this.key(cx, cz);
        if (this.chunks.has(k) || this.pending.has(k)) continue;
        this.pending.add(k);
        // Sort so the nearest missing chunks build first.
        this.queue.push({ cx, cz, k, d: dx * dx + dz * dz });
      }
    }
    this.queue.sort((a, b) => a.d - b.d);

    // Remove chunks that have fallen outside the view radius.
    for (const [k, chunk] of this.chunks) {
      const [cx, cz] = k.split(",").map(Number);
      if (Math.hypot(cx - ccx, cz - ccz) > R + 1.5) {
        this.disposeChunk(chunk);
        this.chunks.delete(k);
      }
    }
  }

  /** Build a bounded number of queued chunks; call once per frame. */
  processQueue(maxPerFrame = 2) {
    let built = 0;
    while (this.queue.length && built < maxPerFrame) {
      const job = this.queue.shift();
      this.pending.delete(job.k);
      // Skip if it drifted out of range while waiting.
      if (Math.hypot(job.cx - this.ccx, job.cz - this.ccz) > VIEW_RADIUS + 1.5) continue;
      this.chunks.set(job.k, this.buildChunk(job.cx, job.cz));
      built++;
    }
    return built;
  }

  /** True once the chunk under (px, pz) is ready (used to gate the loading screen). */
  ready(px, pz) {
    const cx = Math.round(px / CHUNK_SIZE);
    const cz = Math.round(pz / CHUNK_SIZE);
    return this.chunks.has(this.key(cx, cz));
  }
}
