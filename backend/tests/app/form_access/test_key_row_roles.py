"""``row_role_for``: the role a key's row for a form is written with, by the key's
role. The key matrix seeds its rows from its own table, so this is where the
product's mapping is pinned, as a function and as the routes write it.
Everything here is synthetic."""

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.schemas.form_access_grant import (
    ROLE_EDITOR,
    ROLE_REVIEWER,
    ROLE_VIEWER,
)
from backend.app.services.api_key_roles.model import row_ceiling
from backend.app.services.api_key_roles.validation import row_role_for
from tests.app.form_access.test_key_roles import roles_on  # noqa: F401
from tests.app.form_access.test_key_routes import (
    create,
    forms,  # noqa: F401
    ids,
    patch,
)

pytestmark = pytest.mark.asyncio

EXPECTED = {
    None: ROLE_EDITOR,  # as its creator: an Editor row, which the creator narrows
    "EDITOR": ROLE_EDITOR,
    "REVIEWER": ROLE_REVIEWER,
    "VIEWER": ROLE_VIEWER,
    # no grant carries the privacy programme: a listed Privacy officer reads forms
    "PRIVACY_OFFICER": ROLE_VIEWER,
}


@pytest.mark.parametrize("role", list(EXPECTED), ids=lambda r: str(r))
def test_row_role_for_each_key_role(role):
    assert row_role_for(role) == EXPECTED[role]


def test_a_role_this_code_does_not_know_gets_the_least_a_row_can_give():
    for role in ("DEMIGOD", "", "OWNER", "ADMIN"):
        assert row_role_for(role) == ROLE_VIEWER, role


def test_no_row_ever_carries_what_a_grant_never_holds():
    for role in EXPECTED.values():
        for scopes in ((), ("responses:read",), ("forms:write", "responses:read")):
            held = row_ceiling(role, scopes)
            assert Permission.FORM_DELETE not in held, role
            assert Permission.PRIVACY_MANAGE not in held, role


async def test_the_routes_write_each_rows_role_from_the_keys_role(
    client: AsyncClient, workspace, forms, roles_on  # noqa: F811
):
    """Create and edit store the rows with ``row_role_for`` of the key's role: an
    edit that changes only the role rewrites the rows to the new role's."""
    for role, row_role in EXPECTED.items():
        body = {"formScope": "listed", "formIds": ids(forms)[:2]}
        if role is not None:
            body["role"] = role
        made = (await create(client, workspace, **body)).json()
        rows = await container.form_access_grant_repo().for_key(workspace.id, made["id"])
        assert {r.role for r in rows} == {row_role}, role
        assert len(rows) == 2
    key = (await create(client, workspace, role="EDITOR", formScope="listed", formIds=ids(forms)[:1])).json()
    assert (await patch(client, workspace, key["id"], role="REVIEWER")).status_code == 200
    rows = await container.form_access_grant_repo().for_key(workspace.id, key["id"])
    assert {r.role for r in rows} == {ROLE_REVIEWER}
