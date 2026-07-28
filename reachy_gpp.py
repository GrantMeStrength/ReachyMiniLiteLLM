"""Run Karl's Genuine People Personality mode.

GPP follows faces and blinks while someone is present. After a sustained
absence it lowers Karl's head and turns the eyes off, then wakes when a face
returns. From 10 PM until 7 AM it sleeps without checking for people. Rare
local remarks add personality without becoming distracting.
"""

from __future__ import annotations

import datetime
import json
import random
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import reachy_leds


DAEMON_URL = "http://127.0.0.1:8000"
KARLCTL = Path(__file__).with_name("karlctl")
ANTENNA_REST = [0.15, -0.25]
EYE_COLOR = (40, 35, 30)
POLL_INTERVAL = 1.0
FACE_CONFIRMATIONS = 2
NAP_AFTER_SECONDS = 45
NAP_PEEK_INTERVAL = 15
NAP_PEEK_SECONDS = 4
COMMENT_AFTER_SECONDS = 90
COMMENT_CHECK_INTERVAL = 60
COMMENT_CHANCE = 0.025
COMMENT_COOLDOWN_SECONDS = 3 * 60 * 60
BEDTIME_HOUR = 22
WAKE_HOUR = 7


class EyeBlinker:
    """Own one eye-controller connection and blink only while Karl is awake."""

    def __init__(self) -> None:
        self.serial = None
        self.stop_event: threading.Event | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread is not None:
            return
        if self.serial is None:
            self.serial = reachy_leds.connect()
        if self.serial is None:
            return
        self.stop_event = threading.Event()
        self.thread = threading.Thread(
            target=reachy_leds.idle_blink,
            args=(self.serial, self.stop_event),
            kwargs={"color": EYE_COLOR},
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
        self.stop_event = None
        self.thread = None
        if self.serial is not None:
            reachy_leds.off(self.serial)

    def close(self) -> None:
        self.stop()
        if self.serial is not None:
            self.serial.close()
            self.serial = None


def daemon_request(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{DAEMON_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = response.read()
    return json.loads(payload) if payload else {}


def enable_tracking() -> None:
    daemon_request("/api/media/tracking/enable", {"weight": 0.35})


def disable_tracking() -> None:
    daemon_request("/api/media/tracking/disable", {})


def face_detected() -> bool:
    response = daemon_request("/api/media/tracking/face")
    return bool(response.get("face_target", {}).get("detected"))


def is_overnight(now: datetime.datetime | None = None) -> bool:
    local_now = now or datetime.datetime.now().astimezone()
    return local_now.hour >= BEDTIME_HOUR or local_now.hour < WAKE_HOUR


def move_to_nap() -> None:
    disable_tracking()
    daemon_request("/api/motors/set_mode/enabled", {})
    daemon_request(
        "/api/move/goto",
        {
            "head_pose": {
                "x": 0,
                "y": 0,
                "z": 0,
                "roll": 0,
                "pitch": 0.44,
                "yaw": 0,
            },
            "antennas": ANTENNA_REST,
            "body_yaw": 0,
            "duration": 1.2,
            "interpolation": "minjerk",
        },
    )
    time.sleep(1.4)


def move_to_watch() -> None:
    daemon_request("/api/motors/set_mode/enabled", {})
    daemon_request(
        "/api/move/goto",
        {
            "head_pose": {
                "x": 0,
                "y": 0,
                "z": 0,
                "roll": 0,
                "pitch": 0,
                "yaw": 0,
            },
            "antennas": ANTENNA_REST,
            "body_yaw": 0,
            "duration": 0.8,
            "interpolation": "minjerk",
        },
    )
    time.sleep(1)


def look_for_company(stopping: threading.Event) -> bool:
    """Briefly raise Karl's head so the camera can see returning people."""
    move_to_watch()
    enable_tracking()
    confirmations = 0
    deadline = time.monotonic() + NAP_PEEK_SECONDS
    while time.monotonic() < deadline and not stopping.wait(POLL_INTERVAL):
        confirmations = confirmations + 1 if face_detected() else 0
        if confirmations >= FACE_CONFIRMATIONS:
            return True
    move_to_nap()
    return False


def run_karlctl(*arguments: str) -> None:
    subprocess.run(
        [str(KARLCTL), *arguments],
        cwd=KARLCTL.parent,
        check=True,
        timeout=45,
    )


def wake() -> None:
    run_karlctl("wake")
    enable_tracking()


def local_remark() -> str:
    now = datetime.datetime.now().astimezone()
    if random.choice((True, False)):
        current_time = now.strftime("%-I:%M %p")
        return f"It is {current_time}. Time is an illusion, but apparently we are keeping it anyway."
    return random.choice(
        (
            "Whatever the weather is doing outside, I disapprove on principle.",
            "I hope the weather is being reasonable. Someone ought to be.",
            "The weather remains outside, which is probably for the best.",
        )
    )


def speak_remark() -> None:
    disable_tracking()
    try:
        run_karlctl("speak", local_remark())
    finally:
        enable_tracking()


def main() -> None:
    stopping = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stopping.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    eyes = EyeBlinker()
    overnight = is_overnight()
    awake = not overnight
    face_confirmations = 0
    last_seen = time.monotonic()
    person_present_since: float | None = None
    last_comment = time.monotonic() - COMMENT_COOLDOWN_SECONDS
    next_comment_check = last_comment + COMMENT_CHECK_INTERVAL
    next_nap_peek = last_comment

    if overnight:
        print("GPP active during overnight hours; sleeping until 7:00 AM.", flush=True)
        move_to_nap()
    else:
        print("GPP active: following faces, blinking, and watching for company.", flush=True)
        enable_tracking()
        eyes.start()

    try:
        while not stopping.wait(POLL_INTERVAL):
            now = time.monotonic()
            should_be_overnight = is_overnight()

            if should_be_overnight:
                if not overnight:
                    print("GPP bedtime reached; sleeping until 7:00 AM.", flush=True)
                    eyes.stop()
                    move_to_nap()
                    overnight = True
                    awake = False
                    person_present_since = None
                continue

            if overnight:
                print("GPP morning reached; waking for the day.", flush=True)
                wake()
                eyes.start()
                overnight = False
                awake = True
                last_seen = time.monotonic()
                person_present_since = None
                next_comment_check = last_seen + COMMENT_CHECK_INTERVAL
                continue

            if not awake:
                if now < next_nap_peek:
                    continue
                next_nap_peek = now + NAP_PEEK_INTERVAL
                print("GPP checking whether anyone has returned.", flush=True)
                try:
                    if look_for_company(stopping):
                        print("GPP detected company; waking.", flush=True)
                        wake()
                        eyes.start()
                        awake = True
                        last_seen = time.monotonic()
                        person_present_since = last_seen
                        next_comment_check = last_seen + COMMENT_CHECK_INTERVAL
                except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
                    print(f"GPP return check failed: {error}", flush=True)
                    try:
                        move_to_nap()
                    except (OSError, urllib.error.URLError):
                        pass
                continue

            try:
                seen = face_detected()
            except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
                print(f"GPP face check failed: {error}", flush=True)
                continue

            face_confirmations = face_confirmations + 1 if seen else 0

            if seen:
                last_seen = now
                if person_present_since is None:
                    person_present_since = now
            else:
                person_present_since = None

            if awake and now - last_seen >= NAP_AFTER_SECONDS:
                print("GPP room is empty; napping.", flush=True)
                eyes.stop()
                move_to_nap()
                awake = False
                next_nap_peek = time.monotonic() + NAP_PEEK_INTERVAL
                continue

            ready_to_comment = (
                awake
                and person_present_since is not None
                and now - person_present_since >= COMMENT_AFTER_SECONDS
                and now - last_comment >= COMMENT_COOLDOWN_SECONDS
                and now >= next_comment_check
            )
            if ready_to_comment:
                next_comment_check = now + COMMENT_CHECK_INTERVAL
                if random.random() < COMMENT_CHANCE:
                    print("GPP making a rare observation.", flush=True)
                    speak_remark()
                    last_comment = time.monotonic()

    finally:
        eyes.close()
        try:
            disable_tracking()
        except (OSError, urllib.error.URLError):
            pass
        print("GPP stopped.", flush=True)


if __name__ == "__main__":
    main()
