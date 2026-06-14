"""Make Reachy Mini speak words through its speaker using Google TTS."""

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
    """Convert text to 16kHz float32 mono audio samples."""
    with tempfile.TemporaryDirectory() as tmp:
        mp3_path = os.path.join(tmp, "speech.mp3")
        wav_path = os.path.join(tmp, "speech.wav")

        # Google TTS → MP3
        tts = gTTS(text, lang="en")
        tts.save(mp3_path)

        # MP3 → 16kHz mono PCM16 WAV
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", f"LEI16@{SAMPLE_RATE}", "-c", "1",
             mp3_path, wav_path],
            check=True, capture_output=True
        )

        with wave.open(wav_path) as w:
            raw = w.readframes(w.getnframes())
            return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


with ReachyMini(media_backend="default") as mini:
    text = "Hello! I am Reachy Mini! Nice to meet you!"
    print(f'🗣️ Speaking: "{text}"')

    samples = text_to_samples(text)
    duration = len(samples) / SAMPLE_RATE
    print(f"   Audio: {duration:.1f}s")

    mini.media.start_playing()
    mini.media.push_audio_sample(samples.reshape(-1, 1))
    time.sleep(duration + 0.5)
    mini.media.stop_playing()

    print("✅ Done!")
