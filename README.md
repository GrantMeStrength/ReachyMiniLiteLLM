# Reachy Mini Lite + LLM

Control a [Reachy Mini Lite](https://www.pollen-robotics.com/reachy-mini/) robot using Python — with local LLM-powered speech via [Ollama](https://ollama.com) and [Piper TTS](https://github.com/rhasspy/piper).

Everything runs locally on your machine. No cloud APIs required.

**Tested platform:** Reachy Mini Lite with
[`reachy-mini==1.10.0`](https://github.com/pollen-robotics/reachy_mini/releases/tag/v1.10.0)
on Apple Silicon macOS.

## Current Status

The complete stack is working on Karl, the project's Reachy Mini Lite:

| Subsystem | Status | Notes |
|-----------|--------|-------|
| Motors and movement | Working | Wake, head pitch/yaw/roll, body rotation, antennas, nod, shake, and demo motions |
| Microphone | Working | The replacement FPC cable must be installed in the correct orientation |
| Speaker and speech | Working | macOS `say` and Piper use Reachy Mini 1.10's daemon-side speaker EQ |
| Camera | Working | Daemon-native JPEG capture works; `fix_camera.py` corrects the dark macOS image |
| LED eyes | Working | USB startup recovery, color control, blinking, and periodic idle blinking |
| Offline conversation | Working | Whisper STT, Ollama reasoning, Piper TTS, movement, eye feedback, and speaker tracking |
| Face tracking | Working | Reachy Mini 1.10's adaptively smoothed daemon-side YuNet tracker, manual follow mode, and visitor detection |
| GPP mode | Working | Genuine People Personality follows faces, turns toward detected speech, blinks while awake, naps in an empty room, and makes rare local remarks |
| Recorded emotions | Working | Official Reachy emotions dataset available from the CLI and macOS app |
| macOS controller | Working | Native SwiftUI app using daemon REST for motion and supported SDK media APIs |
| OpenClaw integration | Working | `karlctl` is exposed through the installed `reachy` skill |

On Karl's current build, eye firmware flashing has only worked over a
**direct USB-C connection**; normal eye control works through the robot's
internal USB hub. See [Known Limitations](#known-limitations).

## Quick Start

The fastest way to meet Robot Karl is the one-command launcher — it checks
every dependency, starts the daemon, applies the camera fix, wires up the
LED eyes, and drops you into a conversation:

```bash
./start_karl.sh            # "Hey Karl" wake-word assistant (default)
./start_karl.sh listen     # continuous conversation + speaker tracking
./start_karl.sh say "Hi"   # quick offline speech test
```

### Karl Controller macOS app

`KarlController/` contains a native SwiftUI master control application for
starting, stopping, diagnosing, and interacting with Robot Karl.

| Area | Features |
|------|----------|
| **Overview** | Daemon, LED-eye, and camera status; start/stop robot; wake motion |
| **Interactive modes** | Wake-word assistant, continuous conversation, visitor greeter, and GPP |
| **Head** | Look up/down/left/right, center, tilt left/right |
| **Body** | Rotate left/right and return to center |
| **Antennas** | Up, down, and Karl-tested `[0.15, -0.25]` rest position outside the gearbox backlash zone |
| **Tracking** | Start and stop official daemon-side face following |
| **Gestures** | Nod yes, shake no, full demo, and recorded emotions |
| **Speech** | Type text for Karl to speak through the robot |
| **Eyes** | Preset colors, custom color picker, blink now, periodic blinking, and off |
| **Camera** | Reapply the macOS brightness workaround, then capture and display a still image |
| **Diagnostics** | Robot status, serial ports, running processes, daemon log, and mode log |

Build the app and install it on the Desktop:

```bash
./KarlController/build_app.sh --install
```

Then open **Karl Controller.app** from the Desktop. Set `KARL_REPO` before
launching if the repository is stored somewhere other than
`/Users/john/Developer/ReachyMiniLiteLLM`.

**GPP** is Karl's “Genuine People Personality” mode. It uses Reachy Mini
1.10's smoothed face tracking and daemon-side microphone direction state to
turn toward a speaker when no face is visible. Natural eye blinking remains
active while someone is present. After 45 seconds
without seeing a face, Karl lowers his head and turns his eyes off. Because
the camera points down while he sleeps, he briefly raises his head every 15
seconds to look for returning company; two successive face detections wake
him. This daytime nap is separate from overnight sleep: at 10:00 PM local time
Karl lowers his head, turns his eyes off, disables face tracking, and performs
no presence checks. At 7:00 AM local time he wakes automatically and resumes
GPP. After someone has remained in the room for a while, GPP has a deliberately
small chance of making a dry comment about the local time or weather. These
remarks use no cloud or location API.

The Reachy daemon process needs macOS Camera and Microphone permission. Camera
snapshots are read from its GStreamer media pipeline rather than opening the
USB camera a second time.

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

# 3. Start the local-only daemon (in a separate terminal)
HF_HOME="$HOME/.config/karl/huggingface" reachy-mini-daemon

# 4. Run individual scripts!
python wave_antennas.py                          # wave the antennas
python play_tone.py                              # play a melody
python speak.py                                  # simple offline speech demo
python reachy_say.py "Ey up!"                     # speak fully offline (macOS say)
python reachy_speak_llm.py "Tell me a joke!"     # LLM + local TTS
python reachy_speak_animated.py                  # LLM + TTS + head/antenna animation
python reachy_wake.py                            # "Hey Karl" wake-word assistant
python reachy_listen.py                          # continuous conversation
python reachy_greet.py                           # watch for visitors + auto-greet
python reachy_gpp.py                             # autonomous GPP mode
python reachy_dashboard.py                       # local-only webhook server on port 9000
python reachy_eyes.py                            # test the LED eyes (requires ESP32)
```

### Dashboard API (port 9000)

The dashboard binds to `127.0.0.1` by default because its control and camera
endpoints are intentionally unauthenticated. Use an authenticated proxy rather
than exposing port 9000 directly to a network.

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
| `reachy_gpp.py` | Genuine People Personality with face following, DoA attention, blinking, naps, and overnight sleep | No |
| `wave_antennas.py` | Wave the antennas in a friendly greeting | No |
| `play_tone.py` | Play a C-E-G-C melody through the speaker | No |
| `speak.py` | Simple offline speech demo using Karl's macOS voice | No |
| `reachy_say.py` | Speak fully offline using macOS `say` (British voice) | No |
| `reachy_speak_llm.py` | Ask Ollama a question, speak the reply with Piper TTS | No |
| `reachy_speak_animated.py` | LLM speech + animated head/antenna movements | No |
| `reachy_greet.py` | Watches camera for motion, greets visitors with LLM speech | No |
| `reachy_dashboard.py` | Local-only webhook server for announcements, status, history, and camera | No |
| `karlctl.py` / `karlctl` | Unified command-line control for status, motion, speech, eyes, camera, and demos | No |
| `fix_camera.py` | Fix dark camera image on macOS (UVC power-line-frequency) | No |
| `reachy_leds.py` | Shared LED-eye control with safe ownership, recovery, status heartbeat, and GPP blink requests | No |
| `reachy_eyes.py` | `RobotEyes` driver class — auto-detects port, state presets, pulse animation | No |

## Unified `karlctl` CLI

`karlctl` is the shared control layer used by the macOS app and OpenClaw.
Every command connects, performs one action, prints a machine-readable
`OK {...}` or `ERROR ...` result, and exits.

```bash
karlctl status
karlctl wake
karlctl look left
karlctl look up
karlctl look tilt-right
karlctl body right
karlctl antennas up
karlctl track on
karlctl emotion curious1
karlctl nod
karlctl shake
karlctl speak "Hello from Karl"
karlctl eyes 0,80,255
karlctl blink random 6
karlctl eyes-idle 40,35,30
karlctl see --out /tmp/karl-view.jpg
karlctl demo
```

Movement uses the daemon's documented REST API with named `roll`, `pitch`,
and `yaw` values, so the direction controls match the labels in the macOS
app. Camera snapshots use Reachy Mini 1.10's `get_frame_jpeg()` API instead
of competing with the daemon for direct OpenCV camera access.

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

Shared script configuration lives in `karl_config.py`. It resolves voice-model
paths relative to the repository, restricts SDK connections to the local
daemon, and provides Karl's calibrated `[0.15, -0.25]` antenna rest position.

### Interactive experiences

- **`reachy_wake.py`** — Karl idles quietly until he hears **"Hey Karl"**,
  then records your request, thinks, and replies. Best for hands-free,
  always-on use.
- **`reachy_listen.py`** — a continuous back-and-forth conversation that
  also tracks the speaker's direction (DoA) and turns toward whoever is
  talking.
- **`reachy_greet.py`** — uses the official daemon face tracker to recognize
  a visitor, retains low-light motion detection as a fallback, and generates
  a brief Karl-style greeting.
- **`reachy_gpp.py`** — runs Karl's autonomous Genuine People Personality:
  face following, DoA-assisted attention, natural blinking, daytime naps,
  overnight sleep, and rare local remarks.

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
| `speak.py` | macOS `say` | No | Compatibility demo using the same offline synthesis path as `reachy_say.py`. |

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

> **USB startup recovery:** The ESP32 can enumerate but remain unresponsive
> after the robot powers on. The eye drivers automatically recover this state
> by resetting the Espressif USB device and restarting the application through
> its serial control lines. They also auto-detect the changing `/dev/cu.*`
> device path.
>
> On Karl's tested setup, flashing the XIAO through the internal USB hub
> fails because esptool reports "No serial data received." Use a direct USB-C
> connection for firmware updates. Runtime serial eye control through the
> internal hub works normally.
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



**Serial protocol** (newline-terminated). The XIAO ESP32-C6 uses native
USB-Serial/JTAG, which **ignores the baud rate** — the `115200` in the
drivers is nominal. `RESET` reboots responsive firmware; when the board is
silent, the Python drivers instead reset the USB device and pulse its serial
control lines before retrying `PING`.

| Command | Action |
|---------|--------|
| `L0:r,g,b` | Set left eye (values 0–255) |
| `L1:r,g,b` | Set right eye |
| `LA:r,g,b` | Set both eyes |
| `OFF` | Turn both LEDs off |
| `RESET` | Soft-reboot the board (re-emits `READY` on boot) |
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
- **Software:** Python 3.11+, `reachy-mini==1.10.0`, [Ollama](https://ollama.com) with a model (e.g. `llama3.2`), Swift 6.2+ to build Karl Controller
- **OS:** macOS on Apple Silicon for the complete tested stack and native controller; the Python control code may also work on Linux

Karl starts the daemon with an isolated Hugging Face home at
`~/.config/karl/huggingface`, so a token stored in the normal user account
does not automatically enable Reachy's remote signaling relay. Set
`KARL_HF_HOME` before running `start_karl.sh` only when remote access is
intentionally required.

## Known Limitations

- On Karl's current setup, flashing the XIAO ESP32-C6 through the Reachy
  Mini's internal USB hub fails with "No serial data received." Firmware
  updates require a direct USB-C connection, while runtime serial control
  works through the hub.
- The committed macOS app is source code, not a signed/notarized release.
  `build_app.sh` creates an ad-hoc signed local build.
- Karl Controller defaults to this machine's repository, Python environment,
  and daemon paths. `KARL_REPO` overrides the repository path, but fully
  portable dependency discovery is still future work.
- The official conversation app has its own dependency set. Karl's
  control/daemon environment and conversation-app environment are
  intentionally kept separate.
- Camera and microphone access are subject to macOS privacy permissions for
  the process launching the command.

## License

MIT
