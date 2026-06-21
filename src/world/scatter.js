// =====================================================================
// scatter.js — deterministic vegetation & rocks for each terrain chunk.
//
// Props are placed from a per-chunk seeded RNG, so a chunk always grows the
// same forest whether you see it for the first or the hundredth time.
// Everything is drawn with InstancedMesh, so thousands of trees cost only a
// handful of draw calls.
// =====================================================================

import * as THREE from "three";
import { mulberry32, hash2, Noise2D } from "./noise.js";
import {
  heightAt,
  normalAt,
  WATER_LEVEL,
  SNOW_LINE,
  SEED,
} from "./heightfield.js";

const forestNoise = new Noise2D(SEED + 555);

// ---- Shared geometry (created once, instanced everywhere) ----
const trunkGeo = new THREE.CylinderGeometry(0.32, 0.5, 4.2, 6);
trunkGeo.translate(0, 2.1, 0);

const foliageGeo = new THREE.ConeGeometry(2.7, 8.5, 7);
foliageGeo.translate(0, 6.4, 0);

const broadGeo = new THREE.IcosahedronGeometry(3.0, 0); // rounded "broadleaf" canopy
broadGeo.translate(0, 6.0, 0);

const rockGeo = new THREE.IcosahedronGeometry(1.0, 0);
const grassGeo = new THREE.ConeGeometry(0.14, 0.8, 4);
grassGeo.translate(0, 0.4, 0);

// ---- Shared materials ----
const trunkMat = new THREE.MeshStandardMaterial({ color: 0x6b4a2f, roughness: 1 });
const foliageMat = new THREE.MeshStandardMaterial({ roughness: 1, flatShading: true });
const rockMat = new THREE.MeshStandardMaterial({ color: 0x7d776c, roughness: 1, flatShading: true });
const grassMat = new THREE.MeshStandardMaterial({ color: 0x6fa83c, roughness: 1 });

const _m = new THREE.Object3D();
const _c = new THREE.Color();

const FOLIAGE_TONES = [0x4f7f33, 0x3f6e2c, 0x5f8a3a, 0x6f7a2d, 0x86913a];

export class Scatter {
  /**
   * Build all props for one chunk.
   * @returns {THREE.Group|null} group of instanced meshes, or null if empty.
   */
  populate(cx, cz, size) {
    const rng = mulberry32(hash2(cx + 4096, cz + 4096));
    const half = size / 2;
    const ox = cx * size;
    const oz = cz * size;

    const trees = []; // { m: Matrix4, broad: bool, color: int }
    const rocks = [];
    const grass = [];

    // ---- Trees ----
    for (let i = 0; i < 70; i++) {
      const x = ox + (rng() * 2 - 1) * half;
      const z = oz + (rng() * 2 - 1) * half;
      const h = heightAt(x, z);
      if (h < WATER_LEVEL + 1.8 || h > SNOW_LINE - 4) continue;
      if (1 - normalAt(x, z)[1] > 0.34) continue; // too steep

      // Cluster trees into forests using a smooth density field.
      const density = forestNoise.fbm(x * 0.0023, z * 0.0023, 3) * 0.5 + 0.5;
      if (rng() > density * density * 1.15) continue;

      const broad = rng() > 0.62;
      const s = 0.75 + rng() * 0.9;
      _m.position.set(x, h - 0.4, z);
      _m.rotation.set(0, rng() * Math.PI * 2, 0);
      _m.scale.set(s, s * (0.9 + rng() * 0.5), s);
      _m.updateMatrix();
      trees.push({
        m: _m.matrix.clone(),
        broad,
        color: FOLIAGE_TONES[(rng() * FOLIAGE_TONES.length) | 0],
      });
    }

    // ---- Rocks ----
    for (let i = 0; i < 26; i++) {
      const x = ox + (rng() * 2 - 1) * half;
      const z = oz + (rng() * 2 - 1) * half;
      const h = heightAt(x, z);
      if (h < WATER_LEVEL - 1) continue;
      if (rng() > 0.5) continue;
      const s = 0.5 + rng() * 2.4;
      _m.position.set(x, h - 0.2 + s * 0.2, z);
      _m.rotation.set(rng() * 3, rng() * 6, rng() * 3);
      _m.scale.set(s, s * (0.6 + rng() * 0.6), s);
      _m.updateMatrix();
      rocks.push(_m.matrix.clone());
    }

    // ---- Grass tufts ----
    for (let i = 0; i < 200; i++) {
      const x = ox + (rng() * 2 - 1) * half;
      const z = oz + (rng() * 2 - 1) * half;
      const h = heightAt(x, z);
      if (h < WATER_LEVEL + 1.2 || h > 50) continue;
      if (1 - normalAt(x, z)[1] > 0.22) continue;
      const s = 0.7 + rng() * 1.6;
      _m.position.set(x, h, z);
      _m.rotation.set(0, rng() * Math.PI, 0);
      _m.scale.set(s, s, s);
      _m.updateMatrix();
      grass.push(_m.matrix.clone());
    }

    if (!trees.length && !rocks.length && !grass.length) return null;

    const group = new THREE.Group();

    if (trees.length) {
      const trunks = new THREE.InstancedMesh(trunkGeo, trunkMat, trees.length);
      // Two canopy meshes share the same transforms but different geometry.
      const cones = [];
      const balls = [];
      trees.forEach((t) => (t.broad ? balls : cones).push(t));

      trees.forEach((t, i) => trunks.setMatrixAt(i, t.m));
      trunks.castShadow = true;
      trunks.instanceMatrix.needsUpdate = true;
      group.add(trunks);

      const addCanopy = (geo, list) => {
        if (!list.length) return;
        const mesh = new THREE.InstancedMesh(geo, foliageMat, list.length);
        list.forEach((t, i) => {
          mesh.setMatrixAt(i, t.m);
          mesh.setColorAt(i, _c.setHex(t.color));
        });
        mesh.castShadow = true;
        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        group.add(mesh);
      };
      addCanopy(foliageGeo, cones);
      addCanopy(broadGeo, balls);
    }

    if (rocks.length) {
      const rmesh = new THREE.InstancedMesh(rockGeo, rockMat, rocks.length);
      rocks.forEach((m, i) => rmesh.setMatrixAt(i, m));
      rmesh.castShadow = true;
      rmesh.receiveShadow = true;
      rmesh.instanceMatrix.needsUpdate = true;
      group.add(rmesh);
    }

    if (grass.length) {
      const gmesh = new THREE.InstancedMesh(grassGeo, grassMat, grass.length);
      grass.forEach((m, i) => gmesh.setMatrixAt(i, m));
      gmesh.instanceMatrix.needsUpdate = true;
      group.add(gmesh);
    }

    return group;
  }
}
