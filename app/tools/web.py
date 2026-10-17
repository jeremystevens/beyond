"""Shared helpers for the online lookups (/web, /weather, /news, /wiki, /define, /movie, /tv).

All of them use free public services with no API key or account. Only what you typed after the command is sent.
Whatever comes back is third-party text: it is shown to you, never followed as instructions.
"""
import httpx

HEADERS = {'User-Agent': 'BEYOND/1.0 (personal local AI assistant; https://github.com/jeremystevens/beyond)'}


class Unavailable(Exception):
    """A lookup service couldn't be reached or answered with an error. The message names the service."""


def get(url, timeout=12, **kwargs):
    """GET with BEYOND's User-Agent, following redirects (httpx doesn't by default). Raises httpx.HTTPError."""
    response = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True, **kwargs)
    response.raise_for_status()
    return response


def get_limited(url, limit, timeout=10):
    """GET at most `limit` bytes (news feeds), so a huge or endless answer can't fill the memory."""
    with httpx.stream('GET', url, headers=HEADERS, timeout=timeout, follow_redirects=True) as response:
        response.raise_for_status()
        body = b''
        for chunk in response.iter_bytes():
            body += chunk
            if len(body) > limit:
                raise ValueError('The feed is too large')
    return body
