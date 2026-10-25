"""No Beanie reads or writes anywhere (common/db/access_guard.py).

The service is served from Postgres only: a document saved or queried
directly would talk to a Mongo client that never connects. Everything goes
through the Postgres repository. Add a module to ``ALLOWED`` only with the
reason it may bypass it.
"""

from pathlib import Path

import common

from common.db.access_guard import find_direct_access, unused_allow_entries

PACKAGE = Path(__file__).resolve().parents[2] / "googleform"
COMMON = Path(common.__file__).resolve().parent

ALLOWED = {
    "migrate/": "the Mongo -> Postgres migration CLI reads and writes both stores by design",
}


def test_documents_are_only_touched_by_repositories():
    hits = find_direct_access(
        PACKAGE, document_roots=[PACKAGE, COMMON], allowed=ALLOWED
    )
    assert hits == [], (
        "route these through the Postgres repository:\n  " + "\n  ".join(str(h) for h in hits)
    )


def test_the_allow_list_names_existing_paths():
    assert unused_allow_entries(PACKAGE, ALLOWED) == []
