"""``python -m backend.admin.serve``: run the admin service with uvicorn.

Binds ADMIN_BIND_HOST (default 127.0.0.1) on ADMIN_LISTEN_PORT (default
ADMIN_PORT). In the container the compose file binds 0.0.0.0 inside and
publishes the port on the host's loopback only.

Without the settings the sign-in portal needs (database URL, master key, admin
addresses) the service starts as the bare gate: ``/healthz`` and 404s only, with
one warning naming the missing settings. With all of them it serves the portal;
a value that is present but invalid stops startup."""

import logging
import os
from typing import Mapping, Optional

import uvicorn

from backend.admin.asgi import get_admin_application
from backend.admin.config import AdminSettings
from backend.admin.db import make_engine
from backend.admin.gate.settings import GateSettings
from backend.admin.portal import Portal
from backend.admin.portal_config import PortalSettings, missing_portal_settings

log = logging.getLogger("backend.admin")


def build_app(env: Optional[Mapping[str, str]] = None):
    """The ASGI application for ``env`` (the process environment by default)."""
    source = os.environ if env is None else env
    settings = GateSettings.from_env(source)  # invalid configuration stops here
    missing = missing_portal_settings(source)
    if missing:
        log.warning(
            "admin portal disabled, serving only the health check: "
            "not set: %s",
            ", ".join(missing),
        )
        return get_admin_application(settings)
    portal = Portal.build(
        make_engine(AdminSettings.from_env(source)),
        env=source,
        settings=PortalSettings.from_env(source),
    )
    return get_admin_application(settings, portal=portal)


def main() -> None:
    settings = GateSettings.from_env()
    app = build_app()
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
