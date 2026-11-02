"""One list of the audit event kinds, for the writers to check against.

``record`` and ``record_many_or_refuse`` (``services/form_access/audit.py``) used to
each assert their own union of kind groups, and the two drifted: a batched entry
of a kind the other accepted was refused. Both now assert ``ALL_KINDS``, and this
file makes sure the list cannot fall behind the groups of the schema. Synthetic."""

import pytest
from common.ids import RecordId
from common.models.user import User

from backend.app.schemas import workspace_audit_event as schema
from backend.app.services.form_access import audit


def kind_groups() -> dict:
    """Every group of kinds in the schema: a module-level tuple of strings named
    ``*_EVENTS`` (other tuples, such as the parts an automation entry may name, are
    not kinds)."""
    return {
        name: value
        for name, value in vars(schema).items()
        if name.endswith("_EVENTS")
        and isinstance(value, tuple)
        and value
        and all(isinstance(item, str) for item in value)
    }


def test_every_group_of_kinds_in_the_schema_is_in_all_kinds():
    groups = kind_groups()
    assert {
        "ACCESS_EVENTS",
        "API_KEY_EVENTS",
        "MEMBER_FORM_EVENTS",
        "PROMOTION_EVENTS",
        "SETTINGS_EVENTS",
        "AUTOMATION_EVENTS",
        "RESPONSE_REVISION_EVENTS",
    } <= set(groups)
    for name, kinds in groups.items():
        missing = [kind for kind in kinds if kind not in schema.ALL_KINDS]
        assert not missing, (
            f"{name} has kinds that are not in ALL_KINDS (add the group to ALL_KINDS "
            f"in schemas/workspace_audit_event.py): {missing}"
        )


def test_all_kinds_holds_only_kinds_of_a_group_and_none_twice():
    grouped = [kind for kinds in kind_groups().values() for kind in kinds]
    assert set(schema.ALL_KINDS) == set(grouped)
    assert len(schema.ALL_KINDS) == len(set(schema.ALL_KINDS)), "a kind is in two groups"


class _Repo:
    def __init__(self):
        self.stored = []

    async def record(self, document):
        self.stored.append(document)

    async def record_many(self, documents):
        self.stored.extend(documents)


@pytest.mark.parametrize("kind", sorted(set(schema.ALL_KINDS)))
async def test_both_writers_accept_every_kind(kind):
    user = User(id=str(RecordId()), sub="someone@example.org")
    workspace_id = RecordId()
    one, many = _Repo(), _Repo()
    assert await audit.record(one, kind, workspace_id, user) is True
    await audit.record_many_or_refuse(many, [(kind, {})], workspace_id, user)
    assert [d.event for d in one.stored] == [kind]
    assert [d.event for d in many.stored] == [kind]


async def test_both_writers_refuse_a_kind_nobody_declared():
    user = User(id=str(RecordId()), sub="someone@example.org")
    with pytest.raises(AssertionError):
        await audit.record(_Repo(), "made_up_kind", RecordId(), user)
    with pytest.raises(AssertionError):
        await audit.record_many_or_refuse(
            _Repo(), [("made_up_kind", {})], RecordId(), user
        )
