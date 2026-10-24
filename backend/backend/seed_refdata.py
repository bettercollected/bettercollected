"""python -m backend.seed_refdata [--origin ORIGIN ...] [--google-enabled true|false] [--google-url URL]

Seeds the reference data a fresh installation needs, in Postgres: the allowed
origins and the Google Forms provider. Until 4.1 the Mongo seed container
(``seed-data-deployment.js``) wrote the same rows to Mongo; these groups are
served from Postgres only now.

Each table is seeded only while it is empty, so running it on every start is
safe: an upgraded stack (whose rows were imported from Mongo) and anything an
operator changed since are left as they are. Needs DATABASE_URL and the app
schema at its head; never touches Mongo.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Iterable

from loguru import logger

from backend.app.schemas.form_plugin_config import FormPluginConfigDocument

#: what seed-data-deployment.js inserts into an empty collection
DEFAULT_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
)
DEFAULT_GOOGLE_URL = "http://integrations-googleform:8000/api/v1"


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
        for origin in origins:
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
        help="an allowed origin (repeatable; default: the local web app ports)",
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
    from backend.db.startup import dispose_postgres

    try:
        seeded = await seed_refdata(
            container.allowed_origins_repo(),
            container.form_provider_repo(),
            origins=args.origins or DEFAULT_ORIGINS,
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
