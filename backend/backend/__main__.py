import os
import socket

import uvicorn

from backend.app import get_application
from backend.app.services.internal_routes import (
    internal_port,
    log_internal_routes_setup,
)

HOST = "0.0.0.0"


def _listening_socket(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, port))
    sock.set_inheritable(True)
    return sock


def main():
    """Run the FastAPI application: the public port (``PORT``, 8000) and the
    internal listener (``API_INTERNAL_PORT``, 8001; 0 = none) that only the
    services inside the stack reach (``app/services/internal_routes.py``)."""
    app = get_application()
    public = int(os.getenv("PORT", 8000))
    # no uvicorn access log: it prints the full request line, query string and
    # receipt number included; the app's request logger keeps method, redacted
    # path and status (app/middlewares/request_privacy.py)
    config = uvicorn.Config(app, host=HOST, port=public, access_log=False)
    server = uvicorn.Server(config)
    log_internal_routes_setup()
    sockets = [_listening_socket(public)]
    internal = internal_port()
    if internal:
        sockets.append(_listening_socket(internal))
    server.run(sockets=sockets)


if __name__ == "__main__":
    main()
