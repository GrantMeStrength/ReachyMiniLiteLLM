---
name: reachy
description: "Control Robot Karl (a Reachy Mini Lite robot): move its head, blink its RGB eyes, speak out loud, and SEE through its camera."
homepage: https://github.com/GrantMeStrength/ReachyMiniLiteLLM
metadata:
  {
    "openclaw":
      {
        "emoji": "🤖",
        "requires": { "bins": ["karlctl"] },
      },
  }
---

# Robot Karl (Reachy Mini Lite)

Use the `karlctl` command to control a physical desktop robot named **Karl**.
Karl can move his head and antennas, light up his two RGB eyes, speak through
his speaker, and capture what he sees through his camera.

Every command prints one result line: `OK {json}` on success, or
`ERROR <message>` on failure. Commands are fast and self-contained.

## When to Use

Use when the user asks to:

- Make the robot / Karl **move, look around, nod, or shake** its head.
- Make Karl **say / speak / talk** something out loud.
- **Blink** the eyes or set the **eye color**.
- **See / look / check the camera** — "what can you see?", "what's in front of
  the robot?", "look at me and describe what you see".
- Run a quick **demo**.

## Prerequisite

The Reachy Mini daemon must be running. Check first with `karlctl status`
(reports `daemon`, `eyes`, `camera` booleans). If `daemon` is false, start it:

```bash
/Users/john/venv/bin/reachy-mini-daemon >/tmp/daemon.log 2>&1 &
```

## Commands

```bash
karlctl status                 # {"daemon":true,"eyes":true,"camera":true}

# Motion
karlctl wake                   # wake-up emote
karlctl look right             # left | right | up | down | center
karlctl nod 2                  # nod "yes" N times
karlctl shake 2                # shake "no" N times

# Speech (British voice "Daniel" by default; plays on Karl's speaker)
karlctl speak "Hello, I am Karl"
karlctl speak --no-move "Text without head movement"
karlctl speak -v Reed "Use a different macOS voice"

# Eyes (two RGB LEDs, values 0-255)
karlctl eyes 0,120,255         # both eyes blue
karlctl eyes 255,0,0 --side left
karlctl eyes off
karlctl blink random 8         # blink 8 times, random colors
karlctl blink 0,255,0 3        # blink green 3 times

# Vision — capture what Karl sees
karlctl see --out /tmp/karl_view.jpg
```

## Seeing through Karl's camera

To answer "what do you see?" / "look around":

1. Run `karlctl see --out /tmp/karl_view.jpg`.
2. The result line gives the saved JPEG `path` (1920x1080) plus a
   `brightness` value.
3. **Open / view that JPEG file** and describe its contents to the user.

Optionally have Karl `look` in a direction first, then `see`, to inspect a
different part of the room.

## Notes

- One action at a time; commands return as soon as the action completes.
- Speech uses fully-offline macOS text-to-speech, routed through the daemon's
  speaker (no audio-device conflicts).
- If `eyes` or `camera` report false in `status`, that subsystem is
  unplugged — the other commands still work.
- Underlying code lives in the repo `ReachyMiniLiteLLM` (`karlctl.py`).
