r"""Start BEYOND: check the port is free, then run the web server, with an icon in the Windows tray.

Run with:  .\.venv\Scripts\pythonw.exe beyond.py   (no console window; BEYOND lives in the tray)
      or:  .\.venv\Scripts\python.exe beyond.py --console   (in a console window, without the tray icon)
Then open http://127.0.0.1:7770 (or the port in Settings), or click the tray icon.

The tray icon (Phase 20) has Open BEYOND (also a double-click), Pause popups, and Quit. BEYOND keeps running when
the browser is closed, so reminders still go off. When the port or the network switch is changed on the settings
page, BEYOND restarts itself here with the new settings.
"""
import sys
import threading
import webbrowser

from app import config

# pythonw.exe has no console: keep what BEYOND prints in data\beyond.log instead of losing it (or crashing on it).
if sys.stdout is None or sys.stderr is None:
    config.DATA_DIR.mkdir(exist_ok=True)
    _log = open(config.DATA_DIR / 'beyond.log', 'a', encoding='utf-8', buffering=1)
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log

import uvicorn   # noqa: E402  (after the output fix above, so uvicorn logs somewhere)

from app import notify, ports, settings   # noqa: E402
from app.server import app   # noqa: E402

state = {'quitting': False}


def serve():
    """Run the web server; returns an exit code. Restarts itself when the port or network setting changes."""
    previous = None   # where BEYOND was running before a restart, to fall back to if the new port is taken
    while True:
        values = settings.load()
        host = config.NETWORK_HOST if values['allow_network'] else config.LOCAL_ONLY_HOST
        port = values['web_port']
        problem = ports.problem(host, port)
        if problem and previous and not ports.problem(*previous):
            print(problem + f'\nStaying on port {previous[1]} for now.', flush=True)
            (host, port), values['allow_network'] = previous, previous[0] == config.NETWORK_HOST
        elif problem:
            print(problem, flush=True)
            return 1
        config.DATA_DIR.mkdir(exist_ok=True)
        notify.base_url = f'http://127.0.0.1:{port}'
        print(f'BEYOND {config.VERSION} is running: open http://127.0.0.1:{port} in your browser.', flush=True)
        if values['allow_network']:
            for adapter, ip in ports.network_addresses():
                print(f'  Other devices on your network can use http://{ip}:{port}  ({adapter})', flush=True)
        server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level='warning'))
        app.state.server = server
        app.state.running = {'host': host, 'port': port, 'allow_network': values['allow_network']}
        app.state.restart_requested = False
        server.run()
        if not app.state.restart_requested or state['quitting']:
            return 0
        previous = (host, port)
        print('Restarting BEYOND with the new settings...', flush=True)


def run_with_tray():
    """The web server in a background thread; the tray icon on the main thread (Windows wants it there)."""
    import pystray

    result = {'code': 0}

    def server_thread():
        result['code'] = serve()
        icon.stop()   # the server stopped (Quit, or the port was taken): remove the icon and exit

    def open_beyond(_icon=None, _item=None):
        webbrowser.open(notify.base_url)

    def toggle_pause(_icon, _item):
        notify.paused = not notify.paused

    def quit_beyond(_icon, _item):
        state['quitting'] = True
        server = getattr(app.state, 'server', None)
        if server:
            server.should_exit = True
        else:
            icon.stop()

    icon = pystray.Icon('BEYOND', notify.icon_image(64), f'BEYOND {config.VERSION}', pystray.Menu(
        pystray.MenuItem('Open BEYOND', open_beyond, default=True),
        pystray.MenuItem('Pause popups', toggle_pause, checked=lambda _item: notify.paused),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quit BEYOND', quit_beyond)))
    threading.Thread(target=server_thread, name='beyond-server', daemon=True).start()
    icon.run()
    return result['code']


def main():
    if '--console' in sys.argv or sys.platform != 'win32':
        return serve()
    try:
        import pystray  # noqa: F401
    except ImportError:
        print('The tray icon needs pystray (pip install -r requirements.txt); running without it.', flush=True)
        return serve()
    return run_with_tray()


if __name__ == '__main__':
    sys.exit(main())
