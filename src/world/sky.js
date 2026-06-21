// =====================================================================
// sky.js — dynamic sky dome, sun, lighting and a day/night cycle.
//
// Owns: a gradient sky shader with a real sun disk, a shadow-casting
// directional "sun" light that follows the player, hemisphere + ambient
// fill, a star field that fades in at night, and per-frame fog colour so
// the horizon always matches the sky.
// =====================================================================

import * as THREE from "three";

const sstep = THREE.MathUtils.smoothstep;

// Colour keyframes.
const DAY_TOP = new THREE.Color(0x2f6fdf);
const DAY_HORIZON = new THREE.Color(0xaecbe6);
const NIGHT_TOP = new THREE.Color(0x05070f);
const NIGHT_HORIZON = new THREE.Color(0x0c1326);
const SUNSET = new THREE.Color(0xff7a3c);
const SUN_WARM = new THREE.Color(0xffb066);
const SUN_WHITE = new THREE.Color(0xfff4e0);

export class Sky {
  constructor(scene) {
    this.scene = scene;
    this.t = 0.3; // time of day: 0 midnight, 0.25 sunrise, 0.5 noon, 0.75 sunset
    this.dayLength = 220; // seconds per full cycle
    this.paused = false;

    this.sunDir = new THREE.Vector3(0, 1, 0);
    this.dayFactor = 1;

    // --- Sky dome ---
    this.uniforms = {
      uTop: { value: new THREE.Color() },
      uBottom: { value: new THREE.Color() },
      uSunDir: { value: new THREE.Vector3() },
      uSunColor: { value: new THREE.Color() },
    };
    const skyMat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      depthWrite: false,
      uniforms: this.uniforms,
      vertexShader: /* glsl */ `
        varying vec3 vDir;
        void main() {
          vDir = position;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        varying vec3 vDir;
        uniform vec3 uTop, uBottom, uSunDir, uSunColor;
        void main() {
          vec3 dir = normalize(vDir);
          float h = clamp(dir.y * 0.5 + 0.5, 0.0, 1.0);
          vec3 col = mix(uBottom, uTop, pow(h, 0.55));
          float s = max(dot(dir, normalize(uSunDir)), 0.0);
          col += uSunColor * pow(s, 360.0) * 1.6;  // crisp sun disk
          col += uSunColor * pow(s, 6.0) * 0.20;   // soft glow
          gl_FragColor = vec4(col, 1.0);
        }`,
    });
    this.dome = new THREE.Mesh(new THREE.SphereGeometry(5000, 32, 16), skyMat);
    this.dome.renderOrder = -1;
    this.dome.frustumCulled = false;
    scene.add(this.dome);

    // --- Stars ---
    const starCount = 1400;
    const sp = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount; i++) {
      const v = new THREE.Vector3()
        .randomDirection()
        .multiplyScalar(4600);
      if (v.y < 0) v.y = -v.y; // keep them above the horizon
      sp.set([v.x, v.y, v.z], i * 3);
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute("position", new THREE.BufferAttribute(sp, 3));
    this.starMat = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 2.2,
      sizeAttenuation: false,
      transparent: true,
      opacity: 0,
      depthWrite: false,
    });
    this.stars = new THREE.Points(starGeo, this.starMat);
    this.stars.renderOrder = -1;
    this.stars.frustumCulled = false;
    scene.add(this.stars);

    // --- Lights ---
    this.sun = new THREE.DirectionalLight(0xffffff, 2.4);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    const sc = this.sun.shadow.camera;
    sc.left = -200; sc.right = 200; sc.top = 200; sc.bottom = -200;
    sc.near = 10; sc.far = 620;
    sc.updateProjectionMatrix();
    this.sun.shadow.bias = -0.0004;
    this.sun.shadow.normalBias = 0.7;
    scene.add(this.sun);
    scene.add(this.sun.target);

    this.hemi = new THREE.HemisphereLight(0xbcd6ff, 0x55503f, 0.7);
    scene.add(this.hemi);
    this.ambient = new THREE.AmbientLight(0xffffff, 0.18);
    scene.add(this.ambient);
  }

  update(dt, playerPos, camera) {
    if (!this.paused) {
      this.t = (this.t + dt / this.dayLength) % 1;
      if (this.t < 0) this.t += 1;
    }

    const ang = (this.t - 0.25) * Math.PI * 2;
    const sx = Math.cos(ang);
    const sy = Math.sin(ang);
    this.sunDir.set(sx, sy, 0.32).normalize();

    const day = sstep(sy, -0.05, 0.22); // 0 night → 1 day
    this.dayFactor = day;

    // Warm band when the sun is near the horizon (dawn/dusk).
    const nearHoriz = 1 - Math.min(1, Math.abs(sy) / 0.32);
    const notDeepNight = sstep(sy, -0.22, 0.02);
    const warm = nearHoriz * notDeepNight;

    const top = this.uniforms.uTop.value;
    const bottom = this.uniforms.uBottom.value;
    top.copy(NIGHT_TOP).lerp(DAY_TOP, day);
    bottom.copy(NIGHT_HORIZON).lerp(DAY_HORIZON, day);
    bottom.lerp(SUNSET, warm * 0.8);

    const sunColor = this.uniforms.uSunColor.value;
    sunColor.copy(SUN_WARM).lerp(SUN_WHITE, day);
    this.uniforms.uSunDir.value.copy(this.sunDir);

    // Fog tracks the horizon so distant land melts into the sky.
    if (this.scene.fog) this.scene.fog.color.copy(bottom);
    this.scene.background = bottom;

    // Lights.
    this.sun.color.copy(sunColor);
    this.sun.intensity = day * 2.6;
    this.hemi.intensity = 0.25 + day * 0.55;
    this.hemi.color.copy(bottom).lerp(new THREE.Color(0xbcd6ff), 0.5);
    this.ambient.intensity = 0.12 + day * 0.08;
    this.starMat.opacity = THREE.MathUtils.clamp(1 - day * 1.5, 0, 1) * 0.9;

    // Follow the player/camera so everything feels limitless.
    this.dome.position.copy(camera.position);
    this.stars.position.copy(camera.position);
    this.sun.position.copy(playerPos).addScaledVector(this.sunDir, 240);
    this.sun.target.position.copy(playerPos);
    this.sun.target.updateMatrixWorld();
  }

  clockString() {
    const minutes = Math.floor(this.t * 24 * 60);
    const hh = String(Math.floor(minutes / 60)).padStart(2, "0");
    const mm = String(minutes % 60).padStart(2, "0");
    return `${hh}:${mm}`;
  }
}
