"""Deterministic questions for bare requests with no supplied source or conversation."""
import re

_BARE = (
    (r"(?:reply|respond) to (?:this|the) (?:email|e-mail|message)", "Could you paste the email or message you want me to reply to?"),
    (r"(?:help (?:me )?(?:to )?)?(?:fix|troubleshoot) (?:this|the) (?:error|problem)", "What error message do you see?"),
    (r"(?:write|draft) (?:me )?(?:a|the) letter", "What should the letter say?"),
)


def question(history):
    # Existing conversation may already contain the missing detail. Do not guess whether it does.
    if len(history) != 1 or history[0].get('role') != 'user':
        return ''
    text = history[0]['content'].strip()
    text = re.sub(r'^(?:please\s+|(?:can|could|would) you\s+)', '', text, flags=re.I)
    text = re.sub(r'^please\s+', '', text, flags=re.I)
    text = text.rstrip(' .!?').strip()
    for pattern, reply in _BARE:
        if re.fullmatch(pattern, text, re.I):
            return reply
    return ''
