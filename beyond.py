r"""Start BEYOND: check the port is free, then run the web server.

Run with:  .\.venv\Scripts\python.exe beyond.py   (then open http://127.0.0.1:7770)
"""
import sys

import uvicorn

from app import config, ports
from app.server import app


def main():
    host, port = config.LOCAL_ONLY_HOST, config.WEB_PORT
    problem = ports.problem(host, port)
    if problem:
        print(problem, flush=True)
        return 1
    config.DATA_DIR.mkdir(exist_ok=True)
    print(f'BEYOND {config.VERSION} is running: open http://127.0.0.1:{port} in your browser. Press Ctrl+C to stop.',
          flush=True)
    uvicorn.run(app, host=host, port=port, log_level='warning')
    return 0


if __name__ == '__main__':
    sys.exit(main())
