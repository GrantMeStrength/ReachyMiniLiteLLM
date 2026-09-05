"""Reachy Mini LED eye control via ESP32 serial.

ESP32 is connected inside the robot's head via internal USB hub.
Commands: OFF, L0:r,g,b, L1:r,g,b  (values 0-255)
"""

import os
import fcntl
import serial
import serial.tools.list_ports
import threading
import time
import random

ESP32_PORT = "/dev/cu.usbmodem3121301"  # legacy fixed-port fallback
ESP32_BAUD = 115200
ESPRESSIF_VID = 0x303A
ESP32_USB_JTAG_PID = 0x1001
EYE_LOCK_PATH = "/tmp/karl-eyes.lock"
EYE_HEARTBEAT_PATH = "/tmp/karl-eyes.heartbeat"


class LockedSerial:
    """Proxy a serial connection while retaining its interprocess lock."""

    def __init__(self, connection, lock_file):
        object.__setattr__(self, "_connection", connection)
        object.__setattr__(self, "_lock_file", lock_file)
        object.__setattr__(self, "_closed", False)

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def __setattr__(self, name, value):
        setattr(self._connection, name, value)

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.close()

    def close(self):
        if self._closed:
            return
        object.__setattr__(self, "_closed", True)
        try:
            self._connection.close()
        finally:
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()


def _acquire_eye_lock():
    lock_file = open(EYE_LOCK_PATH, "a+")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except BlockingIOError:
        lock_file.close()
        return None


def is_in_use():
    """Return whether another Karl process currently owns the eye controller."""
    lock_file = _acquire_eye_lock()
    if lock_file is None:
        return True
    fcntl.flock(lock_file, fcntl.LOCK_UN)
    lock_file.close()
    return False


def has_recent_heartbeat(max_age=10.0):
    """Return whether the lock owner recently wrote to the eye controller."""
    try:
        return time.time() - os.path.getmtime(EYE_HEARTBEAT_PATH) <= max_age
    except OSError:
        return False


def _record_heartbeat():
    with open(EYE_HEARTBEAT_PATH, "a"):
        os.utime(EYE_HEARTBEAT_PATH)


def _reset_usb_device(serial_number):
    """Reset the eye controller when macOS leaves its USB serial port hung."""
    try:
        import usb.core
        import usb.util

        for dev in usb.core.find(find_all=True, idVendor=ESPRESSIF_VID,
                                 idProduct=ESP32_USB_JTAG_PID):
            if usb.util.get_string(dev, dev.iSerialNumber) == serial_number:
                dev.reset()
                usb.util.dispose_resources(dev)
                time.sleep(2)
                return True
    except Exception:
        pass
    return False


def _recover_serial(ser):
    """Restart the ESP32 application through its USB serial control lines."""
    ser.dtr = False
    ser.rts = True
    time.sleep(0.1)
    ser.rts = False
    time.sleep(2)
    ser.reset_input_buffer()


def _probe(port, baud, recover=False):
    """Open a port and return the serial handle if it answers PING with PONG."""
    ser = None
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(0.5)
        if ser.in_waiting:
            ser.read(ser.in_waiting)  # drain boot output
        ser.reset_input_buffer()
        ser.write(b"PING\n")
        time.sleep(0.2)
        resp = ser.readline().decode(errors="replace").strip() if ser.in_waiting else ""
        if resp != "PONG" and recover:
            _recover_serial(ser)
            ser.write(b"PING\n")
            time.sleep(0.2)
            resp = ser.readline().decode(errors="replace").strip() if ser.in_waiting else ""
        if resp == "PONG":
            return ser
    except Exception:
        pass
    if ser is not None:
        ser.close()
    return None


def find_port(baud=ESP32_BAUD):
    """Auto-detect the eye ESP32 port by probing for a PONG response.

    Order: $REACHY_EYES_PORT, the legacy fixed port, then any usb serial
    device that is not the Reachy Mini's own port (serial number 5B7B).
    Returns an open serial handle, or None if no eye controller is found.
    """
    lock_file = _acquire_eye_lock()
    if lock_file is None:
        return None

    tried = set()
    candidates = []
    ports = list(serial.tools.list_ports.comports())

    env_port = os.environ.get("REACHY_EYES_PORT")
    if env_port:
        candidates.append((env_port, True))
    candidates.append((ESP32_PORT, True))

    for p in ports:
        if "5B7B" in (p.serial_number or ""):  # skip Reachy Mini's own port
            continue
        if any(tag in p.device for tag in ("usbmodem", "usbserial", "wchusbserial")):
            is_eye_controller = (p.vid, p.pid) == (
                ESPRESSIF_VID,
                ESP32_USB_JTAG_PID,
            )
            candidates.append((p.device, is_eye_controller))

    for dev, can_recover in candidates:
        if dev in tried:
            continue
        tried.add(dev)
        ser = _probe(dev, baud, recover=can_recover)
        if ser:
            return LockedSerial(ser, lock_file)

    eye_devices = [
        p for p in ports
        if (p.vid, p.pid) == (ESPRESSIF_VID, ESP32_USB_JTAG_PID)
    ]
    if eye_devices and _reset_usb_device(eye_devices[0].serial_number):
        for p in serial.tools.list_ports.comports():
            if p.serial_number == eye_devices[0].serial_number:
                ser = _probe(p.device, baud, recover=True)
                if ser:
                    return LockedSerial(ser, lock_file)
    fcntl.flock(lock_file, fcntl.LOCK_UN)
    lock_file.close()
    return None


def connect(port=None, baud=ESP32_BAUD):
    """Open serial connection to the eye ESP32. Returns None if unavailable.

    If `port` is given, connect directly; otherwise auto-detect (see
    find_port). Auto-detection makes startup reliable when the ESP32
    enumerates on a different /dev/cu.* path between reboots.
    """
    if port is not None:
        lock_file = _acquire_eye_lock()
        if lock_file is None:
            return None
        try:
            ser = serial.Serial(port, baud, timeout=1)
            time.sleep(0.5)
            if ser.in_waiting:
                ser.read(ser.in_waiting)
            return LockedSerial(ser, lock_file)
        except Exception as e:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
            print(f"⚠️  LED ESP32 not available on {port}: {e}")
            return None

    ser = find_port(baud)
    if ser is None and not is_in_use():
        print("⚠️  LED eyes not detected — continuing without them.")
    return ser


def ping(ser):
    """Health check. Returns True if ESP32 responds with PONG."""
    if not ser:
        return False
    ser.reset_input_buffer()
    ser.write(b"PING\n")
    time.sleep(0.2)
    if ser.in_waiting:
        resp = ser.readline().decode(errors="replace").strip()
        if resp == "PONG":
            _record_heartbeat()
            return True
    return False


def set_color(ser, r, g, b):
    """Set both LEDs to the same color."""
    if not ser:
        return
    ser.write(f"LA:{r},{g},{b}\n".encode())
    _record_heartbeat()
    if ser.in_waiting:
        ser.read(ser.in_waiting)


def set_left(ser, r, g, b):
    """Set left LED."""
    if not ser:
        return
    ser.write(f"L0:{r},{g},{b}\n".encode())
    _record_heartbeat()
    if ser.in_waiting:
        ser.read(ser.in_waiting)


def set_right(ser, r, g, b):
    """Set right LED."""
    if not ser:
        return
    ser.write(f"L1:{r},{g},{b}\n".encode())
    _record_heartbeat()
    if ser.in_waiting:
        ser.read(ser.in_waiting)


def off(ser):
    """Turn off both LEDs."""
    if not ser:
        return
    ser.write(b"OFF\n")
    _record_heartbeat()
    if ser.in_waiting:
        ser.read(ser.in_waiting)


def reset(ser, wait_ready=3.0):
    """Soft-reboot the ESP32 (firmware RESET command) and wait for READY.

    Returns True if the board re-emitted 'READY' within wait_ready seconds.
    """
    if not ser:
        return False
    ser.reset_input_buffer()
    ser.write(b"RESET\n")
    deadline = time.time() + wait_ready
    while time.time() < deadline:
        line = ser.readline().decode(errors="replace").strip()
        if line == "READY":
            return True
    return False


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


def idle_blink(ser, stop_event, color=(40, 35, 30),
               min_interval=2.0, max_interval=5.0):
    """Occasional soft blink while idle/listening — like slow eye blinks."""
    if not ser:
        return
    r, g, b = color
    while not stop_event.is_set():
        set_color(ser, r, g, b)
        stop_event.wait(random.uniform(min_interval, max_interval))
        if stop_event.is_set():
            break
        for scale in [0.5, 0.12, 0, 0, 0.12, 0.5, 1]:
            if stop_event.is_set():
                break
            set_color(ser, int(r * scale), int(g * scale), int(b * scale))
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
