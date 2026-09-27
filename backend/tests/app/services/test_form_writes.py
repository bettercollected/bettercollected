"""The one write path for form content."""

from types import SimpleNamespace

import pytest

from backend.app.services.form_writes import persist_form


class Repo:
    def __init__(self, stored):
        self.stored = stored
        self.saved = []

    async def get_form_document_by_id(self, form_id):
        return self.stored

    async def save_form(self, document):
        self.saved.append(document)


def form(**parts):
    base = dict(
        form_id="f",
        title="T",
        description=None,
        fields=[],
        theme=None,
        welcome_page=None,
        thankyou_page=None,
        published_at=None,
    )
    return SimpleNamespace(**{**base, **parts})


async def test_only_the_named_parts_are_written():
    stored = form(title="Mine")
    repo = Repo(stored)
    assert await persist_form(
        repo, stored, form(title="New", fields=["x"]), parts=["fields"]
    )
    assert repo.saved == [stored] and stored.fields == ["x"] and stored.title == "Mine"


async def test_a_guard_sees_the_form_as_it_is_now_and_can_stop_the_write():
    old_copy = form()
    now = form(fields=["edited meanwhile"])
    repo = Repo(now)
    saved = await persist_form(
        repo, old_copy, form(fields=["compiled"]), guard=lambda f: not f.fields
    )
    assert saved is False and repo.saved == [] and now.fields == ["edited meanwhile"]


async def test_unknown_parts_are_refused():
    with pytest.raises(ValueError):
        await persist_form(Repo(form()), form(), form(), parts=["settings"])
