"""Google Sheets actions still holding a broad grant: ``python -m backend.sheets_legacy``

Counts the Sheets actions on forms by the credential they hold: ``legacy``
(any scope other than exactly ``drive.file``, including credentials that
cannot be read), ``drive_file``, plus how many are already marked
``needs_reconsent``, how many billing owners were mailed and how many runs were
skipped (services/sheets_reconsent.py). Run it before switching
``GOOGLE_SHEETS_OAUTH`` to ``backend`` to size the reconnect mail.

Read-only: it changes nothing. Counts only, never ids, titles, addresses or
tokens. Reads through the routed repositories, so it follows the services'
read source (``DB_READ_SOURCE``).
"""

from __future__ import annotations

import asyncio
import json
import sys

from backend.cli_store import routed_repositories

# forms (their actions' secrets and parameters); actions are Postgres only
GROUPS = ("forms",)


async def main(argv) -> int:
    from backend.app.services.sheets_reconsent import count_legacy_sheets_actions

    if argv:
        print("usage: python -m backend.sheets_legacy (no arguments)")
        return 2
    async with routed_repositories(*GROUPS) as container:
        counts = await count_legacy_sheets_actions(
            container.form_repo(), container.action_repository(), container.crypto()
        )
    print(json.dumps(counts, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
