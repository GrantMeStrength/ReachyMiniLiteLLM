"""Reachy Mini LED eye control via ESP32 serial.

ESP32 is connected inside the robot's head via internal USB hub.
Commands: OFF, L0:r,g,b, L1:r,g,b  (values 0-255)
"""

import serial
import threading
import time
import random

ESP32_PORT = "/dev/cu.usbmodem3121301"
ESP32_BAUD = 115200


def connect(port=ESP32_PORT, baud=ESP32_BAUD):
    """Open serial connection to ESP32. Returns None if unavailable."""
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(0.5)
        # Drain any boot output
        if ser.in_waiting:
            ser.read(ser.in_waiting)
        return ser
    except Exception as e:
        print(f"⚠️  LED ESP32 not available: {e}")
        return None


def ping(ser):
    """Health check. Returns True if ESP32 responds with PONG."""
    if not ser:
        return False
    ser.reset_input_buffer()
    ser.write(b"PING\n")
    time.sleep(0.2)
    if ser.in_waiting:
        resp = ser.readline().decode(errors="replace").strip()
        return resp == "PONG"
    return False


def set_color(ser, r, g, b):
    """Set both LEDs to the same color."""
    if not ser:
        return
    ser.write(f"LA:{r},{g},{b}\n".encode())
    if ser.in_waiting:
        ser.read(ser.in_waiting)


def set_left(ser, r, g, b):
    """Set left LED."""
    if not ser:
        return
    ser.write(f"L0:{r},{g},{b}\n".encode())
    if ser.in_waiting:
        ser.read(ser.in_waiting)


def set_right(ser, r, g, b):
    """Set right LED."""
    if not ser:
        return
    ser.write(f"L1:{r},{g},{b}\n".encode())
    if ser.in_waiting:
        ser.read(ser.in_waiting)


def off(ser):
    """Turn off both LEDs."""
    if not ser:
        return
    ser.write(b"OFF\n")
    if ser.in_waiting:
        ser.read(ser.in_waiting)


def speaking_glow(ser, stop_event):
    """Pulsing cyan/white glow while speaking."""
    if not ser:
        return
    t = 0
    while not stop_event.is_set():
        # Pulse between cyan and white
        pulse = (1 + (t % 2)) / 2  # alternates 0.5 and 1.0
        r = int(80 * pulse)
        g = int(180 + 75 * (1 - pulse))
        b = 255
        set_color(ser, r, g, b)
        t += 1
        stop_event.wait(0.15)
    off(ser)


def idle_blink(ser, stop_event):
    """Occasional soft blink while idle/listening — like slow eye blinks."""
    if not ser:
        return
    while not stop_event.is_set():
        # Eyes dim warm white
        set_color(ser, 40, 35, 30)
        # Wait 2-5 seconds between blinks
        stop_event.wait(random.uniform(2.0, 5.0))
        if stop_event.is_set():
            break
        # Blink: fade out then back in
        for brightness in [20, 5, 0, 0, 5, 20, 40]:
            if stop_event.is_set():
                break
            set_color(ser, brightness, int(brightness * 0.9), int(brightness * 0.75))
            time.sleep(0.06)
    off(ser)


def start_speaking_leds(ser):
    """Start speaking LED effect in background. Returns (thread, stop_event)."""
    stop = threading.Event()
    t = threading.Thread(target=speaking_glow, args=(ser, stop), daemon=True)
    t.start()
    return t, stop


def start_idle_leds(ser):
    """Start idle blink effect in background. Returns (thread, stop_event)."""
    stop = threading.Event()
    t = threading.Thread(target=idle_blink, args=(ser, stop), daemon=True)
    t.start()
    return t, stop
