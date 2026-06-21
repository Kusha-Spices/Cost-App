// =====================================================================
// main.js — bootstrap + game loop.
//
// Creates the renderer/scene, wires the world, sky, water, hero, camera,
// input and HUD together, manages the start/pause overlay, and drives the
// per-frame update → render loop.
// =====================================================================

import * as THREE from "three";
import { World } from "./world/terrain.js";
import { Sky } from "./world/sky.js";
import { Water } from "./world/water.js";
import { Character } from "./player/character.js";
import { ThirdPersonCamera } from "./player/camera.js";
import { Input } from "./core/input.js";
import { HUD } from "./ui/hud.js";

function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch (e) {
    return false;
  }
}

if (!webglAvailable()) {
  document.getElementById("nosupport").classList.remove("hidden");
  document.getElementById("overlay").classList.add("hidden");
} else {
  boot();
}

function boot() {
  const container = document.getElementById("game");

  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  // Slightly thick fog so the streaming horizon dissolves into mist
  // instead of showing a hard edge where chunks stop loading.
  scene.fog = new THREE.FogExp2(0x9ec3e0, 0.0030);

  const camera = new THREE.PerspectiveCamera(62, window.innerWidth / window.innerHeight, 0.1, 8000);

  const world = new World(scene);
  const sky = new Sky(scene);
  const water = new Water(scene);
  const character = new Character(scene);
  character.spawn();

  const tpc = new ThirdPersonCamera(camera);
  const input = new Input(renderer.domElement);
  const hud = new HUD();
  hud.onSwitch = (i) => { character.switchTo(i); hud.setActive(i); };

  // Eagerly build the neighbourhood around spawn so we never start in a void.
  world.update(character.position.x, character.position.z);
  for (let k = 0; k < 10; k++) world.processQueue(40);
  tpc.update(character.position, 0.016);

  // ---------- Overlay / pause ----------
  const overlay = document.getElementById("overlay");
  const loadingRow = document.getElementById("loading-row");
  const startControls = document.getElementById("start-controls");
  const startBtn = document.getElementById("start-btn");
  const hudEl = document.getElementById("hud");

  let started = false;
  let paused = false;

  const pauseHint = document.createElement("div");
  pauseHint.textContent = "Paused — click to resume";
  pauseHint.style.cssText =
    "position:fixed;inset:0;z-index:40;display:none;align-items:center;justify-content:center;" +
    "background:rgba(5,7,13,0.55);color:#ffe9a8;font-size:20px;letter-spacing:3px;backdrop-filter:blur(3px);";
  document.body.appendChild(pauseHint);

  function waitForSpawn() {
    if (world.ready(character.position.x, character.position.z)) {
      loadingRow.classList.add("hidden");
      startControls.classList.remove("hidden");
    } else {
      world.processQueue(12);
      requestAnimationFrame(waitForSpawn);
    }
  }
  waitForSpawn();

  startBtn.addEventListener("click", () => {
    started = true;
    overlay.classList.add("fade");
    setTimeout(() => overlay.classList.add("hidden"), 600);
    hudEl.classList.remove("hidden");
    input.requestLock();
  });

  input.onLockChange((locked) => {
    if (!started) return;
    paused = !locked;
    pauseHint.style.display = locked ? "none" : "flex";
  });

  renderer.domElement.addEventListener("click", () => {
    if (started && !input.locked) input.requestLock();
  });

  window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  // ---------- Loop ----------
  const clock = new THREE.Clock();
  let fps = 60;

  function frame() {
    requestAnimationFrame(frame);
    const dt = Math.min(clock.getDelta(), 0.05);

    if (started && !paused) {
      if (input.wheel) tpc.zoom(input.wheel);
      tpc.rotate(input.mx, input.my);
      character.update(dt, input, tpc);
      if (input.wasPressed("Digit1")) { character.switchTo(0); hud.setActive(0); }
      if (input.wasPressed("Digit2")) { character.switchTo(1); hud.setActive(1); }
      if (input.wasPressed("Digit3")) { character.switchTo(2); hud.setActive(2); }
    }
    input.endFrame();

    tpc.update(character.position, dt);
    world.update(character.position.x, character.position.z);
    world.processQueue(2);
    sky.update(dt, character.position, camera);
    water.update(dt, camera, sky);

    fps += ((dt > 0 ? 1 / dt : 60) - fps) * 0.08;
    if (started) hud.update(dt, character, sky.clockString(), fps);

    renderer.render(scene, camera);
  }
  frame();
}
