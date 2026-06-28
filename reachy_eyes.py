"""
reachy_eyes.py — Python driver for Robot Karl's LED eyes.

Controls RGB LEDs on the XIAO ESP32-C6 via USB serial.
Import this module from other scripts to set eye colors based on robot state.

Usage:
    from reachy_eyes import RobotEyes

    eyes = RobotEyes()  # auto-detects serial port
    eyes.set_both(0, 0, 255)      # blue
    eyes.set_left(255, 0, 0)      # left eye red
    eyes.listening()               # blue pulse
    eyes.thinking()                # purple
    eyes.speaking()                # green
    eyes.idle()                    # dim white
    eyes.off()
    eyes.close()
"""

import serial
import serial.tools.list_ports
import time
import threading


class RobotEyes:
    """Serial interface to the XIAO ESP32-C6 eye LED controller."""

    BAUD = 115200
    TIMEOUT = 1.0

    # Predefined colors for robot states
    COLORS = {
        "idle":      (20, 20, 30),      # dim cool white
        "listening": (0, 80, 255),      # blue
        "thinking":  (150, 0, 255),     # purple
        "speaking":  (0, 200, 50),      # green
        "alert":     (255, 150, 0),     # amber
        "error":     (255, 0, 0),       # red
        "happy":     (0, 255, 100),     # bright green
        "annoyed":   (255, 50, 0),      # orange-red
    }

    def __init__(self, port=None):
        """Connect to the eye controller. Auto-detects port if not specified."""
        if port is None:
            port = self._find_port()
        if port is None:
            raise ConnectionError(
                "Could not find XIAO eye controller. "
                "Check USB connection and that firmware is flashed."
            )
        self._ser = serial.Serial(port, self.BAUD, timeout=self.TIMEOUT)
        time.sleep(0.5)  # wait for READY
        self._ser.reset_input_buffer()
        self._lock = threading.Lock()
        self._pulse_stop = None

    def _find_port(self):
        """Find the XIAO serial port (not the Reachy daemon port)."""
        reachy_port = None
        candidates = []
        for p in serial.tools.list_ports.comports():
            # Skip the Reachy Mini's own port
            if "5B7B" in (p.serial_number or ""):
                reachy_port = p.device
                continue
            if "usbmodem" in p.device or "usbserial" in p.device or "wchusbserial" in p.device:
                candidates.append(p.device)
        # Try each candidate
        for dev in candidates:
            try:
                s = serial.Serial(dev, self.BAUD, timeout=1)
                time.sleep(0.3)
                s.reset_input_buffer()
                s.write(b"PING\n")
                resp = s.readline().decode().strip()
                if resp == "PONG":
                    s.close()
                    return dev
                s.close()
            except Exception:
                continue
        return None

    def _send(self, cmd):
        """Send a command and wait for response."""
        with self._lock:
            self._ser.write(f"{cmd}\n".encode())
            resp = self._ser.readline().decode().strip()
            return resp

    def set_left(self, r, g, b):
        """Set left eye color (0-255 per channel)."""
        return self._send(f"L0:{r},{g},{b}")

    def set_right(self, r, g, b):
        """Set right eye color (0-255 per channel)."""
        return self._send(f"L1:{r},{g},{b}")

    def set_both(self, r, g, b):
        """Set both eyes to the same color."""
        return self._send(f"LA:{r},{g},{b}")

    def off(self):
        """Turn off all LEDs."""
        self.stop_pulse()
        return self._send("OFF")

    def ping(self):
        """Check connection."""
        return self._send("PING") == "PONG"

    # ── State presets ──

    def idle(self):
        """Dim cool white — robot is idle."""
        self.stop_pulse()
        r, g, b = self.COLORS["idle"]
        self.set_both(r, g, b)

    def listening(self):
        """Blue — robot is listening."""
        self.stop_pulse()
        r, g, b = self.COLORS["listening"]
        self.set_both(r, g, b)

    def thinking(self):
        """Purple — robot is processing/thinking."""
        self.stop_pulse()
        r, g, b = self.COLORS["thinking"]
        self.set_both(r, g, b)

    def speaking(self):
        """Green — robot is speaking."""
        self.stop_pulse()
        r, g, b = self.COLORS["speaking"]
        self.set_both(r, g, b)

    def alert(self):
        """Amber — wake word detected."""
        self.stop_pulse()
        r, g, b = self.COLORS["alert"]
        self.set_both(r, g, b)

    def error(self):
        """Red — something went wrong."""
        self.stop_pulse()
        r, g, b = self.COLORS["error"]
        self.set_both(r, g, b)

    # ── Pulse animation (runs in background thread) ──

    def start_pulse(self, r, g, b, period=2.0):
        """Pulse (breathe) a color. Runs until stop_pulse() is called."""
        self.stop_pulse()
        self._pulse_stop = threading.Event()
        t = threading.Thread(target=self._pulse_loop,
                             args=(r, g, b, period, self._pulse_stop),
                             daemon=True)
        t.start()

    def stop_pulse(self):
        """Stop any running pulse animation."""
        if self._pulse_stop is not None:
            self._pulse_stop.set()
            self._pulse_stop = None

    def _pulse_loop(self, r, g, b, period, stop_event):
        """Fade in/out loop."""
        import math
        step = 0.05
        t = 0
        while not stop_event.is_set():
            brightness = (math.sin(t * 2 * math.pi / period) + 1) / 2  # 0..1
            br = max(0.1, brightness)  # never fully off
            self.set_both(int(r * br), int(g * br), int(b * br))
            time.sleep(step)
            t += step

    def close(self):
        """Close the serial connection."""
        self.stop_pulse()
        self.off()
        self._ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == "__main__":
    # Quick test
    print("Connecting to eyes...")
    eyes = RobotEyes()
    print(f"Connected! Ping: {eyes.ping()}")

    print("Red...")
    eyes.set_both(255, 0, 0)
    time.sleep(1)
    print("Green...")
    eyes.set_both(0, 255, 0)
    time.sleep(1)
    print("Blue...")
    eyes.set_both(0, 0, 255)
    time.sleep(1)
    print("Pulse blue...")
    eyes.start_pulse(0, 80, 255, period=2.0)
    time.sleep(5)
    print("Off.")
    eyes.close()
