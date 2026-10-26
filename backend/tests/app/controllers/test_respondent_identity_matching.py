"""The respondent identity end to end: an anonymous response stores the keyed
(v2) identity; "my submissions", the deletion-request list and the deletion
request itself match on it; a stored legacy MD5 is refused until the one pass
(backend.identity_rekey) has converted it, and works afterwards without the
address ever being stored."""

import hashlib
import hmac

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from backend import identity_rekey
from backend.app.container import container
from backend.app.utils import respondent_identity as identity
from backend.app.utils.hash import hash_string
from tests.app.controllers.data import testUser1, testUser2
from tests.app.controllers.test_respondent_deletion_requests import (  # noqa: F401
    _cookies,
    _listed,
    _submit,
    _url,
)
from tests.app.controllers.test_responses_per_workspace import _no_auth_service  # noqa: F401
from tests.app.response_helpers import deletion_request_of


async def _set_identity(table: str, response_id: str, value: str) -> None:
    """Put ``value`` in the stored identity, as a 4.0 database would hold it."""
    column = "response_id"
    async with container.pg_engine().begin() as conn:
        done = await conn.execute(
            text(
                f"UPDATE app.{table} SET doc = jsonb_set(doc, '{{anonymous_identity}}', "
                f"to_jsonb(CAST(:v AS text))) WHERE {column} = :r"
            ),
            {"v": value, "r": response_id},
        )
        assert done.rowcount == 1


async def _rekey() -> None:
    report = await identity_rekey.rekey_identities(
        container.pg_engine(), identity.configured_key()
    )
    assert report.done, report.to_dict()


async def test_a_new_anonymous_response_stores_the_keyed_identity(workspace, published_form):
    response = await _submit(workspace, published_form, testUser1, anonymize=True)
    stored = await container.form_response_repo().get_response(response.response_id)

    md5_hex = hashlib.md5(testUser1.sub.encode()).hexdigest()
    expected = "v2:" + hmac.new(
        identity.configured_key(), md5_hex.encode(), hashlib.sha256
    ).hexdigest()
    assert stored.anonymous_identity == expected
    assert stored.anonymous_identity != hash_string(testUser1.sub)
    # at rest the address is nowhere in the response
    assert testUser1.sub not in repr(stored.model_dump())


async def test_a_deletion_request_carries_the_keyed_identity_and_is_listed(
    client: AsyncClient, workspace, published_form
):
    response = await _submit(workspace, published_form, testUser1, anonymize=True)
    filed = await client.delete(
        f"{_url(workspace)}/submissions/{response.response_id}", cookies=_cookies(testUser1)
    )
    assert filed.status_code == 200, filed.text

    request = await deletion_request_of(
        workspace.id, published_form.form_id, str(response.response_id)
    )
    assert request.anonymous_identity == identity.identity_of(testUser1.sub)
    assert await _listed(client, workspace, testUser1) == [str(response.response_id)]
    assert await _listed(client, workspace, testUser2) == []


async def test_legacy_values_are_refused_until_the_pass_then_everything_matches(
    client: AsyncClient, workspace, published_form
):
    response = await _submit(workspace, published_form, testUser1, anonymize=True)
    response_id = str(response.response_id)
    legacy = hash_string(testUser1.sub)

    # a database as 4.0 left it: the response holds the unsalted MD5
    await _set_identity("form_responses", response_id, legacy)
    refused = await client.delete(
        f"{_url(workspace)}/submissions/{response_id}", cookies=_cookies(testUser1)
    )
    assert refused.status_code in (403, 404), refused.text  # no MD5 fallback
    assert await deletion_request_of(workspace.id, published_form.form_id, response_id) is None

    # the one pass converts it, with no address in sight
    await _rekey()
    stored = await container.form_response_repo().get_response(response.response_id)
    assert stored.anonymous_identity == identity.identity_of(testUser1.sub)
    filed = await client.delete(
        f"{_url(workspace)}/submissions/{response_id}", cookies=_cookies(testUser1)
    )
    assert filed.status_code == 200, filed.text
    assert await _listed(client, workspace, testUser1) == [response_id]

    # the same for a request that was filed on 4.0 (its copy holds the MD5)
    await _set_identity("responses_deletion_requests", response_id, legacy)
    assert await _listed(client, workspace, testUser1) == []  # refused, not matched by MD5
    await _rekey()
    assert await _listed(client, workspace, testUser1) == [response_id]
    assert await _listed(client, workspace, testUser2) == []


async def test_another_respondent_never_matches_a_converted_identity(
    client: AsyncClient, workspace, published_form
):
    response = await _submit(workspace, published_form, testUser1, anonymize=True)
    await _set_identity("form_responses", str(response.response_id), hash_string(testUser1.sub))
    await _rekey()
    refused = await client.delete(
        f"{_url(workspace)}/submissions/{response.response_id}", cookies=_cookies(testUser2)
    )
    assert refused.status_code in (403, 404), refused.text
