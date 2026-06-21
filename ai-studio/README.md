# AURORA — AI Creative Studio

A native **desktop application** for AI-native creative editing. You don't hunt
through menus — you *direct* it, by text or by voice, and it does the work:
generates images, writes and styles titles, grades the look, builds effects,
animates layers, and cuts video reels. It talks back, has opinions, and improvises.

Built with Electron (the same approach as VS Code / Figma desktop), so it's a real
installable app — its own window, app menu, and dock/taskbar icon — not a browser tab.
It runs in **demo mode** with **zero API keys**; every generation/voice call sits behind
a provider adapter so real models drop in later without touching the UI.

> Self-contained app in `ai-studio/`. It does **not** touch the Kusha Spices costing
> app in the repo root.

![AURORA](build/icon.png)

---

## Run the app

```bash
cd ai-studio
npm install        # fetches Electron (first run only)
npm start          # launches the native Aurora Studio window
```

### Build installers (.dmg / .exe / AppImage)

```bash
npm run dist:mac     # macOS  → dist/*.dmg, *.zip
npm run dist:win     # Windows → dist/*.exe (NSIS)
npm run dist:linux   # Linux  → dist/*.AppImage
```

Icons are generated from `build/icon.png` (regenerate with `npm run icon`).

> **No-install fallback:** the UI is plain HTML/CSS/JS, so you can also just open
> `index.html` in Chrome, or serve it with `python3 -m http.server`. The desktop
> build is the intended experience.

---

## Test it (stress + correctness)

```bash
npm test           # node test/stress.js
```

`test/stress.js` is a dependency-free headless harness that stubs a minimal
DOM/canvas, loads the real modules, and hammers them: every intent, the full
effects/preset/animation vocabulary, mass engine operations, a **1,200-round
randomised fuzz** with malformed/emoji/oversized input, real image-gen across
every palette, and the voice provider. It asserts ~8–11k invariants per run and
exits non-zero on any failure. The Electron `main.js` also has an env-gated smoke
mode (`AURORA_SMOKE=1`) that boots the app, reports any renderer errors, and can
capture a screenshot — used to verify the real build end-to-end.

---

## What you can do (try these)

Type them in the Director panel, click the **chips**, or hold the 🎤 mic and *say* them:

| You say | What happens |
|---|---|
| `generate a golden-hour mountain scene` | Generates a background image (deterministic scene synth in demo mode) |
| `add a title that says "Kusha Spices"` | Adds a styled title layer |
| `make it cinematic` / `give it a neon vibe` | Applies a colour grade (vignette, warmth, contrast, bloom…) |
| `make it brighter and warmer and add a vignette` | Combines several effects in one command |
| `add a slow ken-burns zoom` | Animates the image; press **Play** ▶ to preview |
| `make an 8 second reel of a neon city` | Assembles a multi-shot reel with ken-burns, pans, grade and a title card |
| `what do you think?` | The Director critiques the canvas and suggests a fix |
| `surprise me` | It takes over and makes tasteful creative calls on its own |

Direct manipulation too: **click** a layer to select, **drag** to move, **double-click**
text to edit, tweak filters in the floating **Inspector**, scrub the **Timeline**.
Shortcuts: **Space** play/pause · **Del** delete · **Ctrl/⌘+Z** undo.

---

## Architecture

```
ai-studio/
├── index.html        layout + inline SVG icons + aurora curtain + window controls
├── styles.css        design system (tokens, glass, aurora, native title bar)
├── package.json      Electron app + electron-builder config
├── electron/
│   ├── main.js       main process: native window, menu, mic permission, IPC
│   └── preload.js    secure window.aurora bridge (contextIsolation)
├── build/
│   ├── make_icon.py  zero-dep aurora app-icon generator
│   └── icon.png      1024² app icon
├── test/stress.js    headless stress + correctness harness
└── js/
    ├── engine.js     document model · DOM stage renderer · animation/timeline · history
    ├── imagegen.js   image-generation PROVIDER (demo: procedural scene synth)
    ├── voice.js      voice PROVIDER (real: Web Speech STT + TTS)
    ├── director.js   the AI "Director": intent parsing → actions → opinions
    ├── app.js        UI wiring: chat, voice loop, stage, timeline, boot
    └── desktop.js    native-window glue (no-ops in a plain browser)
```

No frontend build step; modules attach to a single `window.Aurora` namespace.

### Where real APIs plug in (the adapter seams)

Demo mode is structured like an agentic LLM app, so going live means editing
**three** spots — nothing else changes:

1. **Conversational brain → Claude.** Replace `Aurora.Director.handle()` in
   `js/director.js` with a call to the Anthropic Messages API (`claude-opus-4-8`),
   exposing the canvas operations as **tools** (`generate_image`, `add_text`,
   `apply_effect`, `animate`, `make_reel`). The persona + tool contract are written
   at the top of that file.
2. **Image generation → a real model.** Replace the body of
   `Aurora.ImageGen.generate(prompt)` in `js/imagegen.js` to return `{ src }` from
   your image endpoint. The drop-in `fetch` example is in the file.
3. **Voice → cloud STT/TTS (optional).** `js/voice.js` uses the browser's Web Speech
   API (real, no keys). Swap `listen()` / `speak()` for a cloud provider for higher
   quality or guaranteed cross-platform support.

For true **generative video**, the `Export` action is the integration point: send the
assembled timeline to a video model / renderer and return an MP4.

---

## Demo mode vs. production

- **Real now:** the whole UI, native window/menu, layers, effects/grade, the keyframe
  animation engine, the timeline + playback, reel assembly, undo/history, drag-to-move,
  and voice out (TTS) + voice in (STT, in Chromium).
- **Mocked now (by design):** *image pixels* are synthesised procedurally instead of by
  a diffusion model, and the AI brain is a local intent parser instead of an LLM. Both
  are one adapter swap away from real.

### Voice note
Speech **synthesis** (the Director talking back) works everywhere. Speech
**recognition** (talking to it) uses Chromium's Web Speech API; in a packaged Electron
build it may need a speech key or a bundled local STT engine — wire it via the
`js/voice.js` adapter. In the meantime, every command works by typing.

## Roadmap

- Wire the three adapters (Claude brain, image model, video render).
- Server-side MP4 export + transparent layers.
- Asset library, fonts, brand kits; project save/load.
- Multi-track audio, captions, beat-synced animation; collaboration.
