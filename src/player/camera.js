// =====================================================================
// camera.js — third-person orbit camera.
//
// Orbits a target (the hero's head), supports mouse-look + wheel zoom, lifts
// itself above the ground so it never clips into hills, and hands movement
// basis vectors (forward / right on the XZ plane) to the character so walking
// is always relative to where you're looking.
// =====================================================================

import * as THREE from "three";
import { heightAt } from "../world/heightfield.js";

const clamp = THREE.MathUtils.clamp;

export class ThirdPersonCamera {
  constructor(camera) {
    this.camera = camera;
    this.yaw = Math.PI;
    this.pitch = 0.42;
    this.distance = 9;
    this.targetDistance = 9;
    this.headOffset = 1.5;

    this.target = new THREE.Vector3();
    this._desired = new THREE.Vector3();
    this._off = new THREE.Vector3();
  }

  rotate(dx, dy, sens = 0.0023) {
    this.yaw -= dx * sens;
    this.pitch = clamp(this.pitch + dy * sens, -0.2, 1.32);
  }

  zoom(wheel) {
    this.targetDistance = clamp(this.targetDistance + wheel * 0.012, 3, 24);
  }

  // Movement basis on the ground plane.
  forward(out) {
    return out.set(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
  }
  right(out) {
    return out.set(Math.cos(this.yaw), 0, -Math.sin(this.yaw));
  }

  update(playerPos, dt) {
    this.distance += (this.targetDistance - this.distance) * Math.min(1, dt * 12);

    // Smoothly follow the hero's head.
    this._desired.set(playerPos.x, playerPos.y + this.headOffset, playerPos.z);
    this.target.lerp(this._desired, Math.min(1, dt * 14));

    const cp = Math.cos(this.pitch);
    this._off.set(
      Math.sin(this.yaw) * cp,
      Math.sin(this.pitch),
      Math.cos(this.yaw) * cp
    ).multiplyScalar(this.distance);

    const camPos = this._off.add(this.target);

    // Don't let the camera sink into the terrain.
    const groundY = heightAt(camPos.x, camPos.z) + 1.3;
    if (camPos.y < groundY) camPos.y = groundY;

    this.camera.position.copy(camPos);
    this.camera.lookAt(this.target);
  }
}
