"""Wave the Reachy Mini's antennas in a friendly greeting."""

from reachy_mini import ReachyMini
import time
from karl_config import ANTENNA_REST, LOCAL_CONNECTION_MODE


def main():
    with ReachyMini(connection_mode=LOCAL_CONNECTION_MODE) as mini:
        print("👋 Waving antennas!")

        for _ in range(3):
            mini.goto_target(antennas=[0.6, -0.6], duration=0.3)
            mini.goto_target(antennas=[-0.6, 0.6], duration=0.3)

        mini.goto_target(antennas=ANTENNA_REST, duration=0.3)
        print("✅ Done!")


if __name__ == "__main__":
    main()
