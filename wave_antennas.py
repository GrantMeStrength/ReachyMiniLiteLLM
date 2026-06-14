"""Wave the Reachy Mini's antennas in a friendly greeting."""

from reachy_mini import ReachyMini
import time

with ReachyMini() as mini:
    print("👋 Waving antennas!")

    for _ in range(3):
        mini.goto_target(antennas=[0.6, -0.6], duration=0.3)
        mini.goto_target(antennas=[-0.6, 0.6], duration=0.3)

    # Return to neutral
    mini.goto_target(antennas=[0, 0], duration=0.3)
    print("✅ Done!")
