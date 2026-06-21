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

## What it can do (the tools)

| Area | Tools |
|------|-------|
| **Shell** | `run_shell` — any bash command |
| **Files** | `read_file`, `write_file`, `append_file`, `list_directory`, `delete_path` |
| **Apps** | `open_app`, `open_path`, `quit_app`, `run_applescript` |
| **Screen** | `take_screenshot` (Jarvis *sees* the screen), `mouse_click`, `type_text`, `press_keys`, `scroll`, `get_screen_size` |
| **Web** | `web_search`, `web_fetch` (Anthropic server-side), `download_file` |
| **System** | `notify`, `get_clipboard`, `set_clipboard`, `set_volume`, `system_info` |

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

**2. Install**
```bash
cd jarvis
python3 -m venv .venv && source .venv/bin/activate
pip install -U -r requirements.txt
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

```bash
python main.py            # type to it; replies are printed and spoken
python main.py --voice    # press Enter, speak; replies are spoken
./run.sh --voice          # or let the launcher set up the venv for you
```

Useful flags:
| Flag | Effect |
|------|--------|
| `--voice` | Push-to-talk voice input |
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

## Troubleshooting

- **"Set ANTHROPIC_API_KEY first"** — create `.env` from `.env.example`.
- **Mouse/keyboard do nothing** — grant **Accessibility** to your terminal, then restart it.
- **Screenshots fail** — grant **Screen Recording**, then restart your terminal.
- **Voice input not working** — `brew install portaudio && pip install pyaudio`, and grant **Microphone**.
- **`TypeError` on `output_config`/`thinking`** — `pip install -U anthropic` (you have an old SDK).
- **It's too cautious / too chatty** — try `--auto` (trusted tasks) or `--effort medium`.

Built to be owned and extended. Have fun. ⚡
