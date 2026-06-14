"""Reachy Mini speaks with animated head and antenna movements."""

import time
import threading
import numpy as np
import ollama
from piper import PiperVoice
from scipy.signal import resample
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

OLLAMA_MODEL = "llama3.2"
PIPER_MODEL = "piper_models/en_GB-northern_english_male-medium.onnx"
PIPER_CONFIG = "piper_models/en_GB-northern_english_male-medium.onnx.json"
ROBOT_SAMPLE_RATE = 16000
SYSTEM_PROMPT = (
    "You are Reachy Mini, a small friendly desktop robot. "
    "Keep replies to 1-2 short sentences. "
    "Do not include actions in asterisks or emojis — your words will be spoken aloud."
)


def llm_generate(prompt: str) -> str:
    resp = ollama.chat(model=OLLAMA_MODEL, messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    return resp.message.content


def tts_synthesize(text: str, voice: PiperVoice, pitch_shift: float = 0.95) -> np.ndarray:
    """pitch_shift: < 1.0 = deeper, > 1.0 = higher."""
    chunks = list(voice.synthesize(text))
    if not chunks:
        return np.array([], dtype=np.float32)
    samples = np.concatenate([ch.audio_float_array for ch in chunks])
    src_rate = chunks[0].sample_rate
    # Pitch shift by resampling at altered rate
    effective_rate = src_rate * pitch_shift
    num_out = int(len(samples) * ROBOT_SAMPLE_RATE / effective_rate)
    samples = resample(samples, num_out).astype(np.float32)
    return samples


def animate_while_speaking(mini: ReachyMini, duration: float):
    """Animate head and antennas with smooth conversational motion.

    create_head_pose(x, y, z, roll, pitch, yaw, mm, degrees) → 4x4 matrix.
      - y: side-to-side (positive = left)
      - z: up/down
      - pitch: nod (positive = look down)
      - yaw: turn (positive = look left)
    """
    keyframes = [
        # (y,    z,     pitch, yaw,  ant_l, ant_r, dur)
        ( 0.02,  0.01,  0,     8,   0.3,  -0.1,  1.0),   # glance right + up
        (-0.02,  0.00,  3,    -8,  -0.1,   0.3,  1.0),   # glance left + nod
        ( 0.01,  0.02,  0,     5,   0.2,  -0.2,  0.8),   # slight right + up
        (-0.01, -0.01, -3,    -5,  -0.2,   0.2,  0.8),   # slight left
        ( 0.0,   0.01,  3,     0,   0.15, -0.15, 0.7),   # center nod
    ]

    start = time.time()
    i = 0
    while time.time() - start < duration:
        y, z, pitch, yaw, al, ar, dur = keyframes[i % len(keyframes)]
        remaining = duration - (time.time() - start)
        dur = min(dur, remaining)
        if dur < 0.1:
            break
        mini.goto_target(
            head=create_head_pose(y=y, z=z, pitch=pitch, yaw=yaw, mm=False, degrees=True),
            antennas=[al, ar],
            duration=dur,
            method="minjerk",
        )
        i += 1

    # Return to neutral
    mini.goto_target(
        head=create_head_pose(),
        antennas=[0, 0],
        duration=0.6,
        method="minjerk",
    )


def main():
    print("🤖 Loading voice model...")
    voice = PiperVoice.load(PIPER_MODEL, PIPER_CONFIG)

    print("💬 Asking LLM...")
    reply = llm_generate("Say hello and something cheerful!")
    print(f'🗣️  "{reply}"')

    samples = tts_synthesize(reply, voice)
    duration = len(samples) / ROBOT_SAMPLE_RATE

    with ReachyMini(media_backend="default") as mini:
        mini.media.start_playing()

        # Start animation in a background thread
        animator = threading.Thread(
            target=animate_while_speaking, args=(mini, duration)
        )
        animator.start()

        # Play speech
        mini.media.push_audio_sample(samples.reshape(-1, 1))

        # Wait for both to finish
        animator.join()
        time.sleep(0.3)
        mini.media.stop_playing()

    print("✅ Done!")


if __name__ == "__main__":
    main()
