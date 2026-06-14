"""Play a cheerful beep melody through Reachy Mini's speaker."""

from reachy_mini import ReachyMini
import numpy as np
import time

SAMPLE_RATE = 16000

def make_tone(freq_hz: float, duration_s: float, volume: float = 0.5) -> np.ndarray:
    """Generate a sine wave tone."""
    t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), endpoint=False)
    tone = (volume * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)
    return tone

def make_melody() -> np.ndarray:
    """Create a short happy melody: C-E-G-C(high)."""
    notes = [
        (523, 0.15),   # C5
        (659, 0.15),   # E5
        (784, 0.15),   # G5
        (1047, 0.30),  # C6 (longer)
    ]
    gap = np.zeros(int(SAMPLE_RATE * 0.05), dtype=np.float32)
    parts = []
    for freq, dur in notes:
        parts.append(make_tone(freq, dur))
        parts.append(gap)
    return np.concatenate(parts)

with ReachyMini(media_backend="default") as mini:
    print("🔊 Playing melody...")
    mini.media.start_playing()

    melody = make_melody()
    # Robot expects (samples, channels) — reshape to mono
    mini.media.push_audio_sample(melody.reshape(-1, 1))
    time.sleep(len(melody) / SAMPLE_RATE + 0.5)

    mini.media.stop_playing()
    print("✅ Done!")
