"""Shared configuration for Karl's local control scripts."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
PIPER_MODEL = str(
    ROOT / "piper_models/en_GB-northern_english_male-medium.onnx"
)
PIPER_CONFIG = f"{PIPER_MODEL}.json"
ANTENNA_REST = [0.15, -0.25]
LOCAL_CONNECTION_MODE = "localhost_only"
