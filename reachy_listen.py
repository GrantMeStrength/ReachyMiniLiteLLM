#!/usr/bin/env python3
"""
reachy_listen.py — Two-way conversation with Robot Karl.

Listens via the robot's microphone (Whisper STT), thinks via Ollama LLM,
speaks via Piper TTS with animated head/body movements.

Press Ctrl+C to stop. The robot listens for speech, then responds.

Usage:
    python reachy_listen.py
"""

import numpy as np
import time
import threading
import math

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose
from faster_whisper import WhisperModel
from piper import PiperVoice
from scipy.signal import resample
import ollama

from robot_karl_prompt import ROBOT_KARL_PROMPT as ROBOT_KARL_SYSTEM_PROMPT

# ── Config ──────────────────────────────────────────────────────────────
WHISPER_MODEL = "base.en"
OLLAMA_MODEL = "llama3.2"
VOICE_MODEL = "piper_models/en_GB-northern_english_male-medium.onnx"
PITCH_SHIFT = 0.95
ROBOT_SAMPLE_RATE = 16000
LISTEN_SECONDS = 4.0
SILENCE_THRESHOLD = 0.008  # RMS below this = silence (don't transcribe)
MIN_TRANSCRIPT_LEN = 3     # ignore very short spurious transcripts
ANTENNA_NEUTRAL = [0.08, -0.08]  # slight offset avoids trembling at exactly 0° (gearbox backlash)

# ── Animation keyframes ────────────────────────────────────────────────
SPEAKING_KEYFRAMES = [
    # (y, z, pitch, yaw, body_yaw, ant_l, ant_r, duration)
    (0, 10, 3, 5, 0.05, 0.2, -0.1, 0.7),
    (0, -5, -3, -8, -0.08, -0.1, 0.3, 0.8),
    (0, 5, 2, 10, 0.1, 0.3, -0.2, 0.7),
    (0, 0, -2, -5, -0.05, -0.2, 0.2, 0.8),
    (0, 8, 4, 3, 0.06, 0.1, -0.3, 0.7),
    (0, -3, -1, -6, -0.04, -0.15, 0.15, 0.8),
]

LISTENING_KEYFRAMES = [
    # Subtle "attentive" nod while listening
    (0, 5, 3, 0, 0, 0.15, -0.1, 1.5),
    (0, 0, -2, 0, 0, 0.08, -0.12, 1.5),
]


def animate_loop(mini, keyframes, stop_event):
    """Loop through keyframes until stop_event is set."""
    idx = 0
    while not stop_event.is_set():
        kf = keyframes[idx % len(keyframes)]
        y, z, pitch, yaw, body_yaw, ant_l, ant_r, dur = kf
        pose = create_head_pose(y=y, z=z, pitch=pitch, yaw=yaw, mm=True, degrees=True)
        mini.goto_target(head=pose, body_yaw=body_yaw, antennas=[ant_l, ant_r],
                         duration=dur, method="minjerk")
        idx += 1
    # Return to neutral
    mini.goto_target(head=create_head_pose(), body_yaw=0, antennas=ANTENNA_NEUTRAL,
                     duration=0.5, method="minjerk")

def record_audio(mini, duration):
    """Record from robot mic, return (mono_audio, doa_yaw_deg or None)."""
    mini.media.start_recording()
    time.sleep(0.1)  # let recording pipeline settle
    chunks = []
    doa_samples = []
    start = time.time()
    while time.time() - start < duration:
        try:
            chunk = mini.media.get_audio_sample()
            if hasattr(chunk, 'ndim') and chunk.ndim == 2:
                chunks.append(chunk)
            # Sample DoA periodically
            angle, active = mini.media.get_DoA()
            if active:
                doa_samples.append(-math.degrees(angle - math.pi / 2))  # negate: DoA convention is opposite to head yaw
        except Exception:
            time.sleep(0.005)
    mini.media.stop_recording()
    if not chunks:
        return np.zeros(int(ROBOT_SAMPLE_RATE * duration), dtype=np.float32), None
    audio = np.concatenate(chunks, axis=0)
    mono = audio.mean(axis=1)  # stereo → mono
    # Average DoA when speech was detected
    doa_yaw = np.mean(doa_samples) if doa_samples else None
    return mono, doa_yaw


def turn_toward_speaker(mini, doa_yaw_deg):
    """Smoothly turn head and body toward the detected speaker direction."""
    # Clamp to safe ranges
    head_yaw = max(-60, min(60, doa_yaw_deg))
    body_yaw_rad = math.radians(max(-40, min(40, doa_yaw_deg * 0.5)))
    pose = create_head_pose(yaw=head_yaw, degrees=True)
    mini.goto_target(head=pose, body_yaw=body_yaw_rad,
                     duration=0.6, method="minjerk")
    print(f"   🧭 Turned toward speaker ({doa_yaw_deg:+.0f}°)", flush=True)


def speak_animated(mini, voice, text, face_yaw=0):
    """Speak text with animated head movements, facing toward face_yaw degrees."""
    # Generate audio
    chunks = []
    for ch in voice.synthesize(text):
        chunks.append(ch.audio_float_array)
    if not chunks:
        return
    raw = np.concatenate(chunks)
    src_rate = voice.config.sample_rate
    num_samples = int(len(raw) * ROBOT_SAMPLE_RATE / (src_rate * PITCH_SHIFT))
    resampled = resample(raw, num_samples).astype(np.float32)
    audio_duration = len(resampled) / ROBOT_SAMPLE_RATE

    # Offset speaking keyframes toward the speaker
    offset_keyframes = []
    for (y, z, pitch, yaw, body_yaw, ant_l, ant_r, dur) in SPEAKING_KEYFRAMES:
        offset_keyframes.append((
            y, z, pitch,
            yaw + face_yaw * 0.7,  # bias gestures toward speaker
            body_yaw + math.radians(face_yaw * 0.3),
            ant_l, ant_r, dur
        ))

    # Start animation
    stop_anim = threading.Event()
    anim_thread = threading.Thread(target=animate_loop,
                                   args=(mini, offset_keyframes, stop_anim))
    anim_thread.start()

    # Play audio
    mini.media.start_playing()
    mini.media.push_audio_sample(resampled.reshape(-1, 1))
    time.sleep(audio_duration + 0.3)
    mini.media.stop_playing()

    # Stop animation
    stop_anim.set()
    anim_thread.join()


def main():
    print("Loading Whisper model...", flush=True)
    whisper = WhisperModel(WHISPER_MODEL, compute_type="int8")

    print("Loading Piper voice...", flush=True)
    voice = PiperVoice.load(VOICE_MODEL)

    print("Connecting to robot...", flush=True)
    mini = ReachyMini(media_backend="default")
    print("Connected! Robot Karl is listening...\n", flush=True)

    conversation_history = [
        {"role": "system", "content": ROBOT_KARL_SYSTEM_PROMPT},
    ]

    # Track speaker direction across turns
    speaker_yaw = 0  # degrees, 0 = straight ahead

    # Quick greeting
    speak_animated(mini, voice, "Right then. I'm listening. What do you want?")

    try:
        while True:
            # Listening animation
            stop_listen_anim = threading.Event()
            listen_thread = threading.Thread(
                target=animate_loop,
                args=(mini, LISTENING_KEYFRAMES, stop_listen_anim)
            )
            listen_thread.start()

            print("🎤 Listening...", flush=True)
            mono, doa_yaw = record_audio(mini, LISTEN_SECONDS)

            stop_listen_anim.set()
            listen_thread.join()

            # Check for silence
            rms = np.sqrt(np.mean(mono ** 2))
            if rms < SILENCE_THRESHOLD:
                print("   (silence)", flush=True)
                continue

            # Turn toward speaker if DoA detected
            if doa_yaw is not None:
                speaker_yaw = doa_yaw
                turn_toward_speaker(mini, speaker_yaw)

            # Transcribe
            print("🧠 Transcribing...", flush=True)
            segments, info = whisper.transcribe(mono, language="en")
            text = " ".join(seg.text for seg in segments).strip()

            if len(text) < MIN_TRANSCRIPT_LEN:
                print(f"   (too short: '{text}')", flush=True)
                continue

            print(f"👤 You: {text}", flush=True)

            # LLM response
            conversation_history.append({"role": "user", "content": text})
            response = ollama.chat(model=OLLAMA_MODEL, messages=conversation_history)
            reply = response["message"]["content"]
            conversation_history.append({"role": "assistant", "content": reply})

            # Keep history manageable
            if len(conversation_history) > 20:
                conversation_history = conversation_history[:1] + conversation_history[-18:]

            print(f"🤖 Karl: {reply}\n", flush=True)

            # Speak while facing the speaker
            speak_animated(mini, voice, reply, face_yaw=speaker_yaw)

    except KeyboardInterrupt:
        print("\n\nStopping...")
        mini.goto_target(head=create_head_pose(), body_yaw=0, antennas=ANTENNA_NEUTRAL,
                         duration=0.5, method="minjerk")
        print("Goodbye!")


if __name__ == "__main__":
    main()
