# AURORA — AI Creative Studio

An **AI-native creative editor**. You don't hunt through menus — you *direct* it, by
text or by voice, and it does the work: generates images, writes and styles titles,
grades the look, builds effects, animates layers, and cuts video reels. It talks back,
has opinions, and improvises.

This is a **working prototype in demo mode**: it opens and runs with **zero setup and
no API keys**. Every generation/voice call sits behind a provider adapter, so real
models drop in later without touching the UI.

> Separate, self-contained app living in `ai-studio/`. It does **not** touch the
> Kusha Spices costing app in the repo root.

---

## Run it

**Option A — just open it.** Double-click `ai-studio/index.html` (it's built as plain
classic scripts so it runs straight from `file://`).

**Option B — tiny static server** (best; some browsers gate the mic on `file://`):

```bash
cd ai-studio
python3 -m http.server 8000
# then open http://localhost:8000
```

Use **Chrome, Edge, or Safari** for full **voice-to-voice** (the Web Speech API).
Everything else works by typing in any modern browser.

---

## What you can do (try these)

Type them in the Director panel, click the **chips**, or hold the 🎤 mic and *say* them:

| You say | What happens |
|---|---|
| `generate a golden-hour mountain scene` | Generates a background image (a real, deterministic scene synth in demo mode) |
| `add a title that says "Kusha Spices"` | Adds a styled title layer |
| `make it cinematic` / `give it a neon vibe` | Applies a colour grade (vignette, warmth, contrast, bloom…) |
| `make it brighter and warmer and add a vignette` | Combines several effects in one command |
| `add a slow ken-burns zoom` | Animates a layer; press **Play** ▶ to preview |
| `make an 8 second reel of a neon city` | Assembles a multi-shot video reel with ken-burns, pans, grade and a title card |
| `what do you think?` | The Director critiques the canvas and suggests a fix |
| `surprise me` | It takes over and makes tasteful creative calls on its own |

Plus direct manipulation: **click** a layer to select, **drag** to move, **double-click**
text to edit, tweak filters in the floating **Inspector**, scrub the **Timeline**.
Shortcuts: **Space** play/pause · **Del** delete · **Ctrl/⌘+Z** undo.

---

## How the vision maps to the build

| Requirement | In this prototype |
|---|---|
| Amazing UI | Glassmorphic, aurora-gradient dark UI; animated; floating inspector; timeline |
| AI executes tasks from commands | The **Director** parses natural language → executes real canvas operations |
| Editing | Layers, filters, colour grade, transforms, opacity — all real |
| Picture generation | Deterministic procedural scene art (demo) behind a real image-API seam |
| Animation generation | Real keyframe engine (fade/zoom/pan/slide/rise/spin/float/pulse) |
| Effects generation | Real CSS-filter + grade engine (brightness/contrast/saturation/blur/sepia/B&W/bloom…) |
| Video generation | Real in-browser **reel assembly** (ken-burns montage + grade + title); generative video is a documented provider seam |
| Converses, opinions, improvisation | The Director critiques, recommends, and has a `surprise me` autonomous mode |
| Voice-to-voice | Real browser **STT in + TTS out**, with a hands-free conversation loop |

---

## Architecture

```
ai-studio/
├── index.html         layout + inline SVG icon set
├── styles.css         the design system (tokens, glass, aurora, layout)
└── js/
    ├── engine.js      document model · DOM stage renderer · animation/timeline · history
    ├── imagegen.js    image-generation PROVIDER (demo: procedural scene synth)
    ├── voice.js       voice PROVIDER (real: Web Speech STT + TTS)
    ├── director.js    the AI "Director": intent parsing → actions → opinions
    └── app.js         UI wiring: chat, voice loop, stage interaction, timeline, boot
```

No build step, no dependencies. Modules attach to a single `window.Aurora` namespace.

### Where real APIs plug in (the adapter seams)

Demo mode is deliberately structured like an agentic LLM app so you can go live by
editing **three** spots — nothing else changes:

1. **Conversational brain → Claude.** Replace `Aurora.Director.handle()` in
   `js/director.js` with a call to the Anthropic Messages API (`claude-opus-4-8`),
   exposing the canvas operations as **tools** (`generate_image`, `add_text`,
   `apply_effect`, `animate`, `make_reel`). The persona and tool contract are already
   written at the top of that file.
2. **Image generation → a real model.** Replace the body of
   `Aurora.ImageGen.generate(prompt)` in `js/imagegen.js` to call your image endpoint
   and return `{ src }`. The drop-in `fetch` example is in the file.
3. **Voice → cloud STT/TTS (optional).** `js/voice.js` already uses the real browser
   Web Speech API. Swap the bodies of `listen()` / `speak()` for a cloud provider if you
   want higher-quality, cross-browser voices.

For true **generative video**, the `Export` action is the integration point: send the
assembled timeline to a video model / renderer and return an MP4.

---

## Demo mode vs. production — what's real today

- **Real now:** the entire UI, layers, effects/grade, the keyframe animation engine,
  the timeline + playback, reel assembly, undo/history, drag-to-move, and **voice in/out**.
- **Mocked now (by design):** *image pixels* are synthesised procedurally instead of by a
  diffusion model, and the AI brain is a local intent parser instead of an LLM. Both are
  one adapter swap away from real.

## Roadmap to a full product

- Wire the three adapters above (Claude brain, image model, video render).
- Server-side render/export for MP4 + transparent layers.
- Real asset library, fonts, and brand kits; project save/load.
- Multi-track audio, captions, and beat-synced animation.
- Collaborative editing and version history.
