"""Make Robot Karl speak — fully offline using macOS `say`.

No internet, no model downloads, no Ollama. Uses the built-in macOS speech
synthesizer to generate audio and plays it through the robot's speaker.

Karl's voice is a British (English UK) accent — defaults to "Daniel", the
standard en_GB male voice, to match his Northern English Piper persona.

Usage:
    python reachy_say.py                       # default greeting
    python reachy_say.py "Right then, let's go!"
    python reachy_say.py -v Reed "Ey up!"      # pick another en_GB voice

List British voices:
    say -v '?' | grep en_GB
"""

import argparse
import os
import subprocess
import tempfile
import time
import wave

import numpy as np
from reachy_mini import ReachyMini

SAMPLE_RATE = 16000
DEFAULT_VOICE = "Daniel"  # en_GB male — closest match to Karl's dialect
DEFAULT_TEXT = "Hello! I am Robot Karl. Nice to meet you!"


def text_to_samples(text: str, voice: str) -> np.ndarray:
    """Synthesize text with macOS `say` and return 16kHz float32 mono samples."""
    with tempfile.TemporaryDirectory() as tmp:
        aiff_path = os.path.join(tmp, "speech.aiff")
        wav_path = os.path.join(tmp, "speech.wav")

        # macOS offline TTS → AIFF
        subprocess.run(["say", "-v", voice, "-o", aiff_path, text], check=True)

        # AIFF → 16kHz mono PCM16 WAV
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", f"LEI16@{SAMPLE_RATE}", "-c", "1",
             aiff_path, wav_path],
            check=True, capture_output=True,
        )

        with wave.open(wav_path) as w:
            raw = w.readframes(w.getnframes())
            return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def main():
    parser = argparse.ArgumentParser(description="Robot Karl offline speech (macOS say).")
    parser.add_argument("text", nargs="*", help="What Karl should say.")
    parser.add_argument("-v", "--voice", default=DEFAULT_VOICE,
                        help=f"macOS voice name (default: {DEFAULT_VOICE}).")
    args = parser.parse_args()

    text = " ".join(args.text) if args.text else DEFAULT_TEXT
    print(f'🗣️  [{args.voice}] "{text}"')

    samples = text_to_samples(text, args.voice)
    duration = len(samples) / SAMPLE_RATE
    print(f"   Audio: {duration:.1f}s")

    with ReachyMini(media_backend="default") as mini:
        mini.media.start_playing()
        mini.media.push_audio_sample(samples.reshape(-1, 1))
        time.sleep(duration + 0.5)
        mini.media.stop_playing()

    print("✅ Done!")


if __name__ == "__main__":
    main()
