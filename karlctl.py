#!/usr/bin/env python3
"""karlctl — a single control CLI for Robot Karl (Reachy Mini Lite).

Designed to be driven by an external agent (e.g. OpenClaw) or a human. Every
subcommand is self-contained: it connects, does one thing, prints a short
machine-readable result line, and exits.

Subsystems (all verified working on this machine):
  * Motion  — reachy_mini SDK, connected with media_backend="no_media" so it
              never fights the daemon for the audio/camera device.
  * Speech  — macOS `say` -> wav, played SERVER-SIDE through the daemon's
              HTTP endpoint POST /api/media/play_sound (no device contention).
  * Eyes    — ESP32 RGB LEDs over serial (reachy_leds auto-detects the port).
  * Vision  — the Reachy Mini Camera is a UVC device; grab a still with OpenCV.

The daemon (reachy-mini-daemon) MUST be running first.

Examples:
  karlctl status
  karlctl wake
  karlctl look right
  karlctl body left
  karlctl antennas up
  karlctl speak "Hello, I am Karl"
  karlctl blink random 8
  karlctl eyes 0,120,255
  karlctl see --out /tmp/karl_view.jpg
  karlctl demo
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.parse
import wave
import signal
import threading

import math

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

DAEMON = os.environ.get("REACHY_DAEMON", "http://127.0.0.1:8000")
CAM_INDEX = int(os.environ.get("REACHY_CAM_INDEX", "0"))
VOICE = os.environ.get("KARL_VOICE", "Daniel")  # en_GB male, Karl's accent


# ----------------------------------------------------------------------------- utils
def _ok(**kw):
    """Print a single machine-readable result line and return 0."""
    print("OK " + json.dumps(kw))
    return 0


def _err(msg):
    print("ERROR " + msg, file=sys.stderr)
    return 1


def _daemon_post(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {} if data is None else {"Content-Type": "application/json"}
    req = urllib.request.Request(
        DAEMON + path, data=data, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        return r.read().decode()


def _daemon_get(path):
    with urllib.request.urlopen(DAEMON + path, timeout=6) as r:
        return r.read().decode()


# ----------------------------------------------------------------------------- motion
def _enable_motors():
    _daemon_post("/api/motors/set_mode/enabled")


def _goto(head=None, antennas=None, body_yaw=None, duration=0.6):
    payload = {
        "duration": duration,
        "interpolation": "minjerk",
    }
    if head is not None:
        payload["head_pose"] = {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "roll": math.radians(head.get("roll", 0.0)),
            "pitch": math.radians(head.get("pitch", 0.0)),
            "yaw": math.radians(head.get("yaw", 0.0)),
        }
    payload["antennas"] = antennas if antennas is not None else ANTENNA_NEUTRAL
    if body_yaw is not None:
        payload["body_yaw"] = body_yaw
    _enable_motors()
    _daemon_post("/api/move/goto", payload)
    time.sleep(duration + 0.1)


LOOKS = {
    "left": dict(yaw=25), "right": dict(yaw=-25),
    "up": dict(pitch=-20), "down": dict(pitch=20),
    "tilt-left": dict(roll=18), "tilt-right": dict(roll=-18),
    "center": dict(), "front": dict(),
}

BODY_YAWS = {
    "left": math.radians(35),
    "right": math.radians(-35),
    "center": 0.0,
}

ANTENNA_POSITIONS = {
    "up": [0.6, -0.6],
    "down": [-0.6, 0.6],
    "neutral": [0.08, -0.15],
}
ANTENNA_NEUTRAL = ANTENNA_POSITIONS["neutral"]

EMOTION_DATASET = "pollen-robotics/reachy-mini-emotions-library"


# ----------------------------------------------------------------------------- eyes
def _eyes_connect():
    import reachy_leds
    return reachy_leds.connect()


# ----------------------------------------------------------------------------- speech
def _synthesize(text, voice):
    """macOS say -> 44.1kHz mono PCM16 wav. Returns (path, duration_s)."""
    tmp = tempfile.mkdtemp(prefix="karl_")
    aiff = os.path.join(tmp, "s.aiff")
    wav = os.path.join(tmp, "s.wav")
    subprocess.run(["say", "-v", voice, "-o", aiff, text], check=True)
    subprocess.run(
        ["afconvert", "-f", "WAVE", "-d", "LEI16@44100", "-c", "1", aiff, wav],
        check=True, capture_output=True,
    )
    with wave.open(wav) as w:
        dur = w.getnframes() / float(w.getframerate())
    return wav, dur


# ----------------------------------------------------------------------------- commands
def cmd_status(args):
    out = {"daemon": False, "eyes": False, "camera": False}
    try:
        _daemon_get("/api/media/status")
        out["daemon"] = True
    except Exception:
        pass
    try:
        import reachy_leds
        ser = reachy_leds.connect()
        out["eyes"] = reachy_leds.ping(ser)
        if ser:
            ser.close()
    except Exception:
        pass
    try:
        specs = json.loads(_daemon_get("/api/camera/specs"))
        out["camera"] = bool(specs.get("name"))
    except Exception:
        pass
    return _ok(**out)


def cmd_wake(args):
    _daemon_post("/api/move/play/wake_up")
    return _ok(action="wake")


def cmd_look(args):
    direction = args.direction.lower()
    if direction not in LOOKS:
        return _err(f"unknown direction '{direction}' (choose {list(LOOKS)})")
    _goto(head=LOOKS[direction], duration=args.duration)
    return _ok(action="look", direction=direction)


def cmd_body(args):
    direction = args.direction.lower()
    _goto(body_yaw=BODY_YAWS[direction], duration=args.duration)
    return _ok(action="body", direction=direction)


def cmd_antennas(args):
    position = args.position.lower()
    _goto(antennas=ANTENNA_POSITIONS[position], duration=args.duration)
    return _ok(action="antennas", position=position)


def cmd_track(args):
    if args.state == "on":
        _daemon_post("/api/media/tracking/enable", {"weight": args.weight})
    else:
        _daemon_post("/api/media/tracking/disable")
    return _ok(action="track", state=args.state)


def cmd_emotion(args):
    dataset = urllib.parse.quote(EMOTION_DATASET, safe="")
    move = urllib.parse.quote(args.name, safe="")
    _daemon_post(f"/api/move/play/recorded-move-dataset/{dataset}/{move}")
    return _ok(action="emotion", name=args.name)


def cmd_nod(args):
    for _ in range(args.times):
        _goto(head={"pitch": 15}, duration=0.3)
        _goto(head={"pitch": -5}, duration=0.3)
    _goto(head={}, duration=0.3)
    return _ok(action="nod", times=args.times)


def cmd_shake(args):
    for _ in range(args.times):
        _goto(head={"yaw": 20}, duration=0.25)
        _goto(head={"yaw": -20}, duration=0.25)
    _goto(head={}, duration=0.25)
    return _ok(action="shake", times=args.times)


def cmd_speak(args):
    text = " ".join(args.text)
    wav, dur = _synthesize(text, args.voice)
    _daemon_post("/api/media/play_sound", {"file": wav})
    if args.move:
        t0 = time.time()
        i = 0
        while time.time() - t0 < dur:
            _goto(
                head={
                    "pitch": 7 if i % 2 == 0 else -3,
                    "yaw": 4 if i % 2 == 0 else -4,
                },
                duration=0.35,
            )
            i += 1
        _goto(head={}, duration=0.4)
    else:
        time.sleep(dur + 0.3)
    return _ok(action="speak", text=text, seconds=round(dur, 1), voice=args.voice)


def _parse_rgb(s):
    parts = [int(x) for x in s.split(",")]
    if len(parts) != 3:
        raise ValueError("color must be r,g,b")
    return [max(0, min(255, v)) for v in parts]


def cmd_eyes(args):
    import reachy_leds
    ser = reachy_leds.connect()
    if ser is None:
        return _err("eyes not detected")
    try:
        if args.color.lower() == "off":
            reachy_leds.off(ser)
            return _ok(action="eyes", state="off")
        r, g, b = _parse_rgb(args.color)
        if args.side == "left":
            reachy_leds.set_left(ser, r, g, b)
        elif args.side == "right":
            reachy_leds.set_right(ser, r, g, b)
        else:
            reachy_leds.set_color(ser, r, g, b)
        return _ok(action="eyes", color=[r, g, b], side=args.side)
    finally:
        ser.close()


def cmd_blink(args):
    import random
    import reachy_leds
    ser = reachy_leds.connect()
    if ser is None:
        return _err("eyes not detected")
    try:
        for _ in range(args.times):
            if args.color == "random":
                c0 = [random.randint(0, 255) for _ in range(3)]
                c1 = [random.randint(0, 255) for _ in range(3)]
            else:
                c0 = c1 = _parse_rgb(args.color)
            reachy_leds.set_left(ser, *c0)
            reachy_leds.set_right(ser, *c1)
            time.sleep(0.22)
            reachy_leds.off(ser)
            time.sleep(0.18)
        reachy_leds.off(ser)
        return _ok(action="blink", times=args.times, color=args.color)
    finally:
        ser.close()


def cmd_eyes_idle(args):
    import reachy_leds
    ser = reachy_leds.connect()
    if ser is None:
        return _err("eyes not detected")
    color = _parse_rgb(args.color)
    stop = threading.Event()

    def request_stop(_signum, _frame):
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    try:
        reachy_leds.idle_blink(
            ser,
            stop,
            color=color,
            min_interval=args.min_interval,
            max_interval=args.max_interval,
        )
        return _ok(action="eyes-idle", state="stopped")
    finally:
        reachy_leds.off(ser)
        ser.close()


def cmd_see(args):
    from reachy_mini import ReachyMini

    out = args.out or os.path.join(tempfile.gettempdir(), "karl_view.jpg")
    with ReachyMini(
        media_backend="default", connection_mode="localhost_only"
    ) as robot:
        jpeg = robot.media.get_frame_jpeg()
    if not jpeg:
        return _err("no frame captured")
    with open(out, "wb") as image_file:
        image_file.write(jpeg)
    return _ok(action="see", path=out, bytes=len(jpeg))


def cmd_demo(args):
    cmd_wake(args)
    for d in ("right", "left", "center"):
        _goto(head=LOOKS[d], duration=0.6)
    class A: pass
    b = A(); b.color = "random"; b.times = 4
    cmd_blink(b)
    s = A(); s.text = ["Hello! I am Robot Karl."]; s.voice = VOICE; s.move = True
    cmd_speak(s)
    return _ok(action="demo")


def build_parser():
    p = argparse.ArgumentParser(prog="karlctl", description="Control Robot Karl (Reachy Mini Lite).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Report daemon/eyes/camera availability.").set_defaults(func=cmd_status)
    sub.add_parser("wake", help="Play the wake-up motion emote.").set_defaults(func=cmd_wake)

    pl = sub.add_parser("look", help="Turn the head to look in a direction.")
    pl.add_argument(
        "direction",
        choices=list(LOOKS),
        help="left|right|up|down|tilt-left|tilt-right|center",
    )
    pl.add_argument("--duration", type=float, default=0.6)
    pl.set_defaults(func=cmd_look)

    pbody = sub.add_parser("body", help="Rotate Karl's body.")
    pbody.add_argument("direction", choices=list(BODY_YAWS))
    pbody.add_argument("--duration", type=float, default=0.7)
    pbody.set_defaults(func=cmd_body)

    pantennas = sub.add_parser("antennas", help="Position both antennas.")
    pantennas.add_argument("position", choices=list(ANTENNA_POSITIONS))
    pantennas.add_argument("--duration", type=float, default=0.4)
    pantennas.set_defaults(func=cmd_antennas)

    ptracking = sub.add_parser("track", help="Enable or disable face tracking.")
    ptracking.add_argument("state", choices=["on", "off"])
    ptracking.add_argument("--weight", type=float, default=0.35)
    ptracking.set_defaults(func=cmd_track)

    pemotion = sub.add_parser("emotion", help="Play an official recorded emotion.")
    pemotion.add_argument("name", help="Move name, e.g. cheerful1 or curious1")
    pemotion.set_defaults(func=cmd_emotion)

    pn = sub.add_parser("nod", help="Nod the head (yes).")
    pn.add_argument("times", nargs="?", type=int, default=2)
    pn.set_defaults(func=cmd_nod)

    ps = sub.add_parser("shake", help="Shake the head (no).")
    ps.add_argument("times", nargs="?", type=int, default=2)
    ps.set_defaults(func=cmd_shake)

    psp = sub.add_parser("speak", help="Speak text through the robot's speaker.")
    psp.add_argument("text", nargs="+")
    psp.add_argument("-v", "--voice", default=VOICE)
    psp.add_argument("--no-move", dest="move", action="store_false", help="Do not move the head while speaking.")
    psp.set_defaults(func=cmd_speak, move=True)

    pe = sub.add_parser("eyes", help="Set eye color (r,g,b) or 'off'.")
    pe.add_argument("color", help="'r,g,b' (0-255) or 'off'")
    pe.add_argument("--side", choices=["both", "left", "right"], default="both")
    pe.set_defaults(func=cmd_eyes)

    pb = sub.add_parser("blink", help="Blink the eyes (color or 'random').")
    pb.add_argument("color", nargs="?", default="random", help="'r,g,b' or 'random'")
    pb.add_argument("times", nargs="?", type=int, default=6)
    pb.set_defaults(func=cmd_blink)

    pi = sub.add_parser("eyes-idle", help="Run periodic eye blinking until stopped.")
    pi.add_argument("color", nargs="?", default="40,35,30")
    pi.add_argument("--min-interval", type=float, default=2.0)
    pi.add_argument("--max-interval", type=float, default=5.0)
    pi.set_defaults(func=cmd_eyes_idle)

    pv = sub.add_parser("see", help="Capture a still from Karl's camera to a JPEG.")
    pv.add_argument("--out", default=None, help="Output JPEG path (default: /tmp/karl_view.jpg)")
    pv.set_defaults(func=cmd_see)

    sub.add_parser("demo", help="Run a short wake/look/blink/speak show.").set_defaults(func=cmd_demo)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:
        return _err(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    sys.exit(main())
