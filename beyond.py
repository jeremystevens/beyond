r"""Start BEYOND: check the port is free, then run the web server.

Run with:  .\.venv\Scripts\python.exe beyond.py   (then open http://127.0.0.1:7770, or the port in Settings)

When the port or the network switch is changed on the settings page, BEYOND restarts itself here with the new
settings, without the window closing.
"""
import sys

import uvicorn

from app import config, ports, settings
from app.server import app


def main():
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
        print(f'BEYOND {config.VERSION} is running: open http://127.0.0.1:{port} in your browser. '
              f'Press Ctrl+C to stop.', flush=True)
        if values['allow_network']:
            for adapter, ip in ports.network_addresses():
                print(f'  Other devices on your network can use http://{ip}:{port}  ({adapter})', flush=True)
        server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level='warning'))
        app.state.server = server
        app.state.running = {'host': host, 'port': port, 'allow_network': values['allow_network']}
        app.state.restart_requested = False
        server.run()
        if not app.state.restart_requested:
            return 0
        previous = (host, port)
        print('Restarting BEYOND with the new settings...', flush=True)


if __name__ == '__main__':
    sys.exit(main())
