"""Port checks: is a port free, and if not, which program is using it (so the message can say so)."""
import socket

import psutil


def users_of(port):
    """Programs listening on `port`, as [(pid, name, command line)]. Empty if none (or if Windows won't say)."""
    found = {}
    try:
        connections = psutil.net_connections(kind='inet')
    except (psutil.AccessDenied, OSError):
        return []
    for conn in connections:
        if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port and conn.pid:
            try:
                process = psutil.Process(conn.pid)
                found[conn.pid] = (conn.pid, process.name(), ' '.join(process.cmdline()))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                found[conn.pid] = (conn.pid, 'an unknown program', '')
    return list(found.values())


def can_bind(host, port):
    """Try to open the port ourselves. No SO_REUSEADDR: on Windows that would let us share a port that is taken."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def problem(host, port):
    """None if BEYOND can use the port, else a plain-language explanation of what is in the way and what to do."""
    users = users_of(port)
    if not users and can_bind(host, port):
        return None
    if any('beyond.py' in command for _, _, command in users):
        return (f'BEYOND is already running. Open http://127.0.0.1:{port} in your browser, '
                f'or close the other BEYOND window first.')
    who = ', '.join(f'{name} (process {pid})' for pid, name, _ in users) or 'another program'
    return (f"BEYOND can't start: port {port} is already in use by {who}.\n"
            f'Close that program, or give BEYOND a different port (WEB_PORT in app/config.py for now; '
            f'a settings page arrives in Phase 4).')
