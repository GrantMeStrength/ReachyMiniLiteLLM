# Reachy Mini Lite + LLM

Control a [Reachy Mini Lite](https://www.pollen-robotics.com/reachy-mini/) robot using Python — with local LLM-powered speech via [Ollama](https://ollama.com) and [Piper TTS](https://github.com/rhasspy/piper).

Everything runs locally on your machine. No cloud APIs required.

## Quick Start

```bash
# 1. Set up environment
python -m venv venv
source venv/bin/activate
pip install reachy-mini ollama piper-tts scipy gtts

# 2. Download a Piper voice model (~60MB, one-time)
mkdir -p piper_models
curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx" \
     -o piper_models/en_US-amy-medium.onnx
curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json" \
     -o piper_models/en_US-amy-medium.onnx.json

# 3. Start the daemon (in a separate terminal)
reachy-mini-daemon

# 4. Run!
python wave_antennas.py                          # wave the antennas
python play_tone.py                              # play a melody
python speak.py                                  # speak via Google TTS
python reachy_speak_llm.py "Tell me a joke!"     # LLM + local TTS
python reachy_speak_animated.py                  # LLM + TTS + head/antenna animation
```

## Scripts

| Script | Description | Internet? |
|--------|-------------|-----------|
| `wave_antennas.py` | Wave the antennas in a friendly greeting | No |
| `play_tone.py` | Play a C-E-G-C melody through the speaker | No |
| `speak.py` | Speak a phrase using Google TTS | Yes |
| `reachy_speak_llm.py` | Ask Ollama a question, speak the reply with Piper TTS | No |
| `reachy_speak_animated.py` | LLM speech + animated head/antenna movements | No |

## Skills Reference

See **[ReachySkills.md](ReachySkills.md)** for the full SDK reference covering movement, audio, camera, media backends, and more.

## Requirements

- **Hardware:** Reachy Mini Lite (USB version)
- **Software:** Python 3.10+, [Ollama](https://ollama.com) with a model (e.g. `llama3.2`)
- **OS:** macOS (tested on Apple Silicon) — Linux should also work

## License

MIT
