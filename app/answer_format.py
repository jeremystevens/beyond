"""Recognize explicit answer formats and remove only known presentation wrappers."""
import json
import re

_QUOTED = re.compile(r'\x60\x60\x60[\s\S]*?\x60\x60\x60|\x60[^\x60\n]+\x60|"[^"\n]+"')
_JSON_ONLY = re.compile(
    r'\b(?:return|output|respond with|give me)\s+(?:only|just)\s+(?:a\s+)?(?:valid\s+)?json\s+object\b'
    r'|\b(?:return|output|respond with)\s+(?:a\s+)?(?:valid\s+)?json\s+object\s+only\b',
    re.I,
)
_BULLET_COUNT = re.compile(
    r'\b(?:exactly\s+|(?:give|use|write|return|include|list|provide)\s+(?:me\s+)?)'
    r'(one|two|three|four|five|six|seven|eight|nine|ten|[1-9]\d?)\s+bullet(?: points?| lines?)?\b',
    re.I,
)
_NO_PREFACE = re.compile(r"\b(?:no|without|do not add|don't add)\s+(?:an?\s+)?(?:intro(?:duction)?|preface|extra text)\b", re.I)
_WORDS = 'one two three four five six seven eight nine ten'.split()
_BULLET = re.compile(r'^[ \t]*[-*+][ \t]+\S')
_BULLET_PREFACE = re.compile(r"^(?:sure[!.]?\s+)?here (?:are|is) (?:the|your) [^:\n]{1,70}:\s*\n", re.I)
_JSON_PREFACE = re.compile(r"^(?:got it[.!]\s*|sure[.!]\s*)?(?:here(?:'s| is) (?:your|the) json(?: object)?\s*:\s*)", re.I)
_JSON_FENCE = re.compile(r'^\x60\x60\x60(?:json)?[ \t]*\r?\n(.*?)\r?\n\x60\x60\x60[ \t]*$', re.I | re.S)
_JSON_INLINE = re.compile(r'^\x60([^\n]+)\x60$')


def requested_format(text):
    """Return the explicit format, if present in the user's task."""
    text = _QUOTED.sub(' ', text)
    if _JSON_ONLY.search(text):
        return 'json', None, True
    count = _BULLET_COUNT.search(text)
    no_preface = bool(_NO_PREFACE.search(text))
    if count:
        value = count[1].lower()
        return 'bullets', int(value) if value.isdigit() else _WORDS.index(value) + 1, no_preface
    if no_preface:
        return 'plain', None, True
    return None


def instruction(request):
    kind, count, no_preface = request
    if kind == 'json':
        return 'Return one valid JSON object only. Start with { and end with }. No Markdown, preface, or trailing text.'
    if kind == 'bullets':
        suffix = ' Omit introductions, headings, and trailing text.' if no_preface else ''
        return f'Use exactly {count} Markdown bullet lines, each beginning with "- ".{suffix}'
    return 'Start immediately with the requested content. Omit introductions and prefaces.'


def unwrap(text, request):
    """Keep the original answer unless an explicitly unwanted wrapper is recognized."""
    kind, count, no_preface = request
    if kind == 'json':
        candidate = _JSON_PREFACE.sub('', text, count=1)
        wrapper = _JSON_FENCE.fullmatch(candidate) or _JSON_INLINE.fullmatch(candidate)
        if wrapper:
            candidate = wrapper[1].strip()
        try:
            value = json.loads(candidate, parse_constant=_invalid_constant)
        except (ValueError, RecursionError):
            return text
        return candidate if isinstance(value, dict) else text
    if kind == 'bullets' and no_preface:
        candidate = _BULLET_PREFACE.sub('', text, count=1)
        lines = [line for line in candidate.splitlines() if line.strip()]
        if len(lines) == count and all(_BULLET.match(line) for line in lines):
            return candidate
    return text


def _invalid_constant(value):
    raise ValueError(value)
