"""BEYOND's defaults: exactly what a fresh download uses.

Every port number BEYOND uses is defined here and nowhere else. Your own changes will be saved in
data/settings.json (Phase 4), which is never committed, so a new user always starts from these values.
"""
from pathlib import Path

VERSION = '0.3.0'
PHASE = 3

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'                          # settings, chats, logs: created at runtime, git-ignored
WEB_DIR = Path(__file__).resolve().parent / 'web'

# BEYOND's own web page. 7770 stays clear of Local AI Studio (1420, 8080, 10086) and of ports other AI apps
# commonly use (7860 Gradio, 8000, 8188 ComfyUI, 1234 LM Studio, 11434 Ollama, 3000).
WEB_PORT = 7770

LOCAL_ONLY_HOST = '127.0.0.1'   # default: only this PC can open BEYOND
NETWORK_HOST = '0.0.0.0'        # "Allow other devices on my network" (an opt-in setting, Phase 4)

# Settings a person can change. These are the fresh-install values; changes go in data/settings.json.
DEFAULTS = {
    # An AI server BEYOND connects to (e.g. Local AI Studio's engine, LM Studio, Ollama), as its web address.
    # Empty on a fresh install: BEYOND's own built-in engine arrives in Phase 33.
    'ai_server_url': '',
    # Model name to ask for. Empty = whatever model the server has loaded (llama.cpp / Studio ignore it anyway).
    'ai_model': '',
}

AI_TIMEOUT_SECONDS = 300    # a long answer on a processor-only PC can take minutes
CHAT_HISTORY_MESSAGES = 40  # recent messages sent with each question (refined in Phase 6)
