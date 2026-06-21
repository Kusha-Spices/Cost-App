// =====================================================================
// water.js — a large animated ocean/lake surface at sea level.
//
// One big plane that re-centres on the camera every frame (so it reaches the
// horizon in all directions). Waves are computed in world space in the
// vertex shader, so the surface stays put in the world while the mesh slides
// under the camera — no "swimming texture" artefacts.
// =====================================================================

import * as THREE from "three";
import { WATER_LEVEL } from "./heightfield.js";

export class Water {
  constructor(scene) {
    this.uniforms = {
      uTime: { value: 0 },
      uSunDir: { value: new THREE.Vector3(0, 1, 0) },
      uSunColor: { value: new THREE.Color(0xffffff) },
      uCamPos: { value: new THREE.Vector3() },
      uDeep: { value: new THREE.Color(0x0e3a52) },
      uShallow: { value: new THREE.Color(0x2f86a6) },
      uDayFactor: { value: 1 },
    };

    const mat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      uniforms: this.uniforms,
      vertexShader: /* glsl */ `
        uniform float uTime;
        varying vec3 vWorldPos;
        varying vec3 vNormal;
        void main() {
          vec4 world = modelMatrix * vec4(position, 1.0);
          float wx = world.x, wz = world.z, t = uTime;

          float h = 0.0, dx = 0.0, dz = 0.0;
          h += sin(wx * 0.080 + t * 1.10) * 0.50; dx += cos(wx * 0.080 + t * 1.10) * 0.080 * 0.50;
          h += sin(wz * 0.130 - t * 0.90) * 0.35; dz += cos(wz * 0.130 - t * 0.90) * 0.130 * 0.35;
          float p = (wx + wz) * 0.050;
          h += sin(p + t * 0.70) * 0.45;
          dx += cos(p + t * 0.70) * 0.050 * 0.45;
          dz += cos(p + t * 0.70) * 0.050 * 0.45;

          world.y += h;
          vWorldPos = world.xyz;
          vNormal = normalize(vec3(-dx, 1.0, -dz));
          gl_Position = projectionMatrix * viewMatrix * world;
        }`,
      fragmentShader: /* glsl */ `
        uniform vec3 uSunDir, uSunColor, uDeep, uShallow, uCamPos;
        uniform float uDayFactor;
        varying vec3 vWorldPos;
        varying vec3 vNormal;
        void main() {
          vec3 N = normalize(vNormal);
          vec3 V = normalize(uCamPos - vWorldPos);
          float fres = pow(1.0 - max(dot(N, V), 0.0), 3.0);

          vec3 col = mix(uDeep, uShallow, clamp(fres + 0.18, 0.0, 1.0));
          col *= 0.35 + 0.65 * uDayFactor;       // darken at night

          vec3 H = normalize(normalize(uSunDir) + V);
          float spec = pow(max(dot(N, H), 0.0), 140.0);
          col += uSunColor * spec * 1.4 * uDayFactor;

          float alpha = 0.74 + fres * 0.24;
          gl_FragColor = vec4(col, alpha);
        }`,
    });

    const geo = new THREE.PlaneGeometry(2200, 2200, 150, 150);
    geo.rotateX(-Math.PI / 2);
    this.mesh = new THREE.Mesh(geo, mat);
    this.mesh.position.y = WATER_LEVEL;
    this.mesh.renderOrder = 1;
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
  }

  update(dt, camera, sky) {
    this.uniforms.uTime.value += dt;
    this.uniforms.uCamPos.value.copy(camera.position);
    this.uniforms.uSunDir.value.copy(sky.sunDir);
    this.uniforms.uSunColor.value.copy(sky.uniforms.uSunColor.value);
    this.uniforms.uDayFactor.value = sky.dayFactor;
    // Re-centre on the camera, snapped to whole units to avoid shimmering.
    this.mesh.position.x = Math.round(camera.position.x);
    this.mesh.position.z = Math.round(camera.position.z);
  }
}
