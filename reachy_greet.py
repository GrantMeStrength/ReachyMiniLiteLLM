"""Reachy Mini watches for a person and greets them.

Uses the Reachy Mini daemon's face tracker, with lightweight motion detection
as a low-light fallback. When a visitor is detected, Robot Karl says hello
with animated movement.

Usage:
    python reachy_greet.py
    # Press Ctrl+C to stop
"""

import time
import threading
import numpy as np
import ollama
from piper import PiperVoice
from scipy.signal import resample
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

# --- Config ---
OLLAMA_MODEL = "llama3.2"
PIPER_MODEL = "piper_models/en_GB-northern_english_male-medium.onnx"
PIPER_CONFIG = "piper_models/en_GB-northern_english_male-medium.onnx.json"
ROBOT_SAMPLE_RATE = 16000
PITCH_SHIFT = 0.95
COOLDOWN_SECONDS = 30  # don't re-greet for this long
CHECK_INTERVAL = 0.5   # seconds between camera checks
MOTION_THRESHOLD = 5.0  # mean pixel diff to count as motion
MOTION_FRAMES = 3       # consecutive motion frames before greeting
FACE_FRAMES = 2         # consecutive face observations before greeting
TRACKING_WEIGHT = 0.35  # gently follow visitors without dominating motion
ANTENNA_NEUTRAL = [0.15, -0.25]  # verified outside Karl's backlash zone

from robot_karl_prompt import ROBOT_KARL_PROMPT

SYSTEM_PROMPT = ROBOT_KARL_PROMPT + (
    "\nContext: Someone just walked into the room. "
    "Greet them in your typical dry, casual style."
)


def tts_synthesize(text: str, voice: PiperVoice) -> np.ndarray:
    """Convert text to 16kHz float32 mono samples."""
    chunks = list(voice.synthesize(text))
    if not chunks:
        return np.array([], dtype=np.float32)
    samples = np.concatenate([ch.audio_float_array for ch in chunks])
    src_rate = chunks[0].sample_rate
    effective_rate = src_rate * PITCH_SHIFT
    num_out = int(len(samples) * ROBOT_SAMPLE_RATE / effective_rate)
    return resample(samples, num_out).astype(np.float32)


def animate_while_speaking(mini: ReachyMini, duration: float):
    """Smooth head/body/antenna animation during speech."""
    keyframes = [
        ( 0.02,  0.01,  0,     8,    0.15,   0.3,  -0.1,  1.0),
        (-0.02,  0.00,  3,    -8,   -0.15,  -0.1,   0.3,  1.0),
        ( 0.01,  0.02,  0,     5,    0.1,    0.2,  -0.2,  0.8),
        (-0.01, -0.01, -3,    -5,   -0.1,   -0.2,   0.2,  0.8),
        ( 0.0,   0.01,  3,     0,    0.0,    0.15, -0.15, 0.7),
    ]
    start = time.time()
    i = 0
    while time.time() - start < duration:
        y, z, pitch, yaw, byaw, al, ar, dur = keyframes[i % len(keyframes)]
        remaining = duration - (time.time() - start)
        dur = min(dur, remaining)
        if dur < 0.1:
            break
        mini.goto_target(
            head=create_head_pose(y=y, z=z, pitch=pitch, yaw=yaw, mm=False, degrees=True),
            antennas=[al, ar], body_yaw=byaw, duration=dur, method="minjerk",
        )
        i += 1
    mini.goto_target(
        head=create_head_pose(), antennas=ANTENNA_NEUTRAL, body_yaw=0.0,
        duration=0.6, method="minjerk",
    )


def speak_and_animate(mini: ReachyMini, voice: PiperVoice, text: str):
    """Speak text with animation."""
    samples = tts_synthesize(text, voice)
    duration = len(samples) / ROBOT_SAMPLE_RATE

    mini.media.start_playing()
    animator = threading.Thread(target=animate_while_speaking, args=(mini, duration))
    animator.start()
    mini.media.push_audio_sample(samples.reshape(-1, 1))
    animator.join()
    time.sleep(0.3)
    mini.media.stop_playing()


def motion_level(frame: np.ndarray, previous: np.ndarray | None):
    """Calculate motion from a sparse grayscale sample without OpenCV."""
    sampled = frame[::6, ::6].astype(np.float32)
    gray = (
        sampled[:, :, 0] * 0.299
        + sampled[:, :, 1] * 0.587
        + sampled[:, :, 2] * 0.114
    )
    if previous is None:
        return gray, 0.0
    return gray, float(np.abs(gray - previous).mean())


def main():
    print("🤖 Loading voice model...")
    voice = PiperVoice.load(PIPER_MODEL, PIPER_CONFIG)

    print("👀 Watching for visitors... (Ctrl+C to stop)")
    last_greet_time = 0
    prev_gray = None
    motion_count = 0
    face_count = 0

    with ReachyMini(
        media_backend="default", connection_mode="localhost_only"
    ) as mini:
        mini.start_head_tracking(weight=TRACKING_WEIGHT)
        try:
            while True:
                frame = mini.media.get_frame()
                if frame is None:
                    time.sleep(CHECK_INTERVAL)
                    continue

                gray, mean_diff = motion_level(frame, prev_gray)
                prev_gray = gray
                motion_count = motion_count + 1 if mean_diff > MOTION_THRESHOLD else 0
                face = mini.get_tracked_face(wait=False)
                face_count = face_count + 1 if face.detected else 0

                now = time.time()
                visitor_seen = face_count >= FACE_FRAMES or motion_count >= MOTION_FRAMES
                if visitor_seen and now - last_greet_time > COOLDOWN_SECONDS:
                    reason = "face" if face_count >= FACE_FRAMES else "motion"
                    print(f"😊 Visitor detected by {reason}! Generating greeting...")
                    resp = ollama.chat(model=OLLAMA_MODEL, messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": "Someone just appeared! Say hello."},
                    ])
                    greeting = resp.message.content
                    print(f'🗣️  "{greeting}"')
                    mini.stop_head_tracking()
                    speak_and_animate(mini, voice, greeting)
                    mini.start_head_tracking(weight=TRACKING_WEIGHT)
                    last_greet_time = time.time()
                    motion_count = 0
                    face_count = 0
                    prev_gray = None
                    time.sleep(2)
                    continue

                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n👋 Stopping watcher.")
        finally:
            mini.stop_head_tracking()


if __name__ == "__main__":
    main()
