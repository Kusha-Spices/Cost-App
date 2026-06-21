// =====================================================================
// character.js — the playable hero: model, animation and movement.
//
// Builds a stylised humanoid from primitives (no external assets needed),
// offers three switchable "elemental" heroes, and runs the full controller:
// walk / sprint / jump / glide / swim / free-fly, with stamina, terrain
// following and a simple procedural walk animation.
// =====================================================================

import * as THREE from "three";
import { heightAt, WATER_LEVEL, biomeAt } from "../world/heightfield.js";

const clamp = THREE.MathUtils.clamp;

// Genshin-style elemental cast. `hud` drives the on-screen portrait glow.
export const PRESETS = [
  { key: "Anemo", glyph: "🌪️", body: 0x2fae8f, accent: 0xa8f0cf, hair: 0x123b33, hud: "#7ef0c2" },
  { key: "Pyro", glyph: "🔥", body: 0xd1492f, accent: 0xffc36b, hair: 0x3a140c, hud: "#ff9a6b" },
  { key: "Hydro", glyph: "💧", body: 0x3a6fd6, accent: 0x8fd6ff, hair: 0x101f48, hud: "#7fd1ff" },
];

// Tunables.
const GRAVITY = 22;
const WALK = 7;
const SPRINT = 13.5;
const SWIM = 5;
const FLY = 28;
const JUMP_V = 9.2;
const GLIDE_FALL = -2.1;
const STAMINA_MAX = 120;

function mat(color, rough = 0.8) {
  return new THREE.MeshStandardMaterial({ color, roughness: rough });
}

function lerpAngle(a, b, t) {
  let d = ((b - a + Math.PI) % (Math.PI * 2)) - Math.PI;
  if (d < -Math.PI) d += Math.PI * 2;
  return a + d * t;
}

export class Character {
  constructor(scene) {
    this.scene = scene;
    this.index = 0;

    this.position = new THREE.Vector3();
    this.velXZ = new THREE.Vector3();
    this.vy = 0;
    this.facing = Math.PI;
    this.phase = 0;

    this.grounded = false;
    this.swimming = false;
    this.gliding = false;
    this.fly = false;
    this.stamina = STAMINA_MAX;
    this.state = "idle";

    this.model = null;
    this.parts = null;
    this._build(PRESETS[this.index]);
  }

  get preset() {
    return PRESETS[this.index];
  }
  get staminaRatio() {
    return this.stamina / STAMINA_MAX;
  }

  // ---------------- Model ----------------
  _build(p) {
    const g = new THREE.Group();

    // Legs are parented to the root so the feet stay planted.
    const legGeo = new THREE.CapsuleGeometry(0.16, 0.62, 3, 6);
    const makeLeg = () => {
      const m = new THREE.Mesh(legGeo, mat(0x2a2f45));
      m.position.y = -0.42;
      m.castShadow = true;
      const pivot = new THREE.Group();
      pivot.add(m);
      return pivot;
    };
    const legL = makeLeg(); legL.position.set(-0.2, 1.0, 0); g.add(legL);
    const legR = makeLeg(); legR.position.set(0.2, 1.0, 0); g.add(legR);

    // Everything above the hips lives in a body pivot we can bob & tilt.
    const body = new THREE.Group();
    g.add(body);

    const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.42, 0.66, 4, 10), mat(p.body, 0.7));
    torso.position.y = 1.5; torso.castShadow = true; body.add(torso);

    const belt = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 0.16, 12), mat(p.accent, 0.5));
    belt.position.y = 1.15; body.add(belt);

    const head = new THREE.Mesh(new THREE.SphereGeometry(0.33, 20, 16), mat(0xf0c9a0, 0.6));
    head.position.y = 2.28; head.castShadow = true; body.add(head);

    const hair = new THREE.Mesh(
      new THREE.SphereGeometry(0.37, 18, 14, 0, Math.PI * 2, 0, Math.PI * 0.62),
      mat(p.hair, 0.7)
    );
    hair.position.y = 2.34; body.add(hair);

    const armGeo = new THREE.CapsuleGeometry(0.13, 0.62, 3, 6);
    const makeArm = () => {
      const m = new THREE.Mesh(armGeo, mat(p.accent));
      m.position.y = -0.42; m.castShadow = true;
      const pivot = new THREE.Group();
      pivot.add(m);
      return pivot;
    };
    const armL = makeArm(); armL.position.set(-0.56, 2.0, 0); body.add(armL);
    const armR = makeArm(); armR.position.set(0.56, 2.0, 0); body.add(armR);

    const cape = new THREE.Mesh(
      new THREE.PlaneGeometry(0.86, 1.15),
      new THREE.MeshStandardMaterial({ color: p.accent, side: THREE.DoubleSide, roughness: 0.6 })
    );
    cape.position.set(0, 1.5, -0.46); cape.rotation.x = 0.12; body.add(cape);

    // Wind-glider, hidden until you take to the air.
    const glider = new THREE.Group();
    const wingMat = new THREE.MeshStandardMaterial({ color: p.accent, side: THREE.DoubleSide, roughness: 0.5, metalness: 0.1 });
    const wingL = new THREE.Mesh(new THREE.PlaneGeometry(1.7, 1.15), wingMat);
    wingL.position.set(-0.9, 0, 0); wingL.rotation.set(-0.3, 0, 0.35);
    const wingR = wingL.clone(); wingR.position.x = 0.9; wingR.rotation.z = -0.35;
    const spar = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 3.2, 6), mat(p.hair, 0.4));
    spar.rotation.z = Math.PI / 2;
    glider.add(wingL, wingR, spar);
    glider.position.set(0, 2.6, -0.1);
    glider.visible = false;
    body.add(glider);

    this.parts = { root: g, body, torso, head, armL, armR, legL, legR, cape, glider };
    g.position.copy(this.position);
    g.rotation.y = this.facing;
    this.model = g;
    this.scene.add(g);
  }

  _disposeModel() {
    if (!this.model) return;
    this.scene.remove(this.model);
    this.model.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        const m = Array.isArray(o.material) ? o.material : [o.material];
        m.forEach((mm) => mm.dispose());
      }
    });
  }

  switchTo(i) {
    if (i === this.index || i < 0 || i >= PRESETS.length) return;
    this.index = i;
    this._disposeModel();
    this._build(PRESETS[i]);
  }

  // Find a pleasant dry spot near origin to start on.
  spawn() {
    let best = new THREE.Vector3(0, heightAt(0, 0), 0);
    for (let r = 0; r < 400; r += 12) {
      for (let a = 0; a < 8; a++) {
        const x = Math.cos(a) * r;
        const z = Math.sin(a) * r;
        const h = heightAt(x, z);
        if (h > WATER_LEVEL + 2 && h < 38) {
          this.position.set(x, h, z);
          this.parts.root.position.copy(this.position);
          return;
        }
      }
    }
    this.position.copy(best);
    this.parts.root.position.copy(this.position);
  }

  // ---------------- Controller ----------------
  update(dt, input, cam) {
    dt = Math.min(dt, 0.05); // clamp huge frames (e.g. tab refocus)

    // Movement intent relative to the camera.
    const f = cam.forward(new THREE.Vector3());
    const r = cam.right(new THREE.Vector3());
    const iz = (input.isDown("KeyW") ? 1 : 0) - (input.isDown("KeyS") ? 1 : 0);
    const ix = (input.isDown("KeyD") ? 1 : 0) - (input.isDown("KeyA") ? 1 : 0);
    const moveDir = f.multiplyScalar(iz).add(r.multiplyScalar(ix));
    const moving = moveDir.lengthSq() > 0.001;
    if (moving) moveDir.normalize();

    const sprintKey = input.isDown("ShiftLeft") || input.isDown("ShiftRight");

    if (input.wasPressed("KeyF")) {
      this.fly = !this.fly;
      this.vy = 0;
    }

    if (this.fly) {
      this._updateFly(dt, input, moveDir, moving);
    } else {
      this._updateGround(dt, input, moveDir, moving, sprintKey);
    }

    this._animate(dt, moving);

    // Push model to the world.
    this.parts.root.position.copy(this.position);
    this.facing = moving ? lerpAngle(this.facing, Math.atan2(-moveDir.x, -moveDir.z), Math.min(1, dt * 12)) : this.facing;
  }

  _updateFly(dt, input, moveDir, moving) {
    const boost = input.isDown("ShiftLeft") ? 2 : 1;
    this.velXZ.copy(moveDir).multiplyScalar(FLY * boost);
    let vy = 0;
    if (input.isDown("Space")) vy += FLY;
    if (input.isDown("ControlLeft") || input.isDown("KeyC")) vy -= FLY;
    this.position.addScaledVector(this.velXZ, dt);
    this.position.y += vy * dt;
    const floor = heightAt(this.position.x, this.position.z);
    if (this.position.y < floor + 0.5) this.position.y = floor + 0.5;
    this.grounded = false;
    this.swimming = false;
    this.gliding = false;
    this.state = "fly";
    this.stamina = Math.min(STAMINA_MAX, this.stamina + 30 * dt);
  }

  _updateGround(dt, input, moveDir, moving, sprintKey) {
    const floorBefore = heightAt(this.position.x, this.position.z);
    const heightAbove = this.position.y - floorBefore;

    const canSprint = sprintKey && moving && this.grounded && this.stamina > 0 && !this.swimming;
    const speed = this.swimming ? SWIM : canSprint ? SPRINT : WALK;

    // Smoothly accelerate toward the desired horizontal velocity.
    const targetV = moveDir.clone().multiplyScalar(moving ? speed : 0);
    this.velXZ.lerp(targetV, Math.min(1, dt * (this.grounded ? 12 : 4)));

    // Jump.
    if (input.wasPressed("Space") && this.grounded && !this.swimming) {
      this.vy = JUMP_V;
      this.grounded = false;
    }

    // Glide: hold Space while airborne and falling.
    this.gliding =
      !this.grounded &&
      input.isDown("Space") &&
      this.vy < 0.5 &&
      heightAbove > 3 &&
      this.stamina > 0 &&
      !this.swimming;

    // Gravity.
    this.vy -= GRAVITY * dt;
    if (this.gliding) {
      this.vy = Math.max(this.vy, GLIDE_FALL);
      this.velXZ.multiplyScalar(1.0); // keep momentum
    }

    // Integrate.
    this.position.addScaledVector(this.velXZ, dt);
    this.position.y += this.vy * dt;

    // Resolve against the ground / water.
    const floor = heightAt(this.position.x, this.position.z);
    const deepWater = floor < WATER_LEVEL - 1.2;

    if (deepWater && this.position.y < WATER_LEVEL + 0.2) {
      // Float at the surface and swim.
      const surf = WATER_LEVEL - 0.5;
      this.vy += (surf - this.position.y) * 6 * dt;
      this.vy *= 0.82;
      if (this.position.y < floor) { this.position.y = floor; this.vy = 0; }
      this.grounded = false;
      this.swimming = true;
    } else {
      this.swimming = false;
      if (this.position.y <= floor) {
        this.position.y = floor;
        this.vy = 0;
        this.grounded = true;
      } else {
        this.grounded = false;
      }
    }

    // Stamina.
    if (canSprint) this.stamina -= 18 * dt;
    else if (this.gliding) this.stamina -= 12 * dt;
    else this.stamina += 26 * dt;
    this.stamina = clamp(this.stamina, 0, STAMINA_MAX);

    // State (for HUD + animation).
    if (this.swimming) this.state = "swim";
    else if (this.gliding) this.state = "glide";
    else if (!this.grounded) this.state = this.vy > 0 ? "jump" : "fall";
    else if (moving) this.state = canSprint ? "run" : "walk";
    else this.state = "idle";
  }

  // ---------------- Animation ----------------
  _animate(dt, moving) {
    const P = this.parts;
    const s = this.state;
    const speed = this.velXZ.length();

    // Reset body tilt; specific states set it below.
    let bodyTiltX = 0;
    let bob = 0;

    P.glider.visible = s === "glide";

    if (s === "walk" || s === "run") {
      this.phase += dt * (6 + speed * 0.9);
      const amp = s === "run" ? 0.95 : 0.55;
      const sw = Math.sin(this.phase) * amp;
      P.armL.rotation.x = sw; P.armR.rotation.x = -sw;
      P.armL.rotation.z = 0; P.armR.rotation.z = 0;
      P.legL.rotation.x = -sw; P.legR.rotation.x = sw;
      bob = Math.abs(Math.sin(this.phase)) * 0.06;
      bodyTiltX = s === "run" ? 0.18 : 0.08;
    } else if (s === "glide") {
      this.phase += dt * 2;
      P.armL.rotation.set(0, 0, -1.35); P.armR.rotation.set(0, 0, 1.35);
      P.legL.rotation.x = 0.15; P.legR.rotation.x = -0.15;
      bodyTiltX = 0.5 + Math.sin(this.phase) * 0.03;
    } else if (s === "swim") {
      this.phase += dt * 5;
      const sw = Math.sin(this.phase);
      P.armL.rotation.set(sw * 0.8, 0, -0.7); P.armR.rotation.set(-sw * 0.8, 0, 0.7);
      P.legL.rotation.x = -sw * 0.5; P.legR.rotation.x = sw * 0.5;
      bodyTiltX = 1.1; // roughly horizontal
    } else if (s === "jump" || s === "fall" || s === "fly") {
      const t = s === "fly" ? 0.0 : 0.5;
      P.armL.rotation.set(0, 0, -0.5); P.armR.rotation.set(0, 0, 0.5);
      P.legL.rotation.x = t; P.legR.rotation.x = t * 0.6;
      bodyTiltX = s === "fly" ? 0.3 : 0;
    } else {
      // idle — gentle breathing, limbs ease back to rest.
      this.phase += dt * 1.6;
      const ease = Math.min(1, dt * 8);
      P.armL.rotation.x *= 1 - ease; P.armR.rotation.x *= 1 - ease;
      P.armL.rotation.z *= 1 - ease; P.armR.rotation.z *= 1 - ease;
      P.legL.rotation.x *= 1 - ease; P.legR.rotation.x *= 1 - ease;
      bob = Math.sin(this.phase) * 0.03;
    }

    P.body.position.y = bob;
    P.body.rotation.x += (bodyTiltX - P.body.rotation.x) * Math.min(1, dt * 10);
    this.parts.root.rotation.y = this.facing;
  }

  // ---------------- Info for HUD ----------------
  describe() {
    return {
      x: Math.round(this.position.x),
      z: Math.round(this.position.z),
      altitude: Math.round(this.position.y),
      biome: biomeAt(this.position.x, this.position.z),
      state: this.state,
      stamina: this.staminaRatio,
      preset: this.preset,
    };
  }
}
