"""No Beanie reads or writes outside the repositories (common/db/access_guard.py).

A document saved or queried directly talks to Mongo alone, so dual and
postgres modes never see it: the write is missing from Postgres, and once a
group reads from Postgres it is lost. Add a module to an ``ALLOWED`` map only
with the reason it may bypass the routed repositories.

Raw pymongo access (operator tools that read collections by name) is outside
this check: it is not a Beanie document call.
"""

from pathlib import Path

import common
import pytest

from common.db.access_guard import find_direct_access, unused_allow_entries

BACKEND = Path(__file__).resolve().parents[2]
COMMON = Path(common.__file__).resolve().parent

PACKAGES = {
    "backend": {
        "app/repositories/": "the repositories: the Mongo side of each routed pair",
        "migrate/": "the Mongo -> Postgres migration CLI reads and writes both stores by design",
    },
    # seed and maintenance scripts: none needs an exception today
    "scripts": {},
}


@pytest.mark.parametrize("package", sorted(PACKAGES))
def test_documents_are_only_touched_by_repositories(package):
    root = BACKEND / package
    hits = find_direct_access(
        root,
        document_roots=[BACKEND / "backend", COMMON],
        allowed=PACKAGES[package],
    )
    assert hits == [], (
        "route these through a repository method (marked @write_op for writes, "
        "with a Postgres twin):\n  " + "\n  ".join(f"{package}/{h}" for h in hits)
    )


@pytest.mark.parametrize("package", sorted(PACKAGES))
def test_the_allow_list_names_existing_paths(package):
    assert unused_allow_entries(BACKEND / package, PACKAGES[package]) == []
