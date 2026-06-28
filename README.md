# Reachy Mini Lite + LLM

Control a [Reachy Mini Lite](https://www.pollen-robotics.com/reachy-mini/) robot using Python — with local LLM-powered speech via [Ollama](https://ollama.com) and [Piper TTS](https://github.com/rhasspy/piper).

Everything runs locally on your machine. No cloud APIs required.

## Quick Start

The fastest way to meet Robot Karl is the one-command launcher — it checks
every dependency, starts the daemon, applies the camera fix, wires up the
LED eyes, and drops you into a conversation:

```bash
./start_karl.sh            # "Hey Karl" wake-word assistant (default)
./start_karl.sh listen     # continuous conversation + speaker tracking
./start_karl.sh say "Hi"   # quick offline speech test
```

See **[Fully Offline Interactive Karl](#fully-offline-interactive-karl)** for
what it runs. To set things up manually instead:

```bash
# 1. Set up environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Download Karl's Piper voice model (~60MB, one-time)
mkdir -p piper_models
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/northern_english_male/medium"
curl -sL "$BASE/en_GB-northern_english_male-medium.onnx"      -o piper_models/en_GB-northern_english_male-medium.onnx
curl -sL "$BASE/en_GB-northern_english_male-medium.onnx.json" -o piper_models/en_GB-northern_english_male-medium.onnx.json

# 3. Start the daemon (in a separate terminal)
reachy-mini-daemon

# 4. Run individual scripts!
python wave_antennas.py                          # wave the antennas
python play_tone.py                              # play a melody
python speak.py                                  # speak via Google TTS (online)
python reachy_say.py "Ey up!"                     # speak fully offline (macOS say)
python reachy_speak_llm.py "Tell me a joke!"     # LLM + local TTS
python reachy_speak_animated.py                  # LLM + TTS + head/antenna animation
python reachy_wake.py                            # "Hey Karl" wake-word assistant
python reachy_listen.py                          # continuous conversation
python reachy_greet.py                           # watch for visitors + auto-greet
python reachy_dashboard.py                       # webhook server on port 9000
python reachy_eyes.py                            # test the LED eyes (requires ESP32)
```

### Dashboard API (port 9000)
```bash
# Speak directly
curl -X POST http://localhost:9000/say \
  -H 'Content-Type: application/json' \
  -d '{"message": "Deploy complete"}'

# Karl-styled announcement
curl -X POST http://localhost:9000/announce \
  -H 'Content-Type: application/json' \
  -d '{"event": "PR #42 merged", "context": "Auth module refactor"}'

# Check status / history
curl http://localhost:9000/status
curl http://localhost:9000/history
```

## Scripts

| Script | Description | Internet? |
|--------|-------------|-----------|
| `start_karl.sh` | One-command launcher — checks deps, starts daemon, fixes camera, wires eyes, launches Karl | No |
| `reachy_wake.py` | Always-on "Hey Karl" wake-word assistant (STT + LLM + TTS + eyes) | No |
| `reachy_listen.py` | Continuous conversation with speaker direction tracking + eyes | No |
| `wave_antennas.py` | Wave the antennas in a friendly greeting | No |
| `play_tone.py` | Play a C-E-G-C melody through the speaker | No |
| `speak.py` | Speak a phrase using Google TTS | Yes |
| `reachy_say.py` | Speak fully offline using macOS `say` (British voice) | No |
| `reachy_speak_llm.py` | Ask Ollama a question, speak the reply with Piper TTS | No |
| `reachy_speak_animated.py` | LLM speech + animated head/antenna movements | No |
| `reachy_greet.py` | Watches camera for motion, greets visitors with LLM speech | No |
| `reachy_dashboard.py` | Webhook server — any agent can POST to make robot announce | No |
| `fix_camera.py` | Fix dark camera image on macOS (UVC power-line-frequency) | No |
| `reachy_leds.py` | Function-based LED eye control (auto-detects the ESP32 port) | No |
| `reachy_eyes.py` | `RobotEyes` driver class — auto-detects port, state presets, pulse animation | No |

## Fully Offline Interactive Karl

Robot Karl is a complete conversational robot that runs **entirely on the
Mac** (tested on a Mac Mini M4) — no cloud, no API keys. Each turn of the
conversation flows through three local models:

```
🎤 mic → Whisper STT → Ollama LLM (Karl persona) → Piper TTS → 🔊 speaker
                              ↓
                  head/antenna animation + LED eyes + speaker tracking
```

| Stage | Runs locally with | Default |
|-------|-------------------|---------|
| Speech-to-text | `faster-whisper` | `base.en` |
| Reasoning | Ollama | `llama3.2` |
| Text-to-speech | Piper | `en_GB-northern_english_male` |

Karl's dry, understated personality lives in
[`robot_karl_prompt.py`](robot_karl_prompt.py) and is shared across every
speaking script.

### Launch it

```bash
./start_karl.sh            # "Hey Karl" wake-word assistant (default)
./start_karl.sh listen     # always-listening conversation + speaker tracking
```

`start_karl.sh` is the reliable entry point. It:

1. Finds a Python interpreter (`./venv`, then `~/venv`, then `python3`).
2. Downloads the Piper voice model if it's missing.
3. Ensures Ollama is running and the `llama3.2` model is pulled.
4. Starts `reachy-mini-daemon` if it isn't already running.
5. Applies the camera brightness fix (`fix_camera.py`).
6. Auto-detects the LED-eye ESP32 and exports `REACHY_EYES_PORT`.
7. Launches the chosen experience.

Override defaults with environment variables, e.g.
`OLLAMA_MODEL=qwen3:30b ./start_karl.sh`.

### Two experiences

- **`reachy_wake.py`** — Karl idles quietly until he hears **"Hey Karl"**,
  then records your request, thinks, and replies. Best for hands-free,
  always-on use.
- **`reachy_listen.py`** — a continuous back-and-forth conversation that
  also tracks the speaker's direction (DoA) and turns toward whoever is
  talking.

### LED eye states

When the [LED eyes](#led-eyes) are connected, both experiences reflect
Karl's state through the eyes (gracefully skipped if no ESP32 is found):

| State | Eyes |
|-------|------|
| Idle / waiting | dim warm white with slow blinks |
| Wake word heard | attentive amber |
| Speaking | pulsing cyan/white glow |

> **Mic note:** the conversation loops depend on the robot's microphone. If
> Karl never reacts to speech, check the mic FPC cable orientation inside
> the head.

## Speech & Voice

Robot Karl speaks with a **British (English UK) accent**. There are three
ways to give him a voice, depending on whether you want offline operation
and how much you care about voice quality:

| Script | Engine | Internet? | Notes |
|--------|--------|-----------|-------|
| `reachy_say.py` | macOS `say` | No | Zero setup — uses the built-in synthesizer. Defaults to the `Daniel` en_GB voice. |
| `reachy_speak_llm.py` / `reachy_speak_animated.py` | Piper TTS | No | Highest quality. Uses the `en_GB-northern_english_male` voice (one-time model download) plus a local Ollama LLM. |
| `speak.py` | Google TTS | Yes | Quick online fallback. |

### Offline speech with `reachy_say.py`

The simplest option needs **no model downloads, no Ollama, and no internet** —
it drives the robot's speaker straight from the macOS speech synthesizer:

```bash
python reachy_say.py                                   # default greeting
python reachy_say.py "Right then, let's get cracking!"  # custom line
python reachy_say.py -v Reed "Ey up!"                   # pick another voice
```

List the available British voices with:

```bash
say -v '?' | grep en_GB
```

`Daniel` is the default to match Karl's Northern English Piper persona, but
any en_GB voice (e.g. `Reed`, `Sandy`, `Shelley`) works via `-v`.

## LED Eyes

> ⚠️ **Experimental — not yet a reliable mod.** The ESP32 eye add-on is a
> work in progress. Known issues:
> - The board often comes up **unresponsive after powering on the robot** —
>   no `PONG`, no LEDs. Last time it only started working after unplugging
>   and re-plugging the ESP32 from the head's internal USB hub *while the
>   robot was powered on*.
> - It **can't be flashed through the internal USB hub** (esptool reports
>   "No serial data received", and the BOOT/RESET buttons are sealed inside
>   the head). Flash the XIAO **directly over USB-C** before installing it.
> - The eye serial port enumerates on different `/dev/cu.*` paths between
>   reboots, which is why the drivers auto-detect it.
>
> All speech/animation scripts treat the eyes as optional and run fine
> without them.

The robot has two RGB LEDs mounted as eyes inside the head, driven by an
ESP32 (XIAO ESP32-C6) connected through the head's internal USB hub. These
are two separate 3mm tri-color (RGB) LEDs — **not** an addressable strip —
so each color leg is driven directly by its own GPIO via PWM. The firmware
lives in [`esp32_led_eyes.ino`](esp32_led_eyes.ino) — flash it with the
Arduino IDE, or with `arduino-cli` using the
`esp32:esp32:XIAO_ESP32C6:CDCOnBoot=cdc` board profile.

**Wiring** — each LED's R/G/B legs connect to a GPIO through a 150 Ω
resistor. The build uses **common-anode** LEDs, so the common (fourth) leg
goes to **3V3** and the firmware drives the legs with inverted PWM:

| Eye | Red | Green | Blue |
|-----|-----|-------|------|
| Left (`L0`)  | D0 / GPIO0 | D1 / GPIO1 | D2 / GPIO2 |
| Right (`L1`) | D3 / GPIO21 | D5 / GPIO23 | D4 / GPIO22 |

> Common-anode means the firmware's inverted PWM (`255 - value`) is correct
> as shipped. If you ever swap to common-cathode LEDs, tie the common leg to
> GND and remove the inversion in `setLeft()` / `setRight()`.



**Serial protocol** (115200 baud, newline-terminated):

| Command | Action |
|---------|--------|
| `L0:r,g,b` | Set left eye (values 0–255) |
| `L1:r,g,b` | Set right eye |
| `LA:r,g,b` | Set both eyes |
| `OFF` | Turn both LEDs off |
| `PING` | Health check — returns `PONG` |

Two Python drivers are provided:

- **`reachy_leds.py`** — lightweight function-based helpers. Auto-detects
  the eye controller's serial port (override with `REACHY_EYES_PORT`).
- **`reachy_eyes.py`** — the `RobotEyes` class. Auto-detects the eye
  controller's serial port, exposes state presets (`listening()`,
  `thinking()`, `speaking()`, `idle()`, `alert()`, `error()`), and a
  background `start_pulse()` breathing animation.

```python
from reachy_eyes import RobotEyes

eyes = RobotEyes()        # auto-detects the serial port
eyes.set_both(0, 0, 255)  # blue
eyes.thinking()           # purple preset
eyes.close()
```

## Skills Reference

See **[ReachySkills.md](ReachySkills.md)** for the full SDK reference covering movement, audio, camera, media backends, and more.

## Requirements

- **Hardware:** Reachy Mini Lite (USB version) — optional: XIAO ESP32-C6 + RGB LEDs for the eyes (see [LED Eyes](#led-eyes))
- **Software:** Python 3.10+, [Ollama](https://ollama.com) with a model (e.g. `llama3.2`)
- **OS:** macOS (tested on Apple Silicon) — Linux should also work

## License

MIT
