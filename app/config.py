"""BEYOND's defaults: exactly what a fresh download uses.

Every port number BEYOND uses is defined here and nowhere else. Your own changes are saved in data/settings.json,
which is never committed and only holds what differs from these defaults, so a new user always starts from here
(and deleting that file brings these values back).
"""
from pathlib import Path

VERSION = '0.27.0'
PHASE = 27

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'                          # settings, chats, logs: created at runtime, git-ignored
WEB_DIR = Path(__file__).resolve().parent / 'web'

# BEYOND's own web page. 7770 stays clear of Local AI Studio (1420, 8080, 10086) and of ports other AI apps
# commonly use (7860 Gradio, 8000, 8188 ComfyUI, 1234 LM Studio, 11434 Ollama, 3000).
WEB_PORT = 7770
# With network access on, BEYOND also serves https:// on the next port (7771) for other devices, because browsers
# only allow the microphone on secure pages (app/https.py).
HTTPS_PORT_OFFSET = 1

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
    # Separate, one-off CPU photo analysis. Fresh installs choose their own files in Settings.
    'vision_enabled': False,
    'vision_executable': '',
    'vision_model': '',
    'vision_mmproj': '',
    'vision_threads': 12,
    'vision_timeout': 600,
    # Separate CPU DreamShaper process; owner file paths stay in data/settings.json.
    'image_enabled': False,
    'image_executable': '',
    'image_model': '',
    'image_threads': 12,
    'image_timeout': 1200,
    # Offline speech. Models are selected locally; fresh downloads do not contain owner paths.
    'speech_enabled': False,
    'speech_auto': False,
    'speech_engine': 'kokoro',
    'speech_voice': 'af_heart',
    'speech_speed': 1.0,
    'speech_threads': 2,
    'speech_timeout': 180,
    'speech_kokoro_model': '',
    'speech_kokoro_voices': '',
    'speech_piper_model': '',
    # The port BEYOND's page is on.
    'web_port': WEB_PORT,
    # Let phones and other computers on your network open BEYOND. Off by default: there's no login yet (Phase 38).
    'allow_network': False,
    # Notice lasting facts you mention about yourself and save them ("🧠 Noted for next time"). Uses the AI once more
    # after a personal-sounding message.
    'auto_facts': True,
    # Search older conversations for exchanges related to your question and give them to the AI as background.
    'recall': True,
    # Check the weather, news or the web by itself when a question needs current information.
    'auto_lookup': True,
    # Windows popups (Phase 20), only while you're not looking at BEYOND's page: when the AI has replied, when a
    # reminder goes off, and when something went wrong (e.g. the AI server stopped answering).
    'popup_replies': True,
    'popup_reminders': True,
    'popup_errors': True,
    # Quiet hours: no popups between these times (24-hour "HH:MM"; both empty = no quiet hours).
    'quiet_start': '',
    'quiet_end': '',
    # Start BEYOND (in the tray) when you sign in to Windows.
    'start_with_windows': False,
}
BOOLEAN_SETTINGS = ('speech_enabled', 'speech_auto', 'image_enabled', 'vision_enabled', 'allow_network', 'auto_facts', 'recall', 'auto_lookup', 'popup_replies', 'popup_reminders',
                    'popup_errors', 'start_with_windows')
TIME_SETTINGS = ('quiet_start', 'quiet_end')
RESTART_SETTINGS = ('web_port', 'allow_network')   # these only take effect after BEYOND restarts

PERSONALITY_FILE = Path(__file__).resolve().parent / 'personality.md'   # BEYOND's system prompt

AI_TIMEOUT_SECONDS = 300      # a long answer on a processor-only PC can take minutes
HISTORY_LIMIT = 12            # most recent messages sent with each question (the window moves 6 -> 12 -> 6 …)
HISTORY_MESSAGE_CHARS = 1500  # an earlier message longer than this is shortened in the history sent to the AI
ANSWER_MAX_TOKENS = 700       # cap on one answer's length (the personality asks for short answers anyway)
TEMPERATURE = 0.7             # how adventurous the wording is (0 = always the same, higher = more varied)
