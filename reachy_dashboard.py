"""Robot Karl Dashboard — webhook server for status announcements.

Run:
    python reachy_dashboard.py

Endpoints:
    POST /say       — speak a message directly (TTS only, no LLM)
    POST /announce  — pass through LLM for Karl-style delivery, then speak
    GET  /status    — check if robot is online
    GET  /history   — recent announcements

Examples:
    curl -X POST http://localhost:9000/say -H 'Content-Type: application/json' \
         -d '{"message": "PR 42 merged successfully"}'

    curl -X POST http://localhost:9000/announce -H 'Content-Type: application/json' \
         -d '{"event": "CI build failed on main", "context": "3 tests broken in auth module"}'

    curl http://localhost:9000/status
"""

import asyncio
import threading
import time
from collections import deque
from datetime import datetime

import numpy as np
import ollama
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from piper import PiperVoice
from scipy.signal import resample

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose
from robot_karl_prompt import ROBOT_KARL_PROMPT

# --- Config ---
OLLAMA_MODEL = "llama3.2"
PIPER_MODEL = "piper_models/en_GB-northern_english_male-medium.onnx"
PIPER_CONFIG = "piper_models/en_GB-northern_english_male-medium.onnx.json"
ROBOT_SAMPLE_RATE = 16000
PITCH_SHIFT = 0.95
PORT = 9000

ANNOUNCE_PROMPT = ROBOT_KARL_PROMPT + (
    "\nContext: You are announcing workflow status updates to the team. "
    "Restate the key info in your own words — keep it brief and useful."
)

# --- Models ---
class SayRequest(BaseModel):
    message: str

class AnnounceRequest(BaseModel):
    event: str
    context: str = ""

class HistoryEntry(BaseModel):
    timestamp: str
    type: str
    input: str
    spoken: str

# --- Globals ---
app = FastAPI(title="Robot Karl Dashboard", version="1.0")
voice: PiperVoice = None
mini: ReachyMini = None
speak_lock = threading.Lock()
history: deque[HistoryEntry] = deque(maxlen=50)


def tts_synthesize(text: str) -> np.ndarray:
    chunks = list(voice.synthesize(text))
    if not chunks:
        return np.array([], dtype=np.float32)
    samples = np.concatenate([ch.audio_float_array for ch in chunks])
    src_rate = chunks[0].sample_rate
    effective_rate = src_rate * PITCH_SHIFT
    num_out = int(len(samples) * ROBOT_SAMPLE_RATE / effective_rate)
    return resample(samples, num_out).astype(np.float32)


def animate_while_speaking(duration: float):
    keyframes = [
        (0.02, 0.01, 0, 8, 0.15, 0.3, -0.1, 1.0),
        (-0.02, 0.0, 3, -8, -0.15, -0.1, 0.3, 1.0),
        (0.01, 0.02, 0, 5, 0.1, 0.2, -0.2, 0.8),
        (-0.01, -0.01, -3, -5, -0.1, -0.2, 0.2, 0.8),
        (0.0, 0.01, 3, 0, 0.0, 0.15, -0.15, 0.7),
    ]
    start = time.time()
    i = 0
    while time.time() - start < duration:
        y, z, p, yw, by, al, ar, d = keyframes[i % len(keyframes)]
        d = min(d, duration - (time.time() - start))
        if d < 0.1:
            break
        mini.goto_target(
            head=create_head_pose(y=y, z=z, pitch=p, yaw=yw, mm=False, degrees=True),
            antennas=[al, ar], body_yaw=by, duration=d, method="minjerk",
        )
        i += 1
    mini.goto_target(
        head=create_head_pose(), antennas=[0, 0], body_yaw=0,
        duration=0.6, method="minjerk",
    )


def speak_text(text: str):
    """Speak text through the robot with animation. Thread-safe."""
    with speak_lock:
        samples = tts_synthesize(text)
        duration = len(samples) / ROBOT_SAMPLE_RATE

        mini.media.start_playing()
        animator = threading.Thread(target=animate_while_speaking, args=(duration,))
        animator.start()
        mini.media.push_audio_sample(samples.reshape(-1, 1))
        animator.join()
        time.sleep(0.3)
        mini.media.stop_playing()


def add_history(type: str, input_text: str, spoken: str):
    history.append(HistoryEntry(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        type=type,
        input=input_text,
        spoken=spoken,
    ))


@app.get("/status")
def get_status():
    return {
        "robot": "online",
        "model": OLLAMA_MODEL,
        "voice": PIPER_MODEL,
        "history_count": len(history),
    }


@app.post("/say")
async def say(req: SayRequest):
    """Speak a message directly — no LLM processing."""
    text = req.message.strip()
    if not text:
        return {"error": "empty message"}

    await asyncio.to_thread(speak_text, text)
    add_history("say", text, text)
    return {"spoken": text}


@app.post("/announce")
async def announce(req: AnnounceRequest):
    """Pass an event through the LLM for Karl-style delivery, then speak."""
    prompt = f"Event: {req.event}"
    if req.context:
        prompt += f"\nDetails: {req.context}"

    resp = await asyncio.to_thread(
        ollama.chat,
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": ANNOUNCE_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    spoken = resp.message.content

    await asyncio.to_thread(speak_text, spoken)
    add_history("announce", req.event, spoken)
    return {"event": req.event, "spoken": spoken}


@app.get("/history")
def get_history():
    return list(history)


def main():
    global voice, mini

    print("🤖 Loading voice model...")
    voice = PiperVoice.load(PIPER_MODEL, PIPER_CONFIG)

    print("🔌 Connecting to robot...")
    mini = ReachyMini(media_backend="default")

    print(f"🚀 Robot Karl Dashboard running on http://localhost:{PORT}")
    print(f"   POST /say       — speak a message directly")
    print(f"   POST /announce  — LLM-styled announcement")
    print(f"   GET  /status    — check robot status")
    print(f"   GET  /history   — recent announcements")
    print()

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
