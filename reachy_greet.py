"""Reachy Mini watches for a person and greets them.

Uses motion detection on the robot's camera. When significant motion is
detected after a period of stillness, Robot Karl says hello with animated movement.
Works in low light where face detection would fail.

Usage:
    python reachy_greet.py
    # Press Ctrl+C to stop
"""

import time
import threading
import numpy as np
import cv2
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

SYSTEM_PROMPT = (
    "You are Robot Karl, a small friendly desktop robot. "
    "Someone just walked into the room. Greet them warmly in 1-2 short sentences. "
    "Do not include actions in asterisks or emojis — your words will be spoken aloud."
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
        head=create_head_pose(), antennas=[0, 0], body_yaw=0.0,
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


def main():
    print("🤖 Loading voice model...")
    voice = PiperVoice.load(PIPER_MODEL, PIPER_CONFIG)

    print("👀 Watching for visitors... (Ctrl+C to stop)")
    last_greet_time = 0
    prev_gray = None
    motion_count = 0

    with ReachyMini(media_backend="default") as mini:
        try:
            while True:
                frame = mini.media.get_frame()
                if frame is None:
                    time.sleep(CHECK_INTERVAL)
                    continue

                # Convert to small grayscale for fast comparison
                small = cv2.resize(frame, (320, 180))
                gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                if prev_gray is not None:
                    diff = cv2.absdiff(prev_gray, gray)
                    mean_diff = diff.mean()

                    if mean_diff > MOTION_THRESHOLD:
                        motion_count += 1
                        if motion_count == 1:
                            print(f"   Motion detected (diff={mean_diff:.1f})...")
                    else:
                        motion_count = 0

                    now = time.time()
                    if motion_count >= MOTION_FRAMES and now - last_greet_time > COOLDOWN_SECONDS:
                        print("😊 Someone's here! Generating greeting...")
                        resp = ollama.chat(model=OLLAMA_MODEL, messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": "Someone just appeared! Say hello."},
                        ])
                        greeting = resp.message.content
                        print(f'🗣️  "{greeting}"')
                        speak_and_animate(mini, voice, greeting)
                        last_greet_time = time.time()
                        motion_count = 0
                        prev_gray = None  # reset baseline after greeting
                        time.sleep(2)
                        continue

                prev_gray = gray
                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n👋 Stopping watcher.")


if __name__ == "__main__":
    main()
