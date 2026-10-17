"""BEYOND's defaults: exactly what a fresh download uses.

Every port number BEYOND uses is defined here and nowhere else. Your own changes will be saved in
data/settings.json (Phase 4), which is never committed, so a new user always starts from these values.
"""
from pathlib import Path

VERSION = '0.1.0'
PHASE = 1

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'                          # settings, chats, logs: created at runtime, git-ignored
WEB_DIR = Path(__file__).resolve().parent / 'web'

# BEYOND's own web page. 7770 stays clear of Local AI Studio (1420, 8080, 10086) and of ports other AI apps
# commonly use (7860 Gradio, 8000, 8188 ComfyUI, 1234 LM Studio, 11434 Ollama, 3000).
WEB_PORT = 7770

LOCAL_ONLY_HOST = '127.0.0.1'   # default: only this PC can open BEYOND
NETWORK_HOST = '0.0.0.0'        # "Allow other devices on my network" (an opt-in setting, Phase 4)
