# Jarvis 🤖 — a local AI assistant for your Mac

Jarvis is a voice + text assistant that runs **on your own Mac** and can actually
*do things*: run shell commands, read/write files, open and drive apps, control
the mouse and keyboard, see the screen, search the web, and more. The brain is
Claude (Anthropic); the "hands" are a set of local tools it calls in a loop until
your task is done.

### An honest note on scope
This is real software, and it's genuinely capable — but it isn't magic. It can do
what **macOS, your installed apps, and the web** allow, through the tools below.
There's no capability "beyond software": everything is bounded by your OS
permissions and what you grant it. Within those bounds it's flexible and powerful,
and you own every line — extend it however you like.

---

## What you need to download

Almost everything is **in this folder already**. Three things can't live in a zip
because they're system-level — here's the whole list:

| # | What | How |
|---|------|-----|
| ✅ | **This folder** (the app + installer) | You have it |
| 1 | **Python 3** (macOS may already have it) | Check: `python3 --version`. Missing? `xcode-select --install` |
| 2 | **An Anthropic API key** | https://console.anthropic.com/ → API Keys |
| 3 | *(voice input only)* **portaudio** | `brew install portaudio` |

Every Python package (anthropic SDK, pyautogui, rumps, …) is installed
**automatically** by the included `install.sh`. You don't fetch those by hand.

```bash
cd jarvis
./install.sh                       # sets up everything, creates .env
#  → then choose a brain (below) and you're done
```

## Pick a brain (free or paid)

Jarvis works with either, and you switch with one line in `.env`:

**A) Free local brain — runs on your Mac, no key, no cost, private.**
1. Install **Ollama** → https://ollama.com (download, open it).
2. Download a model: `ollama pull llama3.2`  (~2 GB; use `llama3.1` or `qwen2.5` if you have 16 GB+ RAM).
3. In `.env`, add:
   ```
   JARVIS_PROVIDER=ollama
   JARVIS_MODEL=llama3.2
   ```
That's it — no API key needed. Best for: free forever, privacy, offline, and the
option to fine-tune later. Trade-off: less reliable than Claude on hard multi-step
tasks, and it can't see screenshots (no vision on small local models).

**B) Paid Claude brain — most capable ("real Jarvis").**
Put your key in `.env` (`ANTHROPIC_API_KEY=sk-ant-…`). Pennies per task, no subscription.

> You can keep both configured and flip anytime: comment/uncomment `JARVIS_PROVIDER`,
> or run `python main.py --provider ollama` / `--provider anthropic`.
> Either way, Jarvis **remembers** what you tell it across sessions (see Memory) —
> that's how it gets more useful to you over time.

---

## What it can do (the tools)

| Area | Tools |
|------|-------|
| **Shell** | `run_shell` — any bash command |
| **Files** | `read_file`, `write_file`, `append_file`, `list_directory`, `delete_path` |
| **Apps** | `open_app`, `open_path`, `quit_app`, `run_applescript` |
| **Screen** | `take_screenshot` (Jarvis *sees* the screen), `mouse_click`, `type_text`, `press_keys`, `scroll`, `get_screen_size` |
| **Web** | `web_search`, `web_fetch` (Anthropic server-side), `download_file` |
| **System** | `notify`, `get_clipboard`, `set_clipboard`, `set_volume`, `system_info` |
| **Apps & extensions** | `send_email`, `create_note`, `create_reminder`, `calendar_add_event`, `music_control`, `keystroke_to`, `menu_click`, `run_shortcut`, `list_shortcuts` |
| **Memory** | `remember`, `recall`, `forget` (persists across sessions) |

> **Any app, any execution — really.** `run_shell` runs *any* command and
> `run_applescript` scripts *any* Mac app, so Jarvis isn't limited to the tools
> above. `menu_click` / `keystroke_to` drive arbitrary app UIs, and
> `run_shortcut` lets you expose **anything you build in Apple Shortcuts** as a
> Jarvis capability. To add a first-class tool of your own, drop a function +
> `Tool(...)` entry into a `tools/*.py` module — it's auto-registered.

Example things to ask:
- "Organize my Downloads folder by file type."
- "Open Safari, search for the weather in Tokyo, and tell me."
- "Take a screenshot and tell me what app is in focus."
- "Create a Python script on my Desktop that renames these files, then run it."
- "What's on my clipboard? Summarize it."

---

## Setup (one time)

**1. Requirements**
- macOS, Python 3.9+
- An Anthropic API key → https://console.anthropic.com/

**2. Install** — one command:
```bash
cd jarvis
./install.sh           # creates the venv, installs deps, makes your .env
```

**3. Add your API key**
```bash
cp .env.example .env
# edit .env and paste your key
```

**4. Grant macOS permissions** (System Settings → Privacy & Security)
- **Accessibility** → add your terminal (Terminal/iTerm) — needed for mouse/keyboard control
- **Screen Recording** → add your terminal — needed for screenshots
- **Microphone** → add your terminal — needed for voice input

**5. (Voice input only)** install the audio backend:
```bash
brew install portaudio
pip install pyaudio
```
Voice *output* (Jarvis talking) needs nothing extra — it uses the built-in `say`.

---

## Run

Three ways to use it:

```bash
# 1) Terminal (text or voice)
python main.py            # type to it; replies are printed and spoken
python main.py --voice    # press Enter, speak; replies are spoken
python main.py --wake     # always listening — just say "Jarvis, ..."

# 2) Menu-bar app (no terminal window)
python menubar.py         # 🤖 appears in your menu bar
#   …or double-click Jarvis.command in Finder

# 3) A real .app  (see "Build a Mac app" below)
./build_app.sh            # → dist/Jarvis.app
```

Useful flags:
| Flag | Effect |
|------|--------|
| `--voice` | Push-to-talk voice input |
| `--wake` | Always-listening wake word ("Jarvis …") |
| `--chat` | Companion conversation mode (warm, voice-to-voice, learns as you talk) |
| `--no-speak` | Don't speak replies (text only) |
| `--auto` | Skip confirmations for risky actions (⚠ see Safety) |
| `--model claude-sonnet-4-6` | Use a faster/cheaper model |
| `--effort medium` | Trade some quality for speed/cost (`low`…`max`) |
| `--no-thinking` | Disable extended thinking for snappier replies |
| `--no-web` | Disable web search/fetch |

---

## Safety

An assistant with shell access can also break things, so actions are graded:

- **SAFE** (read a file, screenshot, search) — run automatically.
- **CAUTION** (write a file, click, type, quit an app) — asks for confirmation.
- **DANGER** (delete, arbitrary shell, arbitrary AppleScript) — asks for confirmation.

You approve risky actions with `y` at the prompt. `--auto` skips these prompts —
convenient for smooth screen control, but it lets Jarvis act unsupervised, so use
it only when you trust the task. A small set of **catastrophic** commands
(e.g. `rm -rf /`, `mkfs`, fork bombs) is **always refused**, even with `--auto`.

Every action is logged to `jarvis.log`.

---

## Cost

Each request bills Anthropic API tokens. Defaults use **Claude Opus 4.8**
(most capable). For lighter/cheaper runs:
```bash
python main.py --model claude-sonnet-4-6 --effort medium
```
Approx. input/output per 1M tokens: Opus 4.8 `$5 / $25`, Sonnet 4.6 `$3 / $15`,
Haiku 4.5 `$1 / $5`. Screenshots add image tokens (auto-downscaled to keep cost down).

---

## How it works

```
main.py        CLI + REPL (text or push-to-talk voice)
  └─ agent.py  the loop: call Claude → run the tools it asks for → repeat
       ├─ tools/   shell, files, apps, screen, web, system  (each a small module)
       ├─ safety.py  risk grading, confirmation, hard-blocks, logging
       ├─ voice.py   say (TTS) + SpeechRecognition (STT)
       └─ config.py  model, effort, system prompt
```

Adding a tool is easy: write a function in a `tools/*.py` module and append a
`Tool(...)` entry with its name, description, JSON schema, handler, and risk level.
It's automatically registered and offered to Claude on the next run.

---

## Wake word

`--wake` (CLI) and the **Listen for wake word** menu item start an always-on
listener. Say any of "**Jarvis**", "hey Jarvis", "okay Jarvis" (configurable in
`config.py`) followed by your command — e.g. *"Jarvis, what's in my Downloads
folder?"*. Say just "Jarvis" and it replies "Yes?" and waits for the command.

The default backend uses Google speech recognition (needs internet, no key). For
lower CPU and a dedicated on-device "Jarvis" keyword, install
[Porcupine](https://picovoice.ai/) (`pip install pvporcupine`) and set a free
`PV_ACCESS_KEY` — then swap it into `wake.py` (the loop is isolated there).

## Menu-bar app & building a Mac app

**Run it as a menu-bar app right now** (no build step):
```bash
python menubar.py          # or double-click Jarvis.command
```
The 🤖 menu lets you type a request, toggle the wake word, toggle auto-approve,
toggle spoken replies, open the log, and quit. Confirmations pop up as native
dialogs, so it works with no terminal attached.

**Build a standalone `Jarvis.app`** (background app, no Dock icon):
```bash
./build_app.sh             # → dist/Jarvis.app
```
Then drag `dist/Jarvis.app` to `/Applications`. On first launch, grant
**Microphone**, **Screen Recording**, and **Accessibility** to *Jarvis* in
System Settings → Privacy & Security, and keep a `.env` (with your key) next to
the app or export `ANTHROPIC_API_KEY`. Packaging runs on your Mac via `py2app`.

### Use your own icon
A default arc-reactor icon ships in `assets/icon.png`. To use a different image,
just **overwrite `assets/icon.png`** with your own (square PNG works best), then
rebuild (`./build_app.sh`) or restart the menu-bar app. The build keeps your
image — it only generates the default if `icon.png` is missing.

## Conversation mode (a companion that learns)

```bash
python main.py --chat        # warm back-and-forth; voice-to-voice if a mic is set up
```
Or, in the menu-bar app, toggle **Conversation mode**. Jarvis takes on a warmer,
friendlier personality, has real back-and-forth conversations, and **learns about
you as you talk** — when it picks up something durable (your name, preferences,
people and projects in your life), it quietly saves it to memory and carries it
into future chats. Say "goodbye" to end.

**What "learns" honestly means:** it grows a memory of *you* and adapts to it over
time — it does **not** retrain its own neural network, and it won't become
conscious or literally human. Within that, it gets more personal and useful the
more you talk to it. (True model fine-tuning is a separate, advanced step that only
the local Ollama brain allows, on capable hardware.)

## Memory

Jarvis remembers things across sessions. Tell it *"remember that my projects live
in ~/code"* and it saves the note (to `memory.json`); next launch it already
knows. It uses three tools — `remember`, `recall`, `forget` — and remembered
notes are injected into its context automatically each turn. Edit or wipe memory
by editing/deleting `memory.json`.

## Stopping a task

If Jarvis is mid-task and you want it to stop:
- **Menu-bar app:** click **Stop current task**, or press **⌘⇧.** (Cmd+Shift+period) anywhere.
- **Terminal:** press **Ctrl-C**.

It stops cleanly at the next step rather than leaving things half-done.

## Troubleshooting

- **"Set ANTHROPIC_API_KEY first"** — create `.env` from `.env.example`.
- **Mouse/keyboard do nothing** — grant **Accessibility** to your terminal, then restart it.
- **Screenshots fail** — grant **Screen Recording**, then restart your terminal.
- **Voice input not working** — `brew install portaudio && pip install pyaudio`, and grant **Microphone**.
- **`TypeError` on `output_config`/`thinking`** — `pip install -U anthropic` (you have an old SDK).
- **It's too cautious / too chatty** — try `--auto` (trusted tasks) or `--effort medium`.

Built to be owned and extended. Have fun. ⚡
