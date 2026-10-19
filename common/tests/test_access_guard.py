"""The direct-access guard finds Beanie calls outside the repositories."""

import textwrap

import pytest

from common.db.access_guard import (
    document_classes,
    find_direct_access,
    unused_allow_entries,
)

MODELS = """
from beanie import Document
from common.configs.mongo_document import MongoDocument

class UserDocument(MongoDocument):
    email: str

class Base(Document):
    pass

class Child(Base):
    pass

class NotADocument:
    pass
"""

SERVICE = """
async def handler(user_repository, payment_service, user):
    await UserDocument.find_one({"email": "x"})          # class read
    await Child.find({"a": 1}).delete()                  # chained write
    await user.save()                                    # instance write
    doc = UserDocument(email="x")
    await doc.insert()
    await user_repository.save(user)                     # a repository: fine
    await payment_service.delete(user)                   # a service: fine
    values = {}
    values.update({"a": 1})                              # not awaited: fine
    NotADocument.find()                                  # not a document
    UserDocument.verify_doc_exists(user)                 # not a query
"""


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))


@pytest.fixture
def package(tmp_path):
    root = tmp_path / "svc"
    write(root, "schemas/models.py", MODELS)
    write(root, "services/handler.py", SERVICE)
    write(root, "repositories/user.py", "async def f():\n    await UserDocument.get(1)\n")
    write(root, "migrate/run.py", "async def f(d):\n    await d.save()\n")
    return root


def test_document_classes_are_transitive(package):
    found = document_classes([package])
    assert {"UserDocument", "Base", "Child"} <= found
    assert "NotADocument" not in found


def test_hits_outside_the_allowed_paths(package):
    hits = find_direct_access(
        package,
        document_roots=[package],
        allowed={"repositories/": "the repositories", "migrate/": "the migration CLI"},
    )
    assert [(h.path, h.line, h.call) for h in hits] == [
        ("services/handler.py", 3, "UserDocument...find_one()"),
        ("services/handler.py", 4, "Child...delete()"),
        ("services/handler.py", 4, "Child...find()"),
        ("services/handler.py", 5, "user.save()"),
        ("services/handler.py", 7, "doc.insert()"),
    ]


def test_an_allowed_file_is_skipped(package):
    hits = find_direct_access(
        package,
        document_roots=[package],
        allowed={
            "repositories/": "r",
            "migrate/": "m",
            "services/handler.py": "a reason",
        },
    )
    assert hits == []


def test_every_allow_entry_needs_a_reason(package):
    with pytest.raises(ValueError):
        find_direct_access(package, document_roots=[package], allowed={"x/": " "})


def test_unused_allow_entries(package):
    assert unused_allow_entries(
        package, {"repositories/": "r", "gone.py": "moved"}
    ) == ["gone.py"]
