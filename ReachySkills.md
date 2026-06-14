# Reachy Mini Lite — Skills File

> **Hardware:** USB Lite version (no onboard RPi, no IMU, no Wi-Fi).
> All code runs on the connected Mac/PC. The daemon bridges USB serial to a local REST/WebSocket API.

---

## 1. Environment Setup

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate          # Windows
pip install reachy-mini          # core SDK
# pip install reachy-mini[full]  # adds AI / simulation extras
```

## 2. Starting the Daemon

The daemon handles low-level USB serial communication. It **must** be running before any SDK code connects.

```bash
# Auto-detect serial port
reachy-mini-daemon

# Explicit port (if auto-detect fails)
reachy-mini-daemon --serialport /dev/tty.usbmodem*   # macOS typical
# reachy-mini-daemon --serialport /dev/ttyACM0       # Linux
# reachy-mini-daemon --serialport COM3               # Windows

# With dashboard (deprecated — use the Desktop App instead)
python -m reachy_mini.daemon.app.main --fastapi-port 8000
# Open http://localhost:8000 for status & camera feed
```

> **Tip:** The official **Reachy Mini Control Desktop App** is the easiest way to verify connectivity and check robot status before writing code.

## 3. Connecting from Python

```python
from reachy_mini import ReachyMini

# Auto-detects USB/localhost connection
with ReachyMini() as mini:
    print("Connected!")
```

The SDK auto-detects whether to use USB/localhost or network. Force a mode if needed:

```python
ReachyMini(connection_mode="localhost_only")   # USB Lite — force local
ReachyMini(connection_mode="network")          # wireless version
```

## 4. Movement

### 4a. Smooth Movement — `goto_target()`

Interpolates smoothly to a target pose over a given duration.

**Parameters:**
- `head` — a pose from `create_head_pose()` (see §5)
- `antennas` — `[left, right]` in radians (positive = outward)
- `body_yaw` — body rotation in radians
- `duration` — seconds for the move
- `method` — interpolation: `"minjerk"` (default, smoothest), `"linear"`, `"ease_in_out"`, `"cartoon"` (bouncy)

> **Note:** The Seeed tutorial docs show uppercase `"MIN_JERK"` etc. but the SDK requires
> **lowercase**: `"minjerk"`, `"linear"`, `"ease_in_out"`, `"cartoon"`.

```python
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose
import numpy as np

with ReachyMini() as mini:
    mini.goto_target(
        head=create_head_pose(z=10, mm=True),
        antennas=np.deg2rad([45, 45]),
        body_yaw=np.deg2rad(30),
        duration=2.0,
        method="minjerk"
    )
```

### 4b. Instant Control — `set_target()`

Bypasses interpolation — use for real-time tracking, joystick control, or generated trajectories.

```python
mini.set_target(
    head=create_head_pose(x=5, y=0, z=0, mm=True),
    antennas=[0.3, -0.3],
    body_yaw=0.0
)
```

### 4c. Motor Management

```python
mini.enable_motors()    # take control of servos
mini.disable_motors()   # release servos (compliant / limp mode)
mini.wake_up()          # power on + stand ready
mini.goto_sleep()       # safe shutdown pose
```

### 4d. Query Current State

```python
pose = mini.get_current_head_pose()
joints = mini.get_current_joint_positions()
```

## 5. Head Pose Helper — `create_head_pose()`

Returns a 4×4 homogeneous transformation matrix for use with `goto_target()` or `set_target()`.

```python
create_head_pose(x=0, y=0, z=0, roll=0, pitch=0, yaw=0, mm=False, degrees=True)
```

**Axis reference (facing the robot):**

| Parameter | What it does | Positive direction |
|-----------|-------------|-------------------|
| `x` | Forward / back | Lean forward |
| `y` | Side to side | Move left |
| `z` | Up / down | Move up |
| `roll` | Tilt head | Tilt left |
| `pitch` | Nod | Look down |
| `yaw` | Turn | Turn left |

**Units:** Set `mm=True` for millimetres (x/y/z), `degrees=True` for degrees (roll/pitch/yaw).
Default is metres + degrees.

```python
from reachy_mini.utils import create_head_pose

# Look slightly left and down
create_head_pose(yaw=10, pitch=5, degrees=True)

# Translate up 10mm
create_head_pose(z=10, mm=True)

# Combine translation + rotation
create_head_pose(y=0.02, z=0.01, pitch=3, yaw=8, mm=False, degrees=True)
```

### 5a. `look_at_world()` and `look_at_image()`

```python
# Look at a 3D point in world space (metres)
mini.look_at_world(x=0.5, y=0.0, z=0.3, duration=1.0, perform_movement=True)

# Look at a pixel in the camera image
mini.look_at_image(u=320, v=240, duration=0.5, perform_movement=True)
```

### 5b. Automatic Body Yaw

When enabled (default), the body auto-rotates to help the head reach target positions.

```python
mini.set_automatic_body_yaw(True)    # enable (default)
mini.set_automatic_body_yaw(False)   # disable — body stays fixed
```

## 6. Camera 📷

```python
with ReachyMini(media_backend="default") as mini:
    frame = mini.media.get_frame()
    # frame is a numpy array: shape (1080, 1920, 3), dtype uint8 (RGB)
```

> **Dep:** `pip install opencv-python Pillow`

### 6a. Save a Snapshot

```python
from PIL import Image

with ReachyMini(media_backend="default") as mini:
    frame = mini.media.get_frame()
    Image.fromarray(frame).save("snapshot.jpg")
```

### 6b. Face Detection (OpenCV Haar Cascade)

Works best in reasonable lighting. Mean brightness < ~40/255 = too dark for reliable detection.

```python
import cv2

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

with ReachyMini(media_backend="default") as mini:
    frame = mini.media.get_frame()
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    # Strict (fewer false positives)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5, minSize=(80, 80))

    # Lenient (better in low light, more false positives)
    # faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(40, 40))

    for (x, y, w, h) in faces:
        print(f"Face at ({x},{y}) size {w}x{h}")
```

### 6c. Motion Detection (Frame Differencing)

More robust than face detection in low light. Compares consecutive frames to detect movement.

```python
import cv2
import numpy as np
import time

MOTION_THRESHOLD = 5.0  # mean pixel diff to count as motion
MOTION_FRAMES = 3       # consecutive motion frames before triggering

with ReachyMini(media_backend="default") as mini:
    prev_gray = None
    motion_count = 0

    while True:
        frame = mini.media.get_frame()
        small = cv2.resize(frame, (320, 180))
        gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if prev_gray is not None:
            diff = cv2.absdiff(prev_gray, gray)
            mean_diff = diff.mean()

            if mean_diff > MOTION_THRESHOLD:
                motion_count += 1
            else:
                motion_count = 0

            if motion_count >= MOTION_FRAMES:
                print(f"Motion detected! (diff={mean_diff:.1f})")
                motion_count = 0
                prev_gray = None  # reset baseline
                time.sleep(2)
                continue

        prev_gray = gray
        time.sleep(0.5)
```

### 6d. Camera Brightness / Dark Image Fix

The 160° wide-angle camera can produce very dark images on macOS due to a known
GStreamer auto-exposure bug ([issue #963](https://github.com/pollen-robotics/reachy_mini/issues/963)).

**Fixes (in order):**

1. **Update firmware:** Reachy Mini Control app → ⚙️ → *Check for updates*. 
   Restart: press OFF, wait 5 seconds, press ON.
2. **Reset macOS exposure:** The GStreamer backend on Mac sometimes defaults to the
   lowest exposure. **Open FaceTime or Photo Booth briefly** after starting the Reachy
   stream — this forces macOS to reset the exposure correctly.
3. **CameraController app (best fix):** Install [CameraController](https://github.com/itaybre/CameraController)
   (open-source USB camera control for macOS). Switch from **basic to advanced** settings —
   this has been reported to fix the issue. You can also manually tune exposure from there.
4. **Improve room lighting:** The 160° wide-angle sensor struggles in low light.
   Use bright workspace lighting for best results.

**Check brightness programmatically:**
```python
gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
brightness = gray.mean()  # 0–255; below ~40 = very dark
```

> **Tip:** Use motion detection instead of face detection in dark rooms.
> See `reachy_greet.py` for a full example that detects someone entering and speaks a greeting.

## 7. Audio 🎙️🔊

> Audio uses 16 kHz sample rate, float32, stereo input / mono or stereo output.
> `push_audio_sample()` is **non-blocking** — it returns immediately while audio plays.
> Always `time.sleep()` for the audio duration if you need to wait for playback.

### 7a. Recording & Playback (Raw Audio)

```python
from reachy_mini import ReachyMini
from scipy.signal import resample
import time

with ReachyMini(media_backend="default") as mini:
    mini.media.start_recording()
    mini.media.start_playing()

    # Record
    samples = mini.media.get_audio_sample()
    # samples: numpy (N, 2) float32 @ 16 kHz

    # Resample if input/output rates differ
    out_rate = mini.media.get_output_audio_samplerate()
    in_rate  = mini.media.get_input_audio_samplerate()
    samples = resample(samples, int(out_rate * len(samples) / in_rate))

    # Playback (non-blocking — returns immediately)
    mini.media.push_audio_sample(samples)
    time.sleep(len(samples) / out_rate)

    # Direction of Arrival (0 = left, π/2 = front, π = right)
    doa, is_speech = mini.media.get_DoA()

    mini.media.stop_recording()
    mini.media.stop_playing()
```

### 7b. Playing Tones & Melodies (No Internet Required)

Generate tones programmatically with numpy and push directly to the speaker.

```python
from reachy_mini import ReachyMini
import numpy as np
import time

SAMPLE_RATE = 16000

def make_tone(freq_hz: float, duration_s: float, volume: float = 0.5) -> np.ndarray:
    t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), endpoint=False)
    return (volume * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)

# Example: C-E-G-C arpeggio
notes = [(523, 0.15), (659, 0.15), (784, 0.15), (1047, 0.30)]
gap = np.zeros(int(SAMPLE_RATE * 0.05), dtype=np.float32)
parts = []
for freq, dur in notes:
    parts.append(make_tone(freq, dur))
    parts.append(gap)
melody = np.concatenate(parts)

with ReachyMini(media_backend="default") as mini:
    mini.media.start_playing()
    mini.media.push_audio_sample(melody.reshape(-1, 1))  # mono: (N, 1)
    time.sleep(len(melody) / SAMPLE_RATE + 0.5)
    mini.media.stop_playing()
```

### 7c. Text-to-Speech (Requires Internet)

> **Deps:** `pip install gtts`
>
> **macOS note:** Both `say -o` and `pyttsx3.save_to_file()` produce truncated audio on
> recent macOS versions. Use **gTTS** (Google TTS) instead — it generates proper MP3 files
> which are then converted to 16 kHz WAV via macOS `afconvert`.

```python
from reachy_mini import ReachyMini
from gtts import gTTS
import subprocess
import numpy as np
import wave
import time
import tempfile
import os

SAMPLE_RATE = 16000

def text_to_samples(text: str) -> np.ndarray:
    """Convert text to 16kHz float32 mono audio via Google TTS."""
    with tempfile.TemporaryDirectory() as tmp:
        mp3_path = os.path.join(tmp, "speech.mp3")
        wav_path = os.path.join(tmp, "speech.wav")

        gTTS(text, lang="en").save(mp3_path)

        # macOS: afconvert MP3 → 16kHz mono PCM16 WAV
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", f"LEI16@{SAMPLE_RATE}", "-c", "1",
             mp3_path, wav_path],
            check=True, capture_output=True
        )

        with wave.open(wav_path) as w:
            raw = w.readframes(w.getnframes())
            return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

with ReachyMini(media_backend="default") as mini:
    samples = text_to_samples("Hello! I am Reachy Mini! Nice to meet you!")

    mini.media.start_playing()
    mini.media.push_audio_sample(samples.reshape(-1, 1))
    time.sleep(len(samples) / SAMPLE_RATE + 0.5)
    mini.media.stop_playing()
```

> **Cross-platform note:** On Linux, replace `afconvert` with `ffmpeg`:
> ```bash
> ffmpeg -i speech.mp3 -ar 16000 -ac 1 -f wav speech.wav
> ```

### 7d. LLM + Local TTS — Fully Offline Speech (Recommended)

Uses **Ollama** for intelligent responses and **Piper TTS** for natural-sounding voice
synthesis. Runs entirely on your machine — no internet needed after setup.

**One-time setup:**
```bash
pip install ollama piper-tts scipy

# Download a Piper voice model (~60MB)
mkdir -p piper_models
curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx" \
     -o piper_models/en_US-amy-medium.onnx
curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json" \
     -o piper_models/en_US-amy-medium.onnx.json
```

> **Other voices:** Browse https://huggingface.co/rhasspy/piper-voices — download any
> `.onnx` + `.onnx.json` pair into `piper_models/`.

**LLM response generation:**
```python
import ollama

SYSTEM_PROMPT = (
    "You are Reachy Mini, a small friendly desktop robot. "
    "Keep replies to 1-2 short sentences. "
    "Do not include actions in asterisks or emojis — your words will be spoken aloud."
)

def llm_generate(prompt: str) -> str:
    resp = ollama.chat(model="llama3.2", messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    return resp.message.content
```

**Piper TTS synthesis (22050 Hz → resampled to 16 kHz for robot):**
```python
from piper import PiperVoice
from scipy.signal import resample
import numpy as np

ROBOT_SAMPLE_RATE = 16000

voice = PiperVoice.load(
    "piper_models/en_US-amy-medium.onnx",
    "piper_models/en_US-amy-medium.onnx.json"
)

def tts_synthesize(text: str) -> np.ndarray:
    chunks = list(voice.synthesize(text))
    samples = np.concatenate([ch.audio_float_array for ch in chunks])
    src_rate = chunks[0].sample_rate
    if src_rate != ROBOT_SAMPLE_RATE:
        num_out = int(len(samples) * ROBOT_SAMPLE_RATE / src_rate)
        samples = resample(samples, num_out).astype(np.float32)
    return samples
```

**Putting it together — ask LLM, speak through robot:**
```python
from reachy_mini import ReachyMini
import time

reply = llm_generate("Say hello and introduce yourself!")
samples = tts_synthesize(reply)

with ReachyMini(media_backend="default") as mini:
    mini.media.start_playing()
    mini.media.push_audio_sample(samples.reshape(-1, 1))
    time.sleep(len(samples) / ROBOT_SAMPLE_RATE + 0.3)
    mini.media.stop_playing()
```

> **Verified working** with Ollama `llama3.2` and Piper `en_US-amy-medium` on macOS ARM.
> See `reachy_speak_llm.py` for the full runnable script.

### 7e. TTS Approach Comparison

| Approach | Voice Quality | Internet | Latency | Install |
|----------|--------------|----------|---------|---------|
| Numpy tones (§7b) | Beeps only | ❌ No | Instant | None |
| gTTS (§7c) | Decent | ✅ Yes | ~1-2s | `pip install gtts` |
| Piper TTS (§7d) | Good, natural | ❌ No | ~0.5s | `pip install piper-tts` + model |
| Piper + Ollama (§7d) | Good + smart | ❌ No | ~2-5s | Both above + `pip install ollama` |

## 8. Media Backend Options

| Backend | When to use |
|---------|-------------|
| `"default"` | Auto-detects LOCAL vs WEBRTC (recommended) |
| `"local"` | Force local — same machine as daemon (USB Lite) |
| `"webrtc"` | Force remote streaming (Linux clients only for now) |
| `"no_media"` | Release camera/audio so OpenCV or sounddevice can use them directly |

## 9. Recording & Replaying Motions

```python
with ReachyMini() as mini:
    mini.start_recording()
    # ... move the robot manually or via code ...
    recorded_data = mini.stop_recording()
    # Save / replay recorded_data later
```

## 10. Lite-Specific Limitations

| Feature | USB Lite | Wireless (RPi) |
|---------|----------|-----------------|
| IMU (accelerometer, gyro) | ❌ Not available | ✅ |
| On-device AI | ❌ Runs on host PC | ✅ On-board |
| Wi-Fi / Bluetooth | ❌ | ✅ |
| Camera | ✅ via USB | ✅ |
| Audio (mic + speaker) | ✅ via USB | ✅ |
| WebRTC remote streaming | ❌ (use `"local"`) | ✅ |

## 11. Example — Wave & Nod Hello

```python
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

with ReachyMini() as mini:
    # Wave antennas
    mini.goto_target(antennas=[0.6, -0.6], duration=0.3)
    mini.goto_target(antennas=[-0.6, 0.6], duration=0.3)
    mini.goto_target(antennas=[0, 0], duration=0.3)

    # Nod hello
    mini.goto_target(head=create_head_pose(z=15, degrees=True), duration=0.5)
    mini.goto_target(head=create_head_pose(z=-15, degrees=True), duration=0.5)
    mini.goto_target(head=create_head_pose(z=0, degrees=True), duration=0.5)
```

## 12. References

- **Getting started:** https://www.runreachyrun.com/getting-started
- **Python SDK docs:** https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/SDK/python-sdk.md
- **Seeed Studio wiki:** https://wiki.seeedstudio.com/reachymini_sdk_python-sdk/
- **PyPI:** https://pypi.org/project/reachy-mini/
- **Troubleshooting:** https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/troubleshooting.md