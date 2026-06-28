#!/usr/bin/env python3
"""
reachy_wake.py — Always-listening Robot Karl with "Hey Karl" wake word.

The robot idles quietly, monitoring the mic for speech. When it detects
the wake phrase "Hey Karl" (or similar), it activates, records the user's
request, and responds with animated LLM-powered speech.

States:
    IDLE     → low-power listening, subtle idle animation
    WAKE     → wake word detected, recording user's full request
    RESPOND  → generating and speaking the reply

Press Ctrl+C to stop.

Usage:
    python -u reachy_wake.py
"""

import numpy as np
import time
import threading
import math
import re

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose
from faster_whisper import WhisperModel
from piper import PiperVoice
from scipy.signal import resample
import ollama
import reachy_leds

from robot_karl_prompt import ROBOT_KARL_PROMPT as ROBOT_KARL_SYSTEM_PROMPT

# ── Config ──────────────────────────────────────────────────────────────
WHISPER_MODEL = "base.en"
OLLAMA_MODEL = "llama3.2"
VOICE_MODEL = "piper_models/en_GB-northern_english_male-medium.onnx"
PITCH_SHIFT = 0.95
ROBOT_SAMPLE_RATE = 16000
ANTENNA_NEUTRAL = [0.08, -0.15]

# Wake word detection
WAKE_PHRASES = ["hey karl", "hey carl", "hey carol", "a]karl", "ok karl", "okay karl"]
WAKE_LISTEN_CHUNK = 2.0      # seconds per wake-word check
SPEECH_THRESHOLD = 0.006     # RMS to consider as speech (lower than conversation mode)
SILENCE_AFTER_WAKE = 0.8     # seconds of silence before stopping recording
REQUEST_MAX_SECONDS = 10.0   # max recording time after wake
REQUEST_MIN_SECONDS = 1.0    # min recording before checking for silence

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

IDLE_KEYFRAMES = [
    # Very subtle breathing-like movement
    (0, 2, 0, 0, 0, 0.09, -0.14, 3.0),
    (0, -1, 0, 0, 0, 0.07, -0.16, 3.0),
]

ALERT_KEYFRAMES = [
    # "I'm listening" — attentive posture
    (0, 8, 5, 0, 0, 0.25, -0.25, 0.8),
    (0, 5, 3, 0, 0, 0.15, -0.2, 1.5),
    (0, 6, 4, 0, 0, 0.2, -0.22, 1.5),
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


def record_chunk(mini, duration):
    """Record a short chunk, return (mono_audio, doa_yaw or None)."""
    mini.media.start_recording()
    time.sleep(0.05)
    chunks = []
    doa_samples = []
    start = time.time()
    while time.time() - start < duration:
        try:
            chunk = mini.media.get_audio_sample()
            if hasattr(chunk, 'ndim') and chunk.ndim == 2:
                chunks.append(chunk)
            angle, active = mini.media.get_DoA()
            if active:
                doa_samples.append(-math.degrees(angle - math.pi / 2))
        except Exception:
            time.sleep(0.005)
    mini.media.stop_recording()
    if not chunks:
        return np.zeros(int(ROBOT_SAMPLE_RATE * duration), dtype=np.float32), None
    audio = np.concatenate(chunks, axis=0)
    mono = audio.mean(axis=1)
    doa_yaw = np.mean(doa_samples) if doa_samples else None
    return mono, doa_yaw


def record_until_silence(mini, max_duration, silence_threshold, silence_duration, min_duration):
    """Record until silence is detected or max_duration reached."""
    mini.media.start_recording()
    time.sleep(0.05)
    chunks = []
    doa_samples = []
    start = time.time()
    last_speech_time = start

    while time.time() - start < max_duration:
        try:
            chunk = mini.media.get_audio_sample()
            if hasattr(chunk, 'ndim') and chunk.ndim == 2:
                chunks.append(chunk)
                # Check if this chunk has speech
                rms = np.sqrt(np.mean(chunk ** 2))
                if rms > silence_threshold:
                    last_speech_time = time.time()
            angle, active = mini.media.get_DoA()
            if active:
                doa_samples.append(-math.degrees(angle - math.pi / 2))
        except Exception:
            time.sleep(0.005)

        # Check for silence (only after min recording time)
        elapsed = time.time() - start
        if elapsed > min_duration and (time.time() - last_speech_time) > silence_duration:
            break

    mini.media.stop_recording()
    if not chunks:
        return np.zeros(int(ROBOT_SAMPLE_RATE * 0.5), dtype=np.float32), None
    audio = np.concatenate(chunks, axis=0)
    mono = audio.mean(axis=1)
    doa_yaw = np.mean(doa_samples) if doa_samples else None
    return mono, doa_yaw


def turn_toward_speaker(mini, doa_yaw_deg):
    """Smoothly turn head and body toward the detected speaker direction."""
    head_yaw = max(-60, min(60, doa_yaw_deg))
    body_yaw_rad = math.radians(max(-40, min(40, doa_yaw_deg * 0.5)))
    pose = create_head_pose(yaw=head_yaw, degrees=True)
    mini.goto_target(head=pose, body_yaw=body_yaw_rad,
                     duration=0.6, method="minjerk")
    print(f"   🧭 Turned toward speaker ({doa_yaw_deg:+.0f}°)", flush=True)


def speak_animated(mini, voice, text, face_yaw=0, led_ser=None):
    """Speak text with animated head movements and speaking-glow eyes."""
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

    offset_keyframes = []
    for (y, z, pitch, yaw, body_yaw, ant_l, ant_r, dur) in SPEAKING_KEYFRAMES:
        offset_keyframes.append((
            y, z, pitch,
            yaw + face_yaw * 0.7,
            body_yaw + math.radians(face_yaw * 0.3),
            ant_l, ant_r, dur
        ))

    stop_anim = threading.Event()
    anim_thread = threading.Thread(target=animate_loop,
                                   args=(mini, offset_keyframes, stop_anim))
    anim_thread.start()

    led_thread, led_stop = reachy_leds.start_speaking_leds(led_ser) if led_ser else (None, None)

    mini.media.start_playing()
    mini.media.push_audio_sample(resampled.reshape(-1, 1))
    time.sleep(audio_duration + 0.3)
    mini.media.stop_playing()

    stop_anim.set()
    anim_thread.join()
    if led_stop:
        led_stop.set()
        led_thread.join()


def contains_wake_word(text):
    """Check if transcribed text contains the wake phrase."""
    text_lower = text.lower().strip()
    for phrase in WAKE_PHRASES:
        if phrase in text_lower:
            return True
    # Also check with fuzzy matching for common Whisper mishearings
    if re.search(r'\bhey\b.*\bkar', text_lower):
        return True
    if re.search(r'\bok\b.*\bkar', text_lower):
        return True
    return False


def extract_after_wake(text):
    """Extract the request that comes after the wake word, if any."""
    text_lower = text.lower()
    for phrase in WAKE_PHRASES:
        idx = text_lower.find(phrase)
        if idx >= 0:
            after = text[idx + len(phrase):].strip()
            # Remove leading punctuation
            after = after.lstrip(".,!? ")
            return after
    # Regex fallback
    match = re.search(r'(?:hey|ok|okay)\s+kar\w*[,.]?\s*(.*)', text_lower)
    if match:
        return match.group(1).strip()
    return ""


def main():
    print("Loading Whisper model...", flush=True)
    whisper = WhisperModel(WHISPER_MODEL, compute_type="int8")

    print("Loading Piper voice...", flush=True)
    voice = PiperVoice.load(VOICE_MODEL)

    print("Connecting to robot...", flush=True)
    mini = ReachyMini(media_backend="default")
    led_ser = reachy_leds.connect()  # auto-detects eye ESP32; None if absent
    print("Connected! Robot Karl is waiting for 'Hey Karl'...\n", flush=True)

    conversation_history = [
        {"role": "system", "content": ROBOT_KARL_SYSTEM_PROMPT},
    ]

    speaker_yaw = 0

    # Idle state manages both the breathing animation and the idle eye blink.
    idle = {"anim_stop": None, "anim_thread": None, "led_thread": None, "led_stop": None}

    def start_idle():
        idle["anim_stop"] = threading.Event()
        idle["anim_thread"] = threading.Thread(
            target=animate_loop, args=(mini, IDLE_KEYFRAMES, idle["anim_stop"]))
        idle["anim_thread"].start()
        if led_ser:
            idle["led_thread"], idle["led_stop"] = reachy_leds.start_idle_leds(led_ser)

    def stop_idle():
        if idle["anim_stop"] is not None:
            idle["anim_stop"].set()
            idle["anim_thread"].join()
            idle["anim_stop"] = None
        if idle["led_stop"] is not None:
            idle["led_stop"].set()
            idle["led_thread"].join()
            idle["led_stop"] = None

    start_idle()

    try:
        while True:
            # ── IDLE STATE: listen for wake word ──
            mono, doa_yaw = record_chunk(mini, WAKE_LISTEN_CHUNK)
            rms = np.sqrt(np.mean(mono ** 2))

            if rms < SPEECH_THRESHOLD:
                continue  # silence, keep idling

            # Speech detected — check for wake word
            segments, _ = whisper.transcribe(mono, language="en")
            text = " ".join(seg.text for seg in segments).strip()

            if not text or len(text) < 3:
                continue

            if not contains_wake_word(text):
                # Speech but no wake word — ignore
                continue

            # ── WAKE STATE: wake word detected! ──
            print(f"🔔 Wake word detected! (heard: '{text}')", flush=True)

            # Stop idle, switch eyes to attentive amber
            stop_idle()
            if led_ser:
                reachy_leds.set_color(led_ser, 255, 150, 0)

            if doa_yaw is not None:
                speaker_yaw = doa_yaw
                turn_toward_speaker(mini, speaker_yaw)

            # Check if they already said something after the wake word
            after_wake = extract_after_wake(text)

            if len(after_wake) > 5:
                # They said the request in the same breath
                request_text = after_wake
                print(f"👤 You: {request_text}", flush=True)
            else:
                # Play acknowledgment sound (quick antenna perk)
                mini.goto_target(antennas=[0.4, -0.4], duration=0.3, method="minjerk")
                mini.goto_target(antennas=ANTENNA_NEUTRAL, duration=0.3, method="minjerk")

                # Start alert animation while listening
                stop_alert = threading.Event()
                alert_thread = threading.Thread(target=animate_loop,
                                                args=(mini, ALERT_KEYFRAMES, stop_alert))
                alert_thread.start()

                # Record the actual request until they stop speaking
                print("🎤 Listening for request...", flush=True)
                request_mono, req_doa = record_until_silence(
                    mini, REQUEST_MAX_SECONDS, SPEECH_THRESHOLD,
                    SILENCE_AFTER_WAKE, REQUEST_MIN_SECONDS
                )

                stop_alert.set()
                alert_thread.join()

                if req_doa is not None:
                    speaker_yaw = req_doa

                # Transcribe
                req_rms = np.sqrt(np.mean(request_mono ** 2))
                if req_rms < SPEECH_THRESHOLD:
                    # They said "Hey Karl" but then nothing — prompt them
                    speak_animated(mini, voice, "Yes? What do you want?", face_yaw=speaker_yaw, led_ser=led_ser)
                    start_idle()
                    continue

                segments, _ = whisper.transcribe(request_mono, language="en")
                request_text = " ".join(seg.text for seg in segments).strip()

                if len(request_text) < 3:
                    speak_animated(mini, voice, "Didn't catch that. Try again.", face_yaw=speaker_yaw, led_ser=led_ser)
                    start_idle()
                    continue

                print(f"👤 You: {request_text}", flush=True)

            # ── RESPOND STATE ──
            conversation_history.append({"role": "user", "content": request_text})
            response = ollama.chat(model=OLLAMA_MODEL, messages=conversation_history)
            reply = response["message"]["content"]
            conversation_history.append({"role": "assistant", "content": reply})

            if len(conversation_history) > 20:
                conversation_history = conversation_history[:1] + conversation_history[-18:]

            print(f"🤖 Karl: {reply}\n", flush=True)
            speak_animated(mini, voice, reply, face_yaw=speaker_yaw, led_ser=led_ser)

            # Resume idle
            start_idle()

    except KeyboardInterrupt:
        print("\n\nStopping...", flush=True)
        stop_idle()
        if led_ser:
            reachy_leds.off(led_ser)
            led_ser.close()
        mini.goto_target(head=create_head_pose(), body_yaw=0, antennas=ANTENNA_NEUTRAL,
                         duration=0.5, method="minjerk")
        print("Goodbye!")


if __name__ == "__main__":
    main()
