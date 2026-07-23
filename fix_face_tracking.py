"""Apply the Reachy Mini 1.9 macOS face-tracking plugin fallback.

Reachy Mini 1.9 expects Gst.ElementFactory.make("v4l2convert") to return
None when the Linux-only plugin is unavailable. The bundled macOS GStreamer
override raises MissingPluginError instead, preventing the intended
videoscale/videoconvert fallback.
"""

from pathlib import Path

import reachy_mini.vision.face_tracking


OLD_IMPORT = "from gi.repository import Gst, GstApp  # noqa: E402, F401\n"
NEW_IMPORT = (
    OLD_IMPORT
    + "from gi.overrides.Gst import MissingPluginError\n"
)
OLD_CONVERTER = (
    '        convert_chain = [Gst.ElementFactory.make("v4l2convert")]\n'
)
NEW_CONVERTER = (
    "        try:\n"
    '            hardware_converter = Gst.ElementFactory.make("v4l2convert")\n'
    "        except MissingPluginError:\n"
    "            hardware_converter = None\n"
    "        convert_chain = [hardware_converter]\n"
)


def main():
    source_path = Path(reachy_mini.vision.face_tracking.__file__)
    source = source_path.read_text()

    if NEW_IMPORT in source and NEW_CONVERTER in source:
        print(f"Face tracking fallback already applied: {source_path}")
        return

    if OLD_IMPORT not in source or OLD_CONVERTER not in source:
        raise RuntimeError(
            f"Unsupported Reachy Mini face tracker source: {source_path}"
        )

    source = source.replace(OLD_IMPORT, NEW_IMPORT, 1)
    source = source.replace(OLD_CONVERTER, NEW_CONVERTER, 1)
    source_path.write_text(source)
    print(f"Applied macOS face tracking fallback: {source_path}")


if __name__ == "__main__":
    main()
