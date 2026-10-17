"""BEYOND's defaults: exactly what a fresh download uses.

Every port number BEYOND uses is defined here and nowhere else. Your own changes are saved in data/settings.json,
which is never committed and only holds what differs from these defaults, so a new user always starts from here
(and deleting that file brings these values back).
"""
from pathlib import Path

VERSION = '0.14.0'
PHASE = 14

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'                          # settings, chats, logs: created at runtime, git-ignored
WEB_DIR = Path(__file__).resolve().parent / 'web'

# BEYOND's own web page. 7770 stays clear of Local AI Studio (1420, 8080, 10086) and of ports other AI apps
# commonly use (7860 Gradio, 8000, 8188 ComfyUI, 1234 LM Studio, 11434 Ollama, 3000).
WEB_PORT = 7770

# Ports BEYOND's web page must never take, because other local AI apps rely on them (checked when you change the port).
RESERVED_PORTS = {
    1420: 'Local AI Studio (web page)', 8080: 'Local AI Studio (image engine)',
    10086: 'Local AI Studio (AI engine)', 1234: 'LM Studio', 11434: 'Ollama',
    7860: 'Gradio apps', 8188: 'ComfyUI',
}
MIN_PORT, MAX_PORT = 1024, 65535    # below 1024 needs administrator rights

LOCAL_ONLY_HOST = '127.0.0.1'   # only this PC can open BEYOND (the default)
NETWORK_HOST = '0.0.0.0'        # other devices on the network can too ("Allow other devices on my network")

# Settings a person can change. These are the fresh-install values; changes go in data/settings.json.
DEFAULTS = {
    # An AI server BEYOND connects to (e.g. Local AI Studio's engine, LM Studio, Ollama), as its web address.
    # Empty on a fresh install: BEYOND's own built-in engine arrives in Phase 33.
    'ai_server_url': '',
    # Model name to ask for. Empty = whatever model the server has loaded (llama.cpp / Studio ignore it anyway).
    'ai_model': '',
    # The port BEYOND's page is on.
    'web_port': WEB_PORT,
    # Let phones and other computers on your network open BEYOND. Off by default: there's no login yet (Phase 38).
    'allow_network': False,
    # Notice lasting facts you mention about yourself and save them ("ðŸ§  Noted for next time"). Uses the AI once more
    # after a personal-sounding message.
    'auto_facts': True,
    # Search older conversations for exchanges related to your question and give them to the AI as background.
    'recall': True,
    'auto_lookup': True,
}
BOOLEAN_SETTINGS = ('allow_network', 'auto_facts', 'recall', 'auto_lookup')
RESTART_SETTINGS = ('web_port', 'allow_network')   # these only take effect after BEYOND restarts

PERSONALITY_FILE = Path(__file__).resolve().parent / 'personality.md'   # BEYOND's system prompt

AI_TIMEOUT_SECONDS = 300      # a long answer on a processor-only PC can take minutes
HISTORY_LIMIT = 12            # most recent messages sent with each question (the window moves 6 -> 12 -> 6 â€¦)
HISTORY_MESSAGE_CHARS = 1500  # an earlier message longer than this is shortened in the history sent to the AI
ANSWER_MAX_TOKENS = 700       # cap on one answer's length (the personality asks for short answers anyway)
TEMPERATURE = 0.7             # how adventurous the wording is (0 = always the same, higher = more varied)
