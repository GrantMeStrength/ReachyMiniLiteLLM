# Reachy Mini Lite + LLM

Control a [Reachy Mini Lite](https://www.pollen-robotics.com/reachy-mini/) robot using Python — with local LLM-powered speech via [Ollama](https://ollama.com) and [Piper TTS](https://github.com/rhasspy/piper).

Everything runs locally on your machine. No cloud APIs required.

## Quick Start

```bash
# 1. Set up environment
python -m venv venv
source venv/bin/activate
pip install reachy-mini ollama piper-tts scipy gtts

# 2. Download a Piper voice model (~60MB, one-time)
mkdir -p piper_models
curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx" \
     -o piper_models/en_US-amy-medium.onnx
curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json" \
     -o piper_models/en_US-amy-medium.onnx.json

# 3. Start the daemon (in a separate terminal)
reachy-mini-daemon

# 4. Run!
python wave_antennas.py                          # wave the antennas
python play_tone.py                              # play a melody
python speak.py                                  # speak via Google TTS (online)
python reachy_say.py "Ey up!"                     # speak fully offline (macOS say)
python reachy_speak_llm.py "Tell me a joke!"     # LLM + local TTS
python reachy_speak_animated.py                  # LLM + TTS + head/antenna animation
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
| `wave_antennas.py` | Wave the antennas in a friendly greeting | No |
| `play_tone.py` | Play a C-E-G-C melody through the speaker | No |
| `speak.py` | Speak a phrase using Google TTS | Yes |
| `reachy_say.py` | Speak fully offline using macOS `say` (British voice) | No |
| `reachy_speak_llm.py` | Ask Ollama a question, speak the reply with Piper TTS | No |
| `reachy_speak_animated.py` | LLM speech + animated head/antenna movements | No |
| `reachy_greet.py` | Watches camera for motion, greets visitors with LLM speech | No |
| `reachy_dashboard.py` | Webhook server — any agent can POST to make robot announce | No |
| `reachy_leds.py` | Simple function-based LED eye control (fixed serial port) | No |
| `reachy_eyes.py` | `RobotEyes` driver class — auto-detects port, state presets, pulse animation | No |

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

The robot has two RGB LEDs mounted as eyes inside the head, driven by an
ESP32 (XIAO ESP32-C6) connected through the head's internal USB hub. These
are two separate 3mm tri-color (RGB) LEDs — **not** an addressable strip —
so each color leg is driven directly by its own GPIO via PWM. The firmware
lives in [`esp32_led_eyes.ino`](esp32_led_eyes.ino) — flash it with the
Arduino IDE.

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

- **`reachy_leds.py`** — lightweight function-based helpers with a fixed
  serial port. Good for quick scripts.
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
