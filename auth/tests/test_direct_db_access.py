"""No Beanie reads or writes in auth (common/db/access_guard.py).

auth is served from Postgres only (4.1): a Beanie document saved or queried
would talk to a Mongo store the service no longer has. Only the import from
4.0 reads Mongo. Add a module to ``ALLOWED`` only with the reason it may.
"""

from pathlib import Path

import common

from common.db.access_guard import find_direct_access, unused_allow_entries

PACKAGE = Path(__file__).resolve().parents[1] / "auth"
COMMON = Path(common.__file__).resolve().parent

ALLOWED = {
    "app/repositories/": "the repository: its own Postgres calls (upsert, delete...) share Beanie's method names",
    "migrate/": "the Mongo -> Postgres migration CLI reads and writes both stores by design",
}


def test_documents_are_only_touched_by_repositories():
    hits = find_direct_access(
        PACKAGE, document_roots=[PACKAGE, COMMON], allowed=ALLOWED
    )
    assert (
        hits == []
    ), "go through the user repository (Postgres) instead:\n  " + "\n  ".join(
        str(h) for h in hits
    )


def test_the_allow_list_names_existing_paths():
    assert unused_allow_entries(PACKAGE, ALLOWED) == []
