#!/usr/bin/env python3
"""
fix_camera.py — Fix dark camera image on Reachy Mini Lite (macOS)

Problem:
    On macOS, the Reachy Mini camera often produces very dark images due to a
    GStreamer auto-exposure bug (https://github.com/pollen-robotics/reachy_mini/issues/963).
    The root cause is the "Powerline Frequency" UVC control defaulting to 50Hz/60Hz mode.

Solution:
    Disable the powerline frequency filter via a UVC SET_CUR request using uvc-util.
    The setting persists in the camera firmware — you only need to run this once after
    each power cycle.

Prerequisites:
    Build uvc-util from source:
        git clone https://github.com/jtfrey/uvc-util.git
        cd uvc-util
        xcodebuild -scheme uvc-util -configuration Release -derivedDataPath build
        cp build/Build/Products/Release/uvc-util /usr/local/bin/  # or anywhere in PATH

Usage:
    python fix_camera.py          # Auto-detect and fix
    python fix_camera.py --check  # Just check current value
    python fix_camera.py --reset  # Restore default (50Hz)

See also: https://github.com/pollen-robotics/reachy_mini/issues/963
"""

import subprocess
import shutil
import sys
import argparse


def find_uvc_util():
    """Find uvc-util binary."""
    # Check PATH first
    path = shutil.which("uvc-util")
    if path:
        return path
    # Common install locations
    for candidate in [
        "/usr/local/bin/uvc-util",
        "./tools/uvc-util",
        "../tools/uvc-util",
    ]:
        if shutil.which(candidate) or __import__("os").path.isfile(candidate):
            return candidate
    return None


def get_power_line_frequency(uvc_util):
    """Get current power-line-frequency value."""
    result = subprocess.run(
        [uvc_util, "-I", "0", "-g", "power-line-frequency"],
        capture_output=True, text=True, timeout=5
    )
    if result.returncode != 0:
        print(f"Error reading control: {result.stderr.strip()}")
        return None
    # Parse "power-line-frequency = 0"
    parts = result.stdout.strip().split("=")
    return int(parts[-1].strip()) if len(parts) == 2 else None


def set_power_line_frequency(uvc_util, value):
    """Set power-line-frequency value (0=Off, 1=50Hz, 2=60Hz)."""
    result = subprocess.run(
        [uvc_util, "-I", "0", "-s", f"power-line-frequency={value}"],
        capture_output=True, text=True, timeout=5
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Fix Reachy Mini camera brightness on macOS")
    parser.add_argument("--check", action="store_true", help="Just show current value")
    parser.add_argument("--reset", action="store_true", help="Restore default (50Hz)")
    args = parser.parse_args()

    uvc_util = find_uvc_util()
    if not uvc_util:
        print("❌ uvc-util not found!")
        print()
        print("Build it from source:")
        print("  git clone https://github.com/jtfrey/uvc-util.git")
        print("  cd uvc-util")
        print("  xcodebuild -scheme uvc-util -configuration Release -derivedDataPath build")
        print("  sudo cp build/Build/Products/Release/uvc-util /usr/local/bin/")
        sys.exit(1)

    print(f"Using: {uvc_util}")

    current = get_power_line_frequency(uvc_util)
    if current is None:
        print("❌ Could not read camera control. Is the robot connected?")
        sys.exit(1)

    value_names = {0: "Off (bright ✅)", 1: "50 Hz (may be dark)", 2: "60 Hz (may be dark)"}
    print(f"Current power-line-frequency: {current} — {value_names.get(current, 'unknown')}")

    if args.check:
        return

    if args.reset:
        target = 1
        print(f"Resetting to default (50Hz)...")
    else:
        target = 0
        if current == 0:
            print("✅ Already set to Off — camera should be bright!")
            return
        print(f"Setting to 0 (Off) to fix dark image...")

    if set_power_line_frequency(uvc_util, target):
        print(f"✅ Done! power-line-frequency set to {target}")
        if target == 0:
            print("   Camera should now produce bright images.")
            print("   (Setting persists in firmware until next power cycle)")
    else:
        print("❌ Failed to set value")
        sys.exit(1)


if __name__ == "__main__":
    main()
