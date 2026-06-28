#!/usr/bin/env bash
#
# start_karl.sh — one-command launcher for the fully-offline Robot Karl.
#
# Verifies every dependency, starts the Reachy Mini daemon if needed,
# detects the LED-eye ESP32, then launches an interactive experience.
#
# Usage:
#   ./start_karl.sh            # "Hey Karl" wake-word assistant (default)
#   ./start_karl.sh listen     # continuous conversation + speaker tracking
#   ./start_karl.sh say "Hi"   # quick offline speech test
#
# Everything runs locally on the Mac (Apple Silicon): Whisper (STT),
# Ollama (LLM) and Piper (TTS). No cloud APIs.

set -uo pipefail
cd "$(dirname "$0")"

# ── Config ───────────────────────────────────────────────────────────────
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2}"
PIPER_MODEL="piper_models/en_GB-northern_english_male-medium.onnx"
PIPER_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/northern_english_male/medium"
MODE="${1:-wake}"

green() { printf '\033[32m✓\033[0m %s\n' "$1"; }
warn()  { printf '\033[33m!\033[0m %s\n' "$1"; }
die()   { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

# ── 1. Python interpreter (prefer repo venv, then ~/venv, then python3) ───
if   [ -x "venv/bin/python" ];            then PY="venv/bin/python"
elif [ -x "$HOME/venv/bin/python" ];      then PY="$HOME/venv/bin/python"
elif command -v python3 >/dev/null 2>&1;  then PY="$(command -v python3)"
else die "No Python interpreter found. Create one with: python3 -m venv venv"; fi
green "Python: $PY"

# ── 2. Piper voice model (download once if missing) ──────────────────────
if [ ! -f "$PIPER_MODEL" ]; then
  warn "Piper voice model missing — downloading (~60MB)…"
  mkdir -p piper_models
  curl -fSL "$PIPER_BASE/en_GB-northern_english_male-medium.onnx"      -o "$PIPER_MODEL"      || die "Voice model download failed"
  curl -fSL "$PIPER_BASE/en_GB-northern_english_male-medium.onnx.json" -o "$PIPER_MODEL.json" || die "Voice config download failed"
fi
green "Voice model: en_GB-northern_english_male"

# ── 3. Ollama service + model ────────────────────────────────────────────
if ! curl -fs http://localhost:11434/api/version >/dev/null 2>&1; then
  if command -v ollama >/dev/null 2>&1; then
    warn "Ollama not running — starting 'ollama serve'…"
    ollama serve >/dev/null 2>&1 &
    for _ in $(seq 1 15); do
      curl -fs http://localhost:11434/api/version >/dev/null 2>&1 && break
      sleep 1
    done
  fi
fi
curl -fs http://localhost:11434/api/version >/dev/null 2>&1 || die "Ollama is not reachable on :11434"
if ! ollama list 2>/dev/null | grep -q "^${OLLAMA_MODEL}"; then
  warn "Model '$OLLAMA_MODEL' not found — pulling…"
  ollama pull "$OLLAMA_MODEL" || die "Could not pull $OLLAMA_MODEL"
fi
green "Ollama model: $OLLAMA_MODEL"

# ── 4. Reachy Mini daemon (start if not already running) ─────────────────
if ! pgrep -f reachy-mini-daemon >/dev/null 2>&1; then
  DAEMON=""
  for c in "venv/bin/reachy-mini-daemon" "$HOME/venv/bin/reachy-mini-daemon" "$(command -v reachy-mini-daemon 2>/dev/null)"; do
    [ -n "$c" ] && [ -x "$c" ] && DAEMON="$c" && break
  done
  [ -n "$DAEMON" ] || die "reachy-mini-daemon not found"
  warn "Starting Reachy Mini daemon…"
  "$DAEMON" >/tmp/reachy-daemon.log 2>&1 &
  sleep 6
fi
pgrep -f reachy-mini-daemon >/dev/null 2>&1 || die "Daemon failed to start (see /tmp/reachy-daemon.log)"
green "Reachy Mini daemon running"

# ── 5. Camera brightness fix (non-fatal — needs uvc-util) ────────────────
if "$PY" fix_camera.py >/tmp/reachy-camera.log 2>&1; then
  green "Camera brightness fix applied"
else
  warn "Camera fix skipped (see /tmp/reachy-camera.log — likely uvc-util not installed)"
fi

# ── 6. LED eyes (optional — auto-detect the ESP32) ───────────────────────
EYES_PORT="$($PY - <<'PY'
import reachy_leds
ser = reachy_leds.find_port()
if ser:
    print(ser.port); ser.close()
PY
)"
if [ -n "$EYES_PORT" ]; then
  export REACHY_EYES_PORT="$EYES_PORT"
  green "LED eyes detected on $EYES_PORT"
else
  warn "LED eyes not detected — running without them"
fi

# ── 7. Launch the chosen experience ──────────────────────────────────────
echo
case "$MODE" in
  wake)   green "Launching 'Hey Karl' wake-word assistant — Ctrl+C to stop"; exec "$PY" -u reachy_wake.py ;;
  listen) green "Launching continuous conversation — Ctrl+C to stop";        exec "$PY" -u reachy_listen.py ;;
  say)    shift; exec "$PY" reachy_say.py "$@" ;;
  *)      die "Unknown mode '$MODE' (use: wake | listen | say)" ;;
esac
