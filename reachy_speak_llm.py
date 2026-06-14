"""Reachy Mini speaks using a local LLM (Ollama) and local TTS (Piper).
Fully offline — no internet required.

Dependencies:
    pip install reachy-mini ollama piper-tts scipy

Voice model (download once):
    mkdir -p piper_models
    curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx" -o piper_models/en_US-amy-medium.onnx
    curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json" -o piper_models/en_US-amy-medium.onnx.json
"""

import sys
import time
import numpy as np
import ollama
from piper import PiperVoice
from scipy.signal import resample
from reachy_mini import ReachyMini

# --- Config ---
OLLAMA_MODEL = "llama3.2"
PIPER_MODEL = "piper_models/en_GB-northern_english_male-medium.onnx"
PIPER_CONFIG = "piper_models/en_GB-northern_english_male-medium.onnx.json"
ROBOT_SAMPLE_RATE = 16000
SYSTEM_PROMPT = (
    "You are Reachy Mini, a small friendly desktop robot. "
    "Keep replies to 1-2 short sentences. "
    "Do not include actions in asterisks or emojis — your words will be spoken aloud."
)


def llm_generate(prompt: str, history: list[dict] | None = None) -> str:
    """Generate a response from the local LLM."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    resp = ollama.chat(model=OLLAMA_MODEL, messages=messages)
    return resp.message.content


def tts_synthesize(text: str, voice: PiperVoice, pitch_shift: float = 0.95) -> np.ndarray:
    """Convert text to 16kHz float32 mono samples using Piper.

    pitch_shift: < 1.0 = deeper, > 1.0 = higher.
    """
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


def speak(mini: ReachyMini, voice: PiperVoice, text: str):
    """Speak text through the robot's speaker."""
    print(f'🗣️  "{text}"')
    samples = tts_synthesize(text, voice)
    duration = len(samples) / ROBOT_SAMPLE_RATE

    mini.media.push_audio_sample(samples.reshape(-1, 1))
    time.sleep(duration + 0.3)


def main():
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Say hello and introduce yourself!"

    print("🤖 Loading Piper voice model...")
    voice = PiperVoice.load(PIPER_MODEL, PIPER_CONFIG)

    print(f"💬 Asking LLM ({OLLAMA_MODEL})...")
    reply = llm_generate(prompt)

    with ReachyMini(media_backend="default") as mini:
        mini.media.start_playing()
        speak(mini, voice, reply)
        mini.media.stop_playing()

    print("✅ Done!")


if __name__ == "__main__":
    main()
