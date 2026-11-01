"""The drawn signature's image is encrypted at rest and served only by an
authorised route (services/signatures.py, ``FormResponseService.signature_image``):
a ciphertext in the store, bound to workspace, form, response, question and
file; the same 404 for everything that is not there or not the caller's;
the headers of an image that is never cached, sniffed or run."""

import json

import pytest

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
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
    if document.dataOwnerIdentifier != testUser2.sub and not document.anonymous_identity:
        pytest.skip("the form does not attribute submissions to the signed-in user")
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
