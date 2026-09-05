"""Compatibility speech demo using Karl's offline macOS voice."""

from reachy_mini import ReachyMini
import time
from karl_config import LOCAL_CONNECTION_MODE
from reachy_say import text_to_samples

SAMPLE_RATE = 16000


def main():
    with ReachyMini(
        media_backend="default",
        connection_mode=LOCAL_CONNECTION_MODE,
    ) as mini:
        text = "Hello! I am Reachy Mini! Nice to meet you!"
        print(f'🗣️ Speaking: "{text}"')

        samples = text_to_samples(text, "Daniel")
        duration = len(samples) / SAMPLE_RATE
        print(f"   Audio: {duration:.1f}s")

        mini.media.start_playing()
        mini.media.push_audio_sample(samples.reshape(-1, 1))
        time.sleep(duration + 0.5)
        mini.media.stop_playing()

        print("✅ Done!")


if __name__ == "__main__":
    main()
