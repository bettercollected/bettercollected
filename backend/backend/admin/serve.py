"""``python -m backend.admin.serve``: run the admin service with uvicorn.

Binds ADMIN_BIND_HOST (default 127.0.0.1) on ADMIN_LISTEN_PORT (default
ADMIN_PORT). In the container the compose file binds 0.0.0.0 inside and
publishes the port on the host's loopback only."""

import os

import uvicorn

from backend.admin.asgi import get_admin_application
from backend.admin.config import AdminSettings
from backend.admin.db import make_engine
from backend.admin.gate.settings import GateSettings
from backend.admin.portal import Portal


def main() -> None:
    settings = GateSettings.from_env()  # invalid configuration stops here
    portal = Portal.build(make_engine(AdminSettings.from_env()))  # invalid config stops here
    app = get_admin_application(settings, portal=portal)
    uvicorn.run(
        app,
        host=os.environ.get("ADMIN_BIND_HOST") or "127.0.0.1",
        port=int(os.environ.get("ADMIN_LISTEN_PORT") or settings.port),
        proxy_headers=False,  # the gate reads the peer itself
        server_header=False,
        date_header=False,
        access_log=False,
        ws="none",
        h11_max_incomplete_event_size=65536,
    )


if __name__ == "__main__":
    main()
