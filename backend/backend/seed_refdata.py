"""python -m backend.seed_refdata [--origin ORIGIN ...] [--google-enabled true|false] [--google-url URL]

Seeds the reference data a fresh installation needs, in Postgres: the allowed
origins and the Google Forms provider. Until 4.1 the Mongo seed container
(``seed-data-deployment.js``) wrote the same rows to Mongo; these groups are
served from Postgres only now. deploy.sh runs it once on a new stack, with the
web app's public origins (``DASHBOARD_DOMAIN`` / ``FORM_DOMAIN``).

Without ``--origin`` the origins are the local web app ports only while the
backend's ``API_CLIENT_URL`` is a local address; otherwise they are that URL's
origin, so a stack with a public address never gets localhost origins.

Each table is seeded only while it is empty, so running it on every start is
safe: an upgraded stack (whose rows were imported from Mongo) and anything an
operator changed since are left as they are. Needs DATABASE_URL and the app
schema at its head. It refuses, as the backend's start does, while Mongo holds
refdata that was never imported (:mod:`backend.db.mongo_import_guard`): seeding
the empty tables first would hide that data from the start's check. Mongo is
asked only then, and only while MONGO_URI is set.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Iterable, Optional
from urllib.parse import urlsplit

from loguru import logger

from backend.app.schemas.form_plugin_config import FormPluginConfigDocument
from backend.app.services.login_redirect import origin_of

#: the local web app ports: the dashboard, nginx's client host and its
#: custom-domain host (docker-compose.deployment.yml)
DEFAULT_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
)
DEFAULT_GOOGLE_URL = "http://integrations-googleform:8000/api/v1"
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def is_local_url(url: str) -> bool:
    try:
        return urlsplit(url).hostname in LOCAL_HOSTS
    except ValueError:
        return False


def default_origins(client_url: Optional[str] = None) -> tuple:
    """The origins seeded when none are given: the local web app ports while
    the client URL (``API_CLIENT_URL``) is local, else the client URL's own
    origin. A stack with a public address never gets localhost origins."""
    if client_url is None:
        from backend.config import settings

        client_url = settings.api_settings.CLIENT_URL
    client = origin_of(client_url)
    if client is None or is_local_url(client_url):
        return DEFAULT_ORIGINS
    return (client,)


def google_provider(url: str, enabled: bool) -> FormPluginConfigDocument:
    return FormPluginConfigDocument(
        enabled=enabled,
        provider_name="google",
        provider_url=url,
        auth_callback_url=f"{url}/google/oauth/callback",
        type="oauth2",
    )


async def seed_refdata(
    origins_repo,
    providers_repo,
    *,
    origins: Iterable[str] = DEFAULT_ORIGINS,
    google_enabled: bool = False,
    google_url: str = DEFAULT_GOOGLE_URL,
) -> dict:
    """Seed each empty table; returns how many rows each got (0: it had rows)."""
    seeded = {"allowed_origins": 0, "forms_plugin_configs": 0}
    if not await origins_repo.list_origins():
        for origin in dict.fromkeys(origins):  # once each, in order
            await origins_repo.add(origin)
            seeded["allowed_origins"] += 1
    if not await providers_repo.list():
        await providers_repo.add(google_provider(google_url, google_enabled))
        seeded["forms_plugin_configs"] = 1
    return seeded


def _bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered not in ("true", "false"):
        raise argparse.ArgumentTypeError("expected true or false")
    return lowered == "true"


def _origin(value: str) -> str:
    """An origin as browsers send it (lower case, no default port)."""
    origin = origin_of(value)
    try:
        parts = urlsplit(value)
    except ValueError:
        parts = None
    if origin is None or parts is None or parts.path not in ("", "/") or (
        parts.query or parts.fragment
    ):
        raise argparse.ArgumentTypeError(
            "expected an origin: http(s)://host[:port], without a path"
        )
    return origin


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.seed_refdata",
        description="Seed the allowed origins and the Google Forms provider into "
        "an empty Postgres store.",
    )
    parser.add_argument(
        "--origin",
        action="append",
        dest="origins",
        type=_origin,
        help="an allowed origin, http(s)://host[:port] (repeatable; default: the "
        "local web app ports while API_CLIENT_URL is local, else its origin)",
    )
    parser.add_argument(
        "--google-enabled",
        type=_bool,
        default=False,
        help="whether the Google Forms provider starts enabled (default false)",
    )
    parser.add_argument("--google-url", default=DEFAULT_GOOGLE_URL)
    return parser


async def run(args: argparse.Namespace) -> int:
    from backend.app.container import container
    from backend.config import settings
    from backend.db.mongo_import_guard import (
        UnimportedMongoData,
        check_unimported_mongo_data,
        mongo_uri_configured,
    )
    from backend.db.startup import dispose_postgres

    try:
        try:
            await check_unimported_mongo_data(
                container.pg_engine(),
                client=None,
                uri=mongo_uri_configured(settings.mongo_settings),
                database=settings.mongo_settings.DB,
                groups=("refdata",),
            )
        except UnimportedMongoData as exc:
            logger.error("{}", exc)
            return 2
        seeded = await seed_refdata(
            container.allowed_origins_repo(),
            container.form_provider_repo(),
            origins=args.origins or default_origins(),
            google_enabled=args.google_enabled,
            google_url=args.google_url,
        )
    finally:
        await dispose_postgres(container)
    for table, count in seeded.items():
        logger.info(
            "{}: {}", table, f"seeded {count} rows" if count else "has rows; unchanged"
        )
    return 0


def main(argv=None) -> int:
    return asyncio.run(run(build_parser().parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
