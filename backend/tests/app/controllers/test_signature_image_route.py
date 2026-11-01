"""The drawn signature's image is encrypted at rest and served only by an
authorised route (services/signatures.py, ``FormResponseService.signature_image``):
a ciphertext in the store, bound to workspace, form, response, question and
file; the same 404 for everything that is not there or not the caller's;
the headers of an image that is never cached, sniffed or run."""

import json

import pytest
from botocore.exceptions import ConnectTimeoutError, EndpointConnectionError

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services import signatures
from common.models.user import User
from common.ids import RecordId
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser1, testUser2
from tests.app.controllers.test_signature_question_routes import (  # noqa: F401
    API,
    FakeStore,
    _answers,
    _drawn_response,
    _png,
    _response_id,
    _submit,
    _switch,
    _url,
    signed_form,
    store,
)

HEADERS = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "content-type": "image/png",
}


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def _route(workspace, response_id, field_id="sig"):
    return f"{API}/workspaces/{workspace.id}/submissions/{response_id}/signatures/{field_id}"


def _key(workspace, form_id, response_id, file_id="img-1"):
    return f"private/{workspace.id}/{form_id}/{response_id}/{file_id}"


async def _member(workspace, role):
    user = User(id=str(RecordId()), sub=f"sig-{role}-{RecordId()}@example.com")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(workspace_id=workspace.id, user_id=user.id, roles=[role])
    )
    return user


# --- at rest ---------------------------------------------------------------------------


def test_an_image_round_trips_through_the_keyset_and_the_stored_form_is_not_an_image():
    png = _png()
    sealed = signatures.seal_image("w", "f", "r", "q", "i", png)
    assert sealed.startswith(b"v1:") and png[8:40] not in sealed
    assert signatures.open_image("w", "f", "r", "q", "i", sealed) == png


@pytest.mark.parametrize(
    "where",
    [
        ("other-w", "f", "r", "q", "i"),
        ("w", "other-f", "r", "q", "i"),
        ("w", "f", "other-r", "q", "i"),
        ("w", "f", "r", "other-q", "i"),
        ("w", "f", "r", "q", "other-i"),
    ],
)
def test_an_image_only_opens_where_it_was_sealed(where):
    sealed = signatures.seal_image("w", "f", "r", "q", "i", _png())
    assert signatures.open_image(*where, sealed) is None


def test_the_binding_cannot_be_forged_by_the_choice_of_ids():
    # ids that put the separators of the context in different places
    a = signatures.image_context("r", "a,b", "c")
    b = signatures.image_context("r", "a", "b,c")
    assert a != b
    sealed = signatures.seal_image("w", "f", "r", 'a","b', "c", _png())
    assert signatures.open_image("w", "f", "r", "a", 'b","c', sealed) is None


def test_what_is_not_ciphertext_or_not_a_png_is_never_opened():
    png = _png()
    # an image stored before encryption existed is never served as it is
    assert signatures.open_image("w", "f", "r", "q", "i", png) is None
    assert signatures.open_image("w", "f", "r", "q", "i", b"") is None
    assert signatures.open_image("w", "f", "r", "q", "i", b"v1:garbage") is None
    # ciphertext of something that is not a PNG, or of an oversized one
    not_png = signatures.seal_image("w", "f", "r", "q", "i", b"<svg onload=alert(1)>")
    assert signatures.open_image("w", "f", "r", "q", "i", not_png) is None
    big = signatures.seal_image("w", "f", "r", "q", "i", signatures.PNG_SIGNATURE + b"0" * signatures.STORED_MAX_BYTES)
    assert signatures.open_image("w", "f", "r", "q", "i", big) is None


def test_the_ciphertext_names_its_key_so_rotation_finds_it():
    from common.services.crypto_service import crypto_service
    from common.services.keyset import ciphertext_key_id

    sealed = signatures.seal_image("w", "f", "r", "q", "i", _png())
    assert ciphertext_key_id(sealed) == crypto_service.primary_key_id


# --- the route ---------------------------------------------------------------------------


async def test_staff_get_the_decrypted_png_with_the_headers_of_a_private_image(
    client, workspace, signed_form, store, test_user_cookies
):
    form_id = signed_form.form_id
    response_id = await _drawn_response(client, workspace, form_id)
    sealed = store.objects[_key(workspace, form_id, response_id)]
    assert not sealed.startswith(b"\x89PNG")
    got = await client.get(_route(workspace, response_id), cookies=test_user_cookies)
    assert got.status_code == 200, got.text
    assert got.content.startswith(b"\x89PNG") and got.content != sealed
    for name, value in HEADERS.items():
        assert got.headers[name] == value, name
    assert got.headers["content-disposition"].startswith("inline")
    assert "sandbox" in got.headers["content-security-policy"]
    # and nothing about it is a link to the store
    one = await client.get(f"{API}/workspaces/{workspace.id}/submissions/{response_id}", cookies=test_user_cookies)
    assert "files.example" not in one.text and store.link_headers == {}


async def test_a_signed_out_caller_gets_nothing(client, workspace, signed_form, store):
    response_id = await _drawn_response(client, workspace, signed_form.form_id)
    got = await client.get(_route(workspace, response_id))
    assert got.status_code in (401, 403)
    assert not got.content.startswith(b"\x89PNG")


@pytest.mark.parametrize(
    "role,allowed",
    [
        (WorkspaceRoles.ADMIN, True),
        (WorkspaceRoles.EDITOR, True),
        (WorkspaceRoles.REVIEWER, True),
        (WorkspaceRoles.VIEWER, True),
        (WorkspaceRoles.PRIVACY_OFFICER, False),
    ],
)
async def test_the_response_read_permission_decides_for_members(
    client, workspace, signed_form, store, role, allowed
):
    response_id = await _drawn_response(client, workspace, signed_form.form_id)
    user = await _member(workspace, role)
    got = await client.get(_route(workspace, response_id), cookies=_cookies(user))
    if allowed:
        assert got.status_code == 200 and got.content.startswith(b"\x89PNG")
    else:
        # not a 403: the route does not say the response exists
        assert got.status_code == 404 and not got.content.startswith(b"\x89PNG")


async def test_a_member_without_a_role_that_reads_nothing_and_a_non_member_get_the_same_404(
    client, workspace, signed_form, store, test_user_cookies
):
    response_id = await _drawn_response(client, workspace, signed_form.form_id)
    missing = await client.get(_route(workspace, "0" * 24), cookies=_cookies(testUser1))
    outsider = await client.get(_route(workspace, response_id), cookies=_cookies(testUser1))
    no_such_field = await client.get(_route(workspace, response_id, "name"), cookies=test_user_cookies)
    no_such_question = await client.get(_route(workspace, response_id, "nope"), cookies=test_user_cookies)
    assert {r.status_code for r in (missing, outsider, no_such_field, no_such_question)} == {404}
    assert missing.text == outsider.text == no_such_field.text == no_such_question.text


async def test_another_workspace_cannot_read_it_even_as_staff(
    client, workspace, workspace_1, signed_form, store, test_user_cookies_1
):
    response_id = await _drawn_response(client, workspace, signed_form.form_id)
    # testUser1 owns workspace_1; the response is collected in `workspace`
    got = await client.get(_route(workspace_1, response_id), cookies=test_user_cookies_1)
    assert got.status_code == 404
    got = await client.get(_route(workspace, response_id), cookies=test_user_cookies_1)
    assert got.status_code == 404


async def test_a_ciphertext_copied_to_another_response_or_question_does_not_serve(
    client, workspace, signed_form, store, test_user_cookies
):
    form_id = signed_form.form_id
    first = await _drawn_response(client, workspace, form_id)
    second = await _drawn_response(client, workspace, form_id)
    assert (await client.get(_route(workspace, second), cookies=test_user_cookies)).status_code == 200
    # someone with storage access copies the first response's object over the second's
    store.objects[_key(workspace, form_id, second)] = store.objects[_key(workspace, form_id, first)]
    swapped = await client.get(_route(workspace, second), cookies=test_user_cookies)
    assert swapped.status_code == 404 and not swapped.content.startswith(b"\x89PNG")
    # and the first is still its own
    assert (await client.get(_route(workspace, first), cookies=test_user_cookies)).status_code == 200


async def test_a_plain_png_in_the_store_is_refused_not_served(
    client, workspace, signed_form, store, test_user_cookies
):
    form_id = signed_form.form_id
    response_id = await _drawn_response(client, workspace, form_id)
    store.objects[_key(workspace, form_id, response_id)] = _png()
    got = await client.get(_route(workspace, response_id), cookies=test_user_cookies)
    assert got.status_code == 404 and not got.content.startswith(b"\x89PNG")


async def test_a_missing_object_and_a_typed_signature_are_404(
    client, workspace, signed_form, store, test_user_cookies
):
    form_id = signed_form.form_id
    response_id = await _drawn_response(client, workspace, form_id)
    del store.objects[_key(workspace, form_id, response_id)]
    assert (await client.get(_route(workspace, response_id), cookies=test_user_cookies)).status_code == 404
    typed = await _submit(client, workspace, form_id, _answers(method="typed", name="Ada"))
    assert typed.status_code == 200
    typed_id = await _response_id(workspace, form_id)
    assert (await client.get(_route(workspace, typed_id), cookies=test_user_cookies)).status_code == 404


async def test_the_respondent_reads_their_own_signature_and_nobody_elses(
    client, workspace, signed_form, store
):
    form_id = signed_form.form_id
    submitted = await _submit(
        client, workspace, form_id, _answers(method="drawn", file_id="img-1"),
        files=[("sig", "img-1", _png())], cookies=_cookies(testUser2),
    )
    assert submitted.status_code == 200, submitted.text
    response_id = await _response_id(workspace, form_id)
    document = await container.form_response_repo().get_response(response_id)
    # the submission is attributed to its signed-in respondent (never a skip)
    assert document.dataOwnerIdentifier == testUser2.sub
    own = await client.get(_route(workspace, response_id), cookies=_cookies(testUser2))
    assert own.status_code == 200 and own.content.startswith(b"\x89PNG")
    other = await client.get(_route(workspace, response_id), cookies=_cookies(testUser1))
    assert other.status_code == 404


async def test_the_route_is_rate_limited_per_user(
    client, workspace, signed_form, store, test_user_cookies, monkeypatch
):
    monkeypatch.setattr(signatures, "READS_PER_MINUTE", 2)
    response_id = await _drawn_response(client, workspace, signed_form.form_id)
    codes = [
        (await client.get(_route(workspace, response_id), cookies=test_user_cookies)).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]


# --- more ways to be (not) allowed -------------------------------------------------------


async def test_a_form_shared_into_another_workspace_does_not_share_the_image(
    client, workspace, workspace_1, signed_form, store, test_user_cookies, test_user_cookies_1
):
    form_id = signed_form.form_id
    response_id = await _drawn_response(client, workspace, form_id)
    # the same form is linked to workspace B too (a provider form imported twice)
    await container.workspace_form_repo().save(
        WorkspaceFormDocument(workspace_id=workspace_1.id, form_id=form_id, user_id=testUser1.id)
    )
    # B's owner reads nothing of A's response, however the path is spelled
    for ws in (workspace_1, workspace):
        got = await client.get(_route(ws, response_id), cookies=test_user_cookies_1)
        assert got.status_code == 404, ws.id
        assert not got.content.startswith(b"\x89PNG")
    # A's copy is read in A, and only in A
    assert (await client.get(_route(workspace, response_id), cookies=test_user_cookies)).status_code == 200
    assert (await client.get(_route(workspace_1, response_id), cookies=test_user_cookies)).status_code == 404


async def test_an_anonymous_response_is_readable_by_its_respondent_only(
    client, workspace, signed_form, store, test_user_cookies
):
    form_id = signed_form.form_id
    data = {
        "response": json.dumps({"anonymize": True, "answers": _answers(method="drawn", file_id="img-1")}),
        "file_field_ids": ["sig"],
        "file_ids": ["img-1"],
    }
    submitted = await client.post(
        f"{_url(workspace, form_id)}/response",
        data=data,
        files=[("files", ("signature.png", _png(), "image/png"))],
        cookies=_cookies(testUser2),
    )
    assert submitted.status_code == 200, submitted.text
    response_id = await _response_id(workspace, form_id)
    document = await container.form_response_repo().get_response(response_id)
    # no identity is stored, only the one-way hash the respondent finds it by
    assert document.dataOwnerIdentifier is None and document.anonymous_identity
    own = await client.get(_route(workspace, response_id), cookies=_cookies(testUser2))
    assert own.status_code == 200 and own.content.startswith(b"\x89PNG")
    assert (await client.get(_route(workspace, response_id), cookies=_cookies(testUser1))).status_code == 404
    # staff with response.read still read it, as they read the response
    assert (await client.get(_route(workspace, response_id), cookies=test_user_cookies)).status_code == 200


async def test_a_response_with_a_deletion_request_is_readable_until_it_is_deleted(
    client, workspace, signed_form, store, test_user_cookies
):
    form_id = signed_form.form_id
    response_id = await _drawn_response(client, workspace, form_id)
    responses = container.form_response_repo()
    await responses.add_deletion_request(await responses.get_response(response_id), response_id)
    # staff decide on the request with the response in front of them
    assert (await client.get(_route(workspace, response_id), cookies=test_user_cookies)).status_code == 200
    deleted = await client.delete(f"{_url(workspace, form_id)}/response/{response_id}", cookies=test_user_cookies)
    assert deleted.status_code == 200, deleted.text
    assert store.objects == {}
    gone = await client.get(_route(workspace, response_id), cookies=test_user_cookies)
    assert gone.status_code == 404


def _rotated(monkeypatch, drop_old=False):
    """The cipher after a key was added as the primary (the old key stays),
    or with only the new key (``drop_old``)."""
    from common.services.crypto_service import crypto_service
    from common.services.keyset import CryptoService, add_primary_key, encode_keyset, only_primary

    before = crypto_service.load()
    keyset = add_primary_key(before.keyset)
    if drop_old:
        keyset = only_primary(keyset)
    after = CryptoService(encode_keyset(keyset))
    assert after.primary_key_id != before.primary_key_id
    monkeypatch.setattr(crypto_service, "_service", after)
    return before.primary_key_id, after.primary_key_id


async def test_an_image_sealed_under_an_older_key_is_still_read_after_a_rotation(
    client, workspace, signed_form, store, test_user_cookies, monkeypatch
):
    from common.services.keyset import ciphertext_key_id

    form_id = signed_form.form_id
    response_id = await _drawn_response(client, workspace, form_id)
    stored = store.objects[_key(workspace, form_id, response_id)]
    old_key, new_key = _rotated(monkeypatch)
    assert ciphertext_key_id(stored) == old_key
    got = await client.get(_route(workspace, response_id), cookies=test_user_cookies)
    assert got.status_code == 200 and got.content.startswith(b"\x89PNG")
    # a new drawing is sealed under the new primary
    fresh = await _drawn_response(client, workspace, form_id)
    assert ciphertext_key_id(store.objects[_key(workspace, form_id, fresh)]) == new_key
    # once the old key is dropped the old image cannot be read (the documented limit)
    _rotated(monkeypatch, drop_old=True)
    gone = await client.get(_route(workspace, response_id), cookies=test_user_cookies)
    assert gone.status_code == 404


async def test_the_not_found_and_rate_limited_answers_are_never_cached(
    client, workspace, signed_form, store, test_user_cookies, monkeypatch
):
    response_id = await _drawn_response(client, workspace, signed_form.form_id)
    missing = await client.get(_route(workspace, "0" * 24), cookies=test_user_cookies)
    assert missing.status_code == 404 and missing.headers["cache-control"] == "no-store"
    outsider = await client.get(_route(workspace, response_id), cookies=_cookies(testUser1))
    assert outsider.status_code == 404 and outsider.headers["cache-control"] == "no-store"
    monkeypatch.setattr(signatures, "READS_PER_MINUTE", 1)
    await client.get(_route(workspace, response_id), cookies=test_user_cookies)
    limited = await client.get(_route(workspace, response_id), cookies=test_user_cookies)
    assert limited.status_code == 429
    assert limited.headers["cache-control"] == "no-store" and limited.headers["retry-after"]


@pytest.mark.parametrize(
    "error",
    [EndpointConnectionError(endpoint_url="http://store.invalid"), ConnectTimeoutError(endpoint_url="http://store.invalid"), ConnectionResetError("reset")],
)
async def test_an_unreachable_store_is_the_same_404(
    client, workspace, signed_form, store, test_user_cookies, monkeypatch, error
):
    response_id = await _drawn_response(client, workspace, signed_form.form_id)

    def down(key, max_bytes, bucket=None):
        raise error

    monkeypatch.setattr(store, "read_object", down)
    got = await client.get(_route(workspace, response_id), cookies=test_user_cookies)
    missing = await client.get(_route(workspace, "0" * 24), cookies=test_user_cookies)
    assert got.status_code == 404 and got.text == missing.text
    assert got.headers["cache-control"] == "no-store"
