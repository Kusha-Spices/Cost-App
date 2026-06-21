# 🌍 Aetherion — An Endless Open World

A browser-based, **open-world exploration game** inspired by the feel of titles
like *Genshin Impact* — a stylised hero you steer through a vast, beautiful
landscape with sprinting, gliding, swimming and climbing-style traversal.

The world is **procedurally generated and effectively infinite**: terrain builds
itself around you as you travel and unloads behind you, so there is **no edge of
the map** — every direction goes on forever, and no two journeys look the same.

Built with **[Three.js](https://threejs.org/) (WebGL)**. No game engine, no build
step, no downloads — it runs in any modern browser.

> **An honest note on scope.** *Genshin Impact* is a 100-million-dollar
> production made by hundreds of artists and engineers over many years on a
> custom engine. This is **not** that, and doesn't pretend to be. It's a
> hand-built, self-contained **open-world engine and playable demo** that
> captures the core ideas — endless procedural terrain, third-person traversal,
> a switchable cast, day/night atmosphere and modern web rendering — in a few
> thousand lines you can actually read, run and extend.

---

## ▶️ How to run

ES modules don't load from `file://`, so serve the folder over HTTP. Two options:

**Option A — Python (no install):**
```bash
cd aetherion
python3 serve.py          # opens http://localhost:8000 automatically
```

**Option B — any static server:**
```bash
cd aetherion
npx serve .               # or: python3 -m http.server 8000
```

Then open the printed URL and click **▶ Explore the World**.
The first load fetches Three.js from a CDN, so you need internet once.

> Best experienced on a desktop/laptop with a discrete or recent integrated GPU.
> Chrome, Edge, Firefox and Safari are all supported (WebGL2).

---

## 🎮 Controls

| Action | Key |
| --- | --- |
| Move | **W A S D** |
| Look around | **Mouse** (click to capture, **Esc** to release) |
| Sprint | **Shift** (drains stamina) |
| Jump | **Space** |
| Glide | **Hold Space** while airborne and falling |
| Swim | automatic in deep water |
| Switch hero | **1 · 2 · 3** (or click a portrait) |
| Free-fly camera | **F** (Space = up, C = down) |
| Zoom | **Mouse wheel** |

Three elemental heroes — **Anemo 🌪️**, **Pyro 🔥** and **Hydro 💧** — can be
swapped instantly, each with their own colour and glider.

---

## ✨ What's in it

- **Infinite streaming terrain** — chunks generate around the player from layered
  simplex noise (continents, rolling hills, ridged mountains, domain warping) and
  dispose once far away. Memory stays bounded no matter how far you walk.
- **Biomes** — sea, beaches, plains, forests, highlands and snow-capped peaks,
  coloured by altitude and slope, and named in the HUD as you cross them.
- **Dynamic day/night** — a real sun arcs overhead with moving shadows, a
  gradient sky shader with a sun disk, fading stars at night, and fog that
  always matches the horizon.
- **Animated water** — a wave-displaced ocean/lake surface with fresnel and sun
  glint that follows you to the horizon.
- **Traversal** — walk, sprint, jump, **glider**, swimming and a free-fly camera,
  all governed by a stamina system.
- **Instanced vegetation** — forests, rocks and grass scattered deterministically
  per region and drawn with `InstancedMesh` for performance.
- **HUD** — status panel, stamina bar, party switcher and a **live minimap**
  rendered straight from the heightfield.

---

## 🗺️ Why exploration is "endless"

Nothing about the world is stored on disk. Every hill, coastline and forest is a
pure function of its `(x, z)` coordinates:

```
heightAt(x, z)  →  elevation
biomeAt(x, z)   →  region
```

Because those functions are deterministic, the engine can throw away terrain
behind you and rebuild it identically if you return — which means the playable
area is limited only by floating-point range, not by memory or a designed map
boundary. Walk in any direction for as long as you like; there's always more.

---

## 📁 Project structure

```
aetherion/
├── index.html            # canvas, HUD markup, Three.js import map
├── styles.css            # HUD / menu styling
├── serve.py              # tiny local static server
└── src/
    ├── main.js           # bootstrap + game loop
    ├── core/input.js     # keyboard + pointer-lock mouse
    ├── player/
    │   ├── character.js   # hero model, animation, movement controller
    │   └── camera.js      # third-person orbit camera
    ├── world/
    │   ├── noise.js       # seedable simplex noise + fbm/ridged helpers
    │   ├── heightfield.js # heightAt / biomeAt — the shape of the world
    │   ├── terrain.js     # streaming chunk manager
    │   ├── scatter.js     # instanced trees / rocks / grass
    │   ├── sky.js         # sky dome, sun, lights, day/night, stars
    │   └── water.js       # animated water surface
    └── ui/hud.js          # status panel, stamina, party, minimap
```

---

## 🛠️ Tuning & extending

Most of the feel lives in a few constants:

- **World shape** → `src/world/heightfield.js` (`heightAt`, `WATER_LEVEL`, `SNOW_LINE`).
- **Draw distance / detail** → `CHUNK_SIZE`, `SEGMENTS`, `VIEW_RADIUS` in `terrain.js`.
- **Movement** → speeds, gravity, jump and stamina in `player/character.js`.
- **Day length & palette** → `sky.js`.

Ideas to build on: collectibles & a mini-quest, elemental combat tied to the
three heroes, gliding wind currents, points of interest seeded into chunks,
loading external `.glb` hero models, or a teleport/waypoint map.

---

*Made with Three.js. Procedurally generated — no two journeys alike.*
