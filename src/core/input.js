// =====================================================================
// input.js — keyboard + pointer-lock mouse input.
//
// Exposes held keys, edge-triggered presses (for toggles like 1/2/3/F),
// accumulated mouse-look delta and wheel. Call endFrame() once per frame
// after everything has read its input.
// =====================================================================

export class Input {
  constructor(domElement) {
    this.dom = domElement;
    this.keys = Object.create(null);
    this.pressed = new Set();
    this.mx = 0;
    this.my = 0;
    this.wheel = 0;
    this.locked = false;
    this._lockCbs = [];

    addEventListener("keydown", (e) => {
      // Stop Space / arrows from scrolling the page.
      if (["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.code)) {
        e.preventDefault();
      }
      if (!e.repeat && !this.keys[e.code]) this.pressed.add(e.code);
      this.keys[e.code] = true;
    });

    addEventListener("keyup", (e) => {
      this.keys[e.code] = false;
    });

    // Release everything if the window loses focus (prevents "stuck" keys).
    addEventListener("blur", () => {
      this.keys = Object.create(null);
    });

    document.addEventListener("pointerlockchange", () => {
      this.locked = document.pointerLockElement === this.dom;
      this._lockCbs.forEach((cb) => cb(this.locked));
    });

    document.addEventListener("mousemove", (e) => {
      if (!this.locked) return;
      this.mx += e.movementX || 0;
      this.my += e.movementY || 0;
    });

    addEventListener(
      "wheel",
      (e) => {
        this.wheel += e.deltaY;
      },
      { passive: true }
    );
  }

  requestLock() {
    if (this.dom.requestPointerLock) this.dom.requestPointerLock();
  }
  exitLock() {
    if (document.exitPointerLock) document.exitPointerLock();
  }
  onLockChange(cb) {
    this._lockCbs.push(cb);
  }

  isDown(code) {
    return !!this.keys[code];
  }
  wasPressed(code) {
    return this.pressed.has(code);
  }

  // Reset per-frame accumulators.
  endFrame() {
    this.mx = 0;
    this.my = 0;
    this.wheel = 0;
    this.pressed.clear();
  }
}
