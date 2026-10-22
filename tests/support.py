"""Shared test helpers."""
from app import chats


class _ClosingConnection:
    """A database connection that is always closed when the code using it is done.

    Windows can't delete a temporary test folder while a connection to its database is still open, so the tests make
    every connection close itself. App code opens connections in two ways, and both work with this:

    - ``with chats.connect() as db:``: a transaction (committed, or rolled back on an error), then closed;
    - ``with closing(chats.connect()) as db:``: closed at the end, without a transaction.
    """

    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def __enter__(self):
        self._db.__enter__()
        return self._db

    def __exit__(self, *problem):
        try:
            return self._db.__exit__(*problem)
        finally:
            self._db.close()

    def close(self):
        self._db.close()


def local_request():
    """A request from the PC BEYOND runs on, for tests that call a route function directly."""
    from starlette.requests import Request
    return Request({'type': 'http', 'method': 'POST', 'path': '/', 'headers': [], 'query_string': b'',
                    'client': ('127.0.0.1', 50000), 'server': ('127.0.0.1', 7770), 'scheme': 'http'})


def closing_connections():
    """A replacement for chats.connect that hands out self-closing connections (use with patch.object)."""
    connect = chats.connect

    def closing_connect():
        return _ClosingConnection(connect())
    return closing_connect
