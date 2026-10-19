"""No Beanie reads or writes outside the repositories (common/db/access_guard.py).

A document saved or queried directly talks to Mongo alone, so dual and
postgres modes never see it. Add a module to ``ALLOWED`` only with the reason
it may bypass the routed repositories.
"""

from pathlib import Path

import common

from common.db.access_guard import find_direct_access, unused_allow_entries

PACKAGE = Path(__file__).resolve().parents[1] / "auth"
COMMON = Path(common.__file__).resolve().parent

ALLOWED = {
    "app/repositories/": "the repositories: the Mongo side of each routed pair",
    "migrate/": "the Mongo -> Postgres migration CLI reads and writes both stores by design",
}


def test_documents_are_only_touched_by_repositories():
    hits = find_direct_access(
        PACKAGE, document_roots=[PACKAGE, COMMON], allowed=ALLOWED
    )
    assert hits == [], (
        "route these through a repository method (marked @write_op for writes, "
        "with a Postgres twin):\n  " + "\n  ".join(str(h) for h in hits)
    )


def test_the_allow_list_names_existing_paths():
    assert unused_allow_entries(PACKAGE, ALLOWED) == []
