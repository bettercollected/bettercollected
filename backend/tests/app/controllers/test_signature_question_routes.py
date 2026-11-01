"""The signature question end to end (SIGNATURE_QUESTION_ENABLED,
services/signatures.py): a respondent signs by drawing or typing, the answer is
stored (the drawn image as a private object next to the response's files),
staff read it back, and every way a response goes takes the image with it.
Also the switch on every write path, like the newer question types'.

Storage is an in-memory fake and the document sandbox is its real re-encoder."""

import io
import json

import pytest
from httpx import AsyncClient
from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo

from backend.app.container import container
from backend.app.services import signatures
from backend.app.services.pdf_import.logo_image import reencode_image
from backend.config import settings
from common.models.standard_form import StandardForm
from tests.app.controllers.data import testUser
from tests.app.controllers.test_new_question_types_routes import (
    API,
    _body,
    _short,
)
from tests.app.controllers.test_mcp_server import (
    _call_tool,
    _make_key,
    _make_v2,
    _tool_text,
)
from tests.app.controllers.test_public_api import (
    BASE as PUBLIC,
    SPEC,
    _auth,
    _create,
    _is_error,
    _token,
)
from tests.app.controllers.test_workspace_form_submissions import (
    _allow_editing,
    _edit,
)

CODE = "signature_question_disabled"


def _switch(monkeypatch, on):
    monkeypatch.setattr(settings, "SIGNATURE_QUESTION_ENABLED", on)


def _sign(field_id="sig", **properties):
    return {"id": field_id, "type": "signature", "title": "Your signature", "properties": properties}


def _png(secret=None) -> bytes:
    image = Image.new("RGBA", (600, 200), (0, 0, 0, 0))
    ImageDraw.Draw(image).line((20, 150, 200, 40, 380, 160, 560, 60), fill=(20, 20, 20, 255), width=5)
    info = PngInfo()
    if secret:
        info.add_text("Comment", secret)
    out = io.BytesIO()
    image.save(out, format="PNG", pnginfo=info)
    return out.getvalue()


class FakeStore:
    """The object store: keys to bytes."""

    def __init__(self):
        self.objects = {}

    async def upload_file_to_s3(self, file=None, key=None, previous_image="", bucket=None, private=False, folder_name="public"):
        self.objects[f"{folder_name}/{key}"] = file.read()

    def check_if_key_exists(self, key, bucket=None):
        return any(k.startswith(key) for k in self.objects)

    def generate_presigned_url(self, key, bucket=None):
        return f"https://files.example/{key}?signed"

    def delete_file_from_s3(self, key, bucket=None):
        self.objects.pop(key, None)

    def delete_folder_from_s3(self, prefix, bucket=None, keep=""):
        for key in [k for k in self.objects if k.startswith(prefix) and not (keep and keep in k)]:
            del self.objects[key]


@pytest.fixture()
def store(monkeypatch):
    fake = FakeStore()
    monkeypatch.setattr(container.workspace_form_service(), "_aws_service", fake)
    monkeypatch.setattr(container.form_response_service(), "_aws_service", fake)

    async def process(data):
        return reencode_image(data, signatures.MAX_PIXELS)

    monkeypatch.setattr(signatures, "_process_in_sandbox", process)
    return fake


@pytest.fixture()
async def signed_form(workspace, monkeypatch):
    _switch(monkeypatch, True)
    form = StandardForm(
        title="Agreement",
        builder_version="v2",
        fields=[
            {
                "id": "p1",
                "index": 0,
                "type": "slide",
                "properties": {
                    "fields": [
                        {"id": "name", "index": 0, "type": "short_text", "title": "Name"},
                        {
                            "id": "sig",
                            "index": 1,
                            "type": "signature",
                            "title": "Sign",
                            "validations": {"required": True},
                        },
                    ]
                },
            }
        ],
    )
    created = await container.workspace_form_service().create_form(workspace.id, form, testUser)
    return await container.workspace_form_service().publish_form(workspace.id, created.form_id, testUser)


def _url(workspace, form_id):
    return f"{API}/workspaces/{workspace.id}/forms/{form_id}"


def _answers(**sig):
    return {"name": {"type": "text", "text": "Ada"}, "sig": {"type": "signature", "signature": sig}}


async def _submit(client, workspace, form_id, answers, files=None, cookies=None):
    data = {"response": json.dumps({"answers": answers})}
    if files:
        data["file_field_ids"] = [f for f, _, _ in files]
        data["file_ids"] = [i for _, i, _ in files]
    return await client.post(
        f"{_url(workspace, form_id)}/response",
        data=data,
        files=[("files", ("signature.png", blob, "image/png")) for _, _, blob in files] if files else None,
        cookies=cookies,
    )


async def _stored(workspace, form_id, response_id):
    from common.services.crypto_service import crypto_service

    document = await container.form_response_repo().get_response(response_id)
    return json.loads(
        crypto_service.decrypt(workspace_id=workspace.id, form_id=form_id, data=document.answers)
    )


async def _response_id(workspace, form_id):
    page = await container.form_response_repo().list_by_form_id(
        await container.form_response_service().scope(workspace.id, [str(form_id)])
    )
    return max(page, key=lambda r: r.created_at).response_id


# --- answering ---------------------------------------------------------------------


async def test_a_typed_signature_is_stored_with_a_server_stamp(
    client: AsyncClient, workspace, signed_form, store
):
    response = await _submit(client, workspace, signed_form.form_id, _answers(method="typed", name="Ada Lovelace", signed_at="1999-01-01T00:00:00Z"))
    assert response.status_code == 200, response.text
    stored = await _stored(workspace, signed_form.form_id, await _response_id(workspace, signed_form.form_id))
    signature = stored["sig"]["signature"]
    assert signature["method"] == "typed" and signature["name"] == "Ada Lovelace"
    assert signature["signed_at"].endswith("Z") and not signature["signed_at"].startswith("1999")
    assert store.objects == {}


async def test_a_drawn_signature_stores_a_clean_image_and_staff_get_a_link(
    client: AsyncClient, workspace, signed_form, store, test_user_cookies
):
    form_id = signed_form.form_id
    response = await _submit(
        client, workspace, form_id, _answers(method="drawn", file_id="img-1"),
        files=[("sig", "img-1", _png(secret="my secret note"))],
    )
    assert response.status_code == 200, response.text
    response_id = await _response_id(workspace, form_id)
    key = f"private/{workspace.id}/{form_id}/{response_id}/img-1"
    assert list(store.objects) == [key]
    assert store.objects[key].startswith(b"\x89PNG") and b"my secret note" not in store.objects[key]
    stored = await _stored(workspace, form_id, response_id)
    assert stored["sig"]["signature"]["file_id"] == "img-1"
    assert "url" not in stored["sig"]["signature"]
    one = await client.get(f"{API}/workspaces/{workspace.id}/submissions/{response_id}", cookies=test_user_cookies)
    assert one.status_code == 200, one.text
    signature = one.json()["response"]["answers"]["sig"]["signature"]
    assert signature["method"] == "drawn" and signature["file_id"] == "img-1"
    assert signature["url"] == f"https://files.example/{key}?signed"


async def test_a_bad_drawing_is_refused_with_nothing_stored(
    client: AsyncClient, workspace, signed_form, store
):
    form_id = signed_form.form_id
    for blob in (b"<svg onload=alert(1)/>", b"\x89PNG\r\n\x1a\n<script>1</script>" * 4, b"GIF89a" + b"0" * 50):
        response = await _submit(client, workspace, form_id, _answers(method="drawn", file_id="img-1"), files=[("sig", "img-1", blob)])
        assert response.status_code == 422, response.text
        assert response.json()["errors"] == [{"fieldId": "sig", "rule": "signature_image"}]
    # an id with no image at all
    response = await _submit(client, workspace, form_id, _answers(method="drawn", file_id="img-1"))
    assert response.status_code == 422 and response.json()["errors"][0]["rule"] == "signature_image"
    assert store.objects == {}
    assert await container.form_response_service().count_for_form(workspace.id, str(form_id)) == 0


async def test_a_signature_that_is_required_and_missing_is_refused(
    client: AsyncClient, workspace, signed_form, store
):
    response = await _submit(client, workspace, signed_form.form_id, {"name": {"type": "text", "text": "Ada"}})
    assert response.status_code == 422
    assert {"fieldId": "sig", "rule": "required"} in response.json()["errors"]


async def test_an_unsupported_shape_is_refused(client: AsyncClient, workspace, signed_form, store):
    for signature in (
        {"method": "typed", "name": ""},
        {"method": "typed", "name": " padded "},
        {"method": "typed", "name": "x" * 101},
        {"method": "typed", "name": "Zero​width"},
        {"method": "scribble", "name": "x"},
    ):
        response = await _submit(client, workspace, signed_form.form_id, _answers(**signature))
        assert response.status_code == 422, (signature, response.text)


async def test_a_drawn_image_cannot_ride_on_a_file_upload_or_another_response(
    client: AsyncClient, workspace, signed_form, store
):
    # a part sent for the name question is not the signature's image
    response = await _submit(
        client, workspace, signed_form.form_id, _answers(method="drawn", file_id="img-1"),
        files=[("name", "img-1", _png())],
    )
    assert response.status_code == 422
    assert store.objects == {}


async def test_the_sandbox_being_down_is_a_503_and_typing_still_works(
    client: AsyncClient, workspace, signed_form, store, monkeypatch
):
    from backend.app.services.pdf_import.sandbox import SandboxUnavailable

    async def down(data):
        raise SandboxUnavailable("gone")

    monkeypatch.setattr(signatures, "_process_in_sandbox", down)
    drawn = await _submit(client, workspace, signed_form.form_id, _answers(method="drawn", file_id="img-1"), files=[("sig", "img-1", _png())])
    assert drawn.status_code == 503, drawn.text
    typed = await _submit(client, workspace, signed_form.form_id, _answers(method="typed", name="Ada"))
    assert typed.status_code == 200, typed.text


# --- answering with the switch off: stored questions keep working -----------------------


async def test_the_switch_never_governs_answering(client: AsyncClient, workspace, signed_form, store, monkeypatch):
    _switch(monkeypatch, False)
    response = await _submit(client, workspace, signed_form.form_id, _answers(method="drawn", file_id="img-1"), files=[("sig", "img-1", _png())])
    assert response.status_code == 200, response.text
    assert len(store.objects) == 1


# --- the image goes with the response, on every path ------------------------------------


async def _drawn_response(client, workspace, form_id):
    response = await _submit(client, workspace, form_id, _answers(method="drawn", file_id="img-1"), files=[("sig", "img-1", _png())])
    assert response.status_code == 200, response.text
    return await _response_id(workspace, form_id)


async def test_staff_deleting_the_response_deletes_the_image(client, workspace, signed_form, store, test_user_cookies):
    form_id = signed_form.form_id
    response_id = await _drawn_response(client, workspace, form_id)
    assert len(store.objects) == 1
    deleted = await client.delete(f"{_url(workspace, form_id)}/response/{response_id}", cookies=test_user_cookies)
    assert deleted.status_code == 200, deleted.text
    assert store.objects == {}


async def test_the_retention_job_deleting_the_response_deletes_the_image(client, workspace, signed_form, store):
    form_id = signed_form.form_id
    response_id = await _drawn_response(client, workspace, form_id)
    other = await _drawn_response(client, workspace, form_id)  # a second response, kept
    assert len(store.objects) == 2
    await container.form_response_service().delete_response(response_id=response_id)
    assert list(store.objects) == [f"private/{workspace.id}/{form_id}/{other}/img-1"] or len(store.objects) == 1
    assert not any(response_id in key for key in store.objects)


async def test_unlinking_a_form_from_a_workspace_deletes_its_responses_files_but_not_an_import_original(
    client, workspace, signed_form, store
):
    form_id = signed_form.form_id
    await _drawn_response(client, workspace, form_id)
    original = f"private/{workspace.id}/{form_id}/imports/imp-1/source.pdf"
    store.objects[original] = b"%PDF"
    await container.form_response_service().delete_workspace_form_responses(workspace.id, str(form_id))
    assert list(store.objects) == [original]


async def test_deleting_the_form_deletes_the_image(client, workspace, signed_form, store, test_user_cookies):
    form_id = signed_form.form_id
    await _drawn_response(client, workspace, form_id)
    deleted = await client.delete(_url(workspace, form_id), cookies=test_user_cookies)
    assert deleted.status_code == 200, deleted.text
    assert store.objects == {}


# --- the respondent's edit ----------------------------------------------------------------


async def test_an_edit_that_redraws_or_retypes_deletes_the_replaced_image(
    client, workspace, signed_form, store, test_user_cookies
):
    form_id = signed_form.form_id
    common_url = f"{API}/workspaces/{workspace.id}"
    await _allow_editing(client, common_url, form_id, test_user_cookies)
    submitted = await _submit(client, workspace, form_id, _answers(method="drawn", file_id="img-1"), files=[("sig", "img-1", _png())], cookies=test_user_cookies)
    assert submitted.status_code == 200, submitted.text
    response_id = await _response_id(workspace, form_id)
    folder = f"private/{workspace.id}/{form_id}/{response_id}"
    # the same answer sent back (what the edit page does) changes nothing
    again = await client.patch(
        f"{common_url}/forms/{form_id}/response/{response_id}",
        data={"response": json.dumps({"answers": {"sig": {"type": "signature", "signature": {"method": "drawn", "file_id": "img-1", "url": "https://signed.test/x"}}}})},
        cookies=test_user_cookies,
    )
    assert again.status_code == 200, again.text
    assert list(store.objects) == [f"{folder}/img-1"]
    # redraw: the old image goes after the new one is stored
    redrawn = await client.patch(
        f"{common_url}/forms/{form_id}/response/{response_id}",
        data={
            "response": json.dumps({"answers": {"sig": {"type": "signature", "signature": {"method": "drawn", "file_id": "img-2"}}}}),
            "file_field_ids": ["sig"],
            "file_ids": ["img-2"],
        },
        files=[("files", ("s.png", _png(), "image/png"))],
        cookies=test_user_cookies,
    )
    assert redrawn.status_code == 200, redrawn.text
    assert list(store.objects) == [f"{folder}/img-2"]
    # retype: the image goes, the name is stored
    retyped = await _edit(client, common_url, form_id, response_id, {"sig": {"type": "signature", "signature": {"method": "typed", "name": "Ada Lovelace"}}}, test_user_cookies)
    assert retyped.status_code == 200, retyped.text
    assert store.objects == {}
    stored = await _stored(workspace, form_id, response_id)
    assert stored["sig"]["signature"]["name"] == "Ada Lovelace" and "file_id" not in stored["sig"]["signature"]
    # naming an image the response does not hold is refused
    forged = await _edit(client, common_url, form_id, response_id, {"sig": {"type": "signature", "signature": {"method": "drawn", "file_id": "someone-elses"}}}, test_user_cookies)
    assert forged.status_code == 422, forged.text


# --- the switch on every write path ---------------------------------------------------------


async def _save(client, workspace, form, cookies, fields):
    return await client.patch(
        f"{API}/workspaces/{workspace.id}/forms/{form.form_id}",
        cookies=cookies,
        data={"form_body": json.dumps(_body(fields))},
    )


async def test_the_builder_save_refuses_a_new_signature_question_while_off(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, monkeypatch
):
    _switch(monkeypatch, False)
    response = await _save(client, workspace, workspace_form, test_user_cookies, [_short(), _sign()])
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == CODE
    assert [(e["fieldId"], e["type"]) for e in body["errors"]] == [("sig", "signature")]
    assert "SIGNATURE_QUESTION_ENABLED" in body["message"]
    _switch(monkeypatch, True)
    assert (await _save(client, workspace, workspace_form, test_user_cookies, [_short(), _sign()])).status_code == 200


async def test_a_signature_question_a_form_has_keeps_saving_while_off(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, monkeypatch
):
    _switch(monkeypatch, True)
    fields = [_short(), _sign()]
    assert (await _save(client, workspace, workspace_form, test_user_cookies, fields)).status_code == 200
    _switch(monkeypatch, False)
    fields[1]["title"] = "Sign below"
    fields.append(_short("b"))
    fields.reverse()
    assert (await _save(client, workspace, workspace_form, test_user_cookies, fields)).status_code == 200
    # another question turned into a signature: refused
    turned = json.loads(json.dumps(fields))
    for field in turned:
        if field["id"] == "b":
            field["type"] = "signature"
    refused = await _save(client, workspace, workspace_form, test_user_cookies, turned)
    assert refused.status_code == 422 and refused.json()["code"] == CODE
    # a second signature question: refused
    more = json.loads(json.dumps(fields)) + [_sign("sig2")]
    refused = await _save(client, workspace, workspace_form, test_user_cookies, more)
    assert refused.status_code == 422 and refused.json()["code"] == CODE
    # one removed, or made an older type: allowed
    kept = [f for f in fields if f["id"] != "sig"]
    assert (await _save(client, workspace, workspace_form, test_user_cookies, kept)).status_code == 200


async def test_the_two_switches_are_independent(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, monkeypatch
):
    time_question = {"id": "t", "type": "time", "title": "Arrival"}
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", True)
    _switch(monkeypatch, False)
    assert (await _save(client, workspace, workspace_form, test_user_cookies, [time_question])).status_code == 200
    refused = await _save(client, workspace, workspace_form, test_user_cookies, [time_question, _sign()])
    assert refused.status_code == 422 and refused.json()["code"] == CODE
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", False)
    _switch(monkeypatch, True)
    refused = await _save(client, workspace, workspace_form, test_user_cookies, [{**time_question, "id": "t2"}, _sign()])
    assert refused.status_code == 422 and refused.json()["code"] == "question_type_disabled"
    assert (await _save(client, workspace, workspace_form, test_user_cookies, [_sign()])).status_code == 200


async def test_creating_a_form_follows_the_switch_and_a_copy_keeps_its_signature_question(
    workspace, monkeypatch
):
    from backend.app.controllers.workspace_forms import _parse_form_body

    service = container.workspace_form_service()

    def body():
        return _parse_form_body(json.dumps(_body([_short(), _sign()])))

    _switch(monkeypatch, False)
    with pytest.raises(Exception) as error:
        await service.create_form(workspace.id, body(), testUser)
    assert error.value.status_code == 422 and error.value.content["code"] == CODE
    _switch(monkeypatch, True)
    created = await service.create_form(workspace.id, body(), testUser)
    # a copy (a template's or a form's) keeps what its source has
    _switch(monkeypatch, False)
    copy = await service.create_form(workspace.id, body(), testUser, drop_unusable_settings=True)
    stored = await container.form_service().get_form_document_by_id(copy.form_id)
    assert [f.type.value for f in stored.fields[0].properties.fields] == ["short_text", "signature"]
    assert created.form_id != copy.form_id


async def test_a_template_follows_the_switch(
    client: AsyncClient, workspace, test_user_cookies, monkeypatch
):
    from tests.app.controllers.test_new_question_types_routes import _page

    template = {"title": "T", "fields": [_page([_short(), _sign()])]}
    url = f"{API}/workspaces/{workspace.id}/template"
    _switch(monkeypatch, False)
    response = await client.post(url, cookies=test_user_cookies, data={"template_body": json.dumps(template)})
    assert response.status_code == 422, response.text
    assert response.json()["code"] == CODE
    _switch(monkeypatch, True)
    response = await client.post(url, cookies=test_user_cookies, data={"template_body": json.dumps(template)})
    assert response.status_code != 422, response.text


SIGNATURE_SPEC = {
    **SPEC,
    "pages": [{"id": "page-1", "fields": [{"id": "sig", "type": "signature", "title": "Sign here"}]}],
}


async def test_the_spec_api_follows_the_switch(client: AsyncClient, workspace, monkeypatch):
    token = await _token(workspace.id)
    _switch(monkeypatch, False)
    refused = await client.post(f"{PUBLIC}/forms", json=SIGNATURE_SPEC, headers=_auth(token))
    body = _is_error(refused, 422, CODE)
    assert "SIGNATURE_QUESTION_ENABLED" in body["message"]
    validated = await client.post(f"{PUBLIC}/forms/validate", json=SIGNATURE_SPEC, headers=_auth(token))
    assert validated.status_code == 200, validated.text
    assert any("signature" in w["message"] for w in validated.json().get("warnings", []))
    _switch(monkeypatch, True)
    created = await client.post(f"{PUBLIC}/forms", json=SIGNATURE_SPEC, headers=_auth(token))
    assert created.status_code == 201, created.text
    # off again: the document read back can be saved again, a new signature
    # question in it is refused
    url = f"{PUBLIC}/forms/{created.json()['formId']}"
    _switch(monkeypatch, False)
    fetched = await client.get(url, headers=_auth(token))
    assert fetched.status_code == 200
    document = fetched.json()
    assert document["pages"][0]["fields"][0]["type"] == "signature"
    replaced = await client.put(
        url,
        json={**document, "title": "Renamed"},
        headers=_auth(token, **{"If-Match": fetched.headers["ETag"]}),
    )
    assert replaced.status_code == 200, replaced.text
    added = json.loads(json.dumps(replaced.json()))
    added["pages"][0]["fields"].append({"id": "sig2", "type": "signature", "title": "Again"})
    _is_error(
        await client.put(url, json=added, headers=_auth(token, **{"If-Match": replaced.headers["ETag"]})),
        422,
        CODE,
    )


async def test_the_public_api_ops_follow_the_switch(client: AsyncClient, workspace, monkeypatch):
    token = await _token(workspace.id)
    form_id = (await _create(client, token, SPEC)).json()["formId"]
    url = f"{PUBLIC}/forms/{form_id}/ops"
    add = [{"op": "add_field", "pageId": "page-1", "field": {"title": "Sign", "type": "signature"}}]
    _switch(monkeypatch, False)
    body = _is_error(await client.post(url, json={"ops": add}, headers=_auth(token)), 422, "ops_failed")
    assert "SIGNATURE_QUESTION_ENABLED" in body["errors"][0]["message"]
    _switch(monkeypatch, True)
    response = await client.post(url, json={"ops": add}, headers=_auth(token))
    assert response.status_code == 200, response.text
    stored = await container.form_repo().get_form_document_by_id(form_id)
    fields = [f for page in stored.fields for f in page.properties.fields]
    signature = next(f for f in fields if f.type.value == "signature")
    # off again: a new title still applies; another type's field cannot become one
    _switch(monkeypatch, False)
    rename = [{"op": "update_field", "fieldId": signature.id, "patch": {"title": "Sign below"}}]
    assert (await client.post(url, json={"ops": rename}, headers=_auth(token))).status_code == 200
    again = [{"op": "add_field", "pageId": "page-1", "field": {"title": "Sign again", "type": "signature"}}]
    _is_error(await client.post(url, json={"ops": again}, headers=_auth(token)), 422, "ops_failed")
    # a condition on a signature is signed or not, nothing else
    _switch(monkeypatch, True)
    logic = [{"op": "set_field_logic", "fieldId": "dinner", "logic": {"action": "SHOW", "operator": "AND", "conditions": [{"fieldId": signature.id, "comparison": "IS_EQUAL", "value": "x"}]}}]
    _is_error(await client.post(url, json={"ops": logic}, headers=_auth(token)), 422, "ops_failed")
    logic[0]["logic"]["conditions"][0] = {"fieldId": signature.id, "comparison": "IS_NOT_EMPTY"}
    assert (await client.post(url, json={"ops": logic}, headers=_auth(token))).status_code == 200


async def test_mcp_update_form_follows_the_switch(
    client: AsyncClient, workspace, workspace_form, monkeypatch
):
    doc = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    await _make_v2(doc)
    page_id = doc.fields[0].id
    token = await _make_key(workspace.id, ["forms:read", "forms:write"])
    ops = [{"op": "add_field", "pageId": page_id, "field": {"title": "Sign", "type": "signature"}}]
    args = {"form_id": workspace_form.form_id, "ops": ops, "atomic": True}
    _switch(monkeypatch, False)
    result = _tool_text(await _call_tool(client, token, "update_form", args))
    assert result["applied"] is False
    assert "SIGNATURE_QUESTION_ENABLED" in result["results"][0]["message"]
    _switch(monkeypatch, True)
    result = _tool_text(await _call_tool(client, token, "update_form", args))
    assert result["applied"] is True, result
    stored = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    assert [f.type.value for f in stored.fields[0].properties.fields][-1] == "signature"


async def test_the_permissions_answer_tells_the_builder(client: AsyncClient, workspace, test_user_cookies, monkeypatch):
    url = f"{API}/workspaces/{workspace.id}/permissions"
    _switch(monkeypatch, False)
    assert (await client.get(url, cookies=test_user_cookies)).json()["signatureQuestionEnabled"] is False
    _switch(monkeypatch, True)
    assert (await client.get(url, cookies=test_user_cookies)).json()["signatureQuestionEnabled"] is True


def test_the_switch_is_off_by_default_and_listed():
    from backend.config.application import Application

    assert Application.model_fields["SIGNATURE_QUESTION_ENABLED"].default is False
    assert "SIGNATURE_QUESTION_ENABLED" in open(
        "../docs/settings-inventory.md", encoding="utf-8"
    ).read()


def test_the_assistant_is_told_about_signatures_only_while_they_are_on(monkeypatch):
    from backend.app.services.ai.prompt_builder import ops_guide

    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", False)
    _switch(monkeypatch, False)
    assert "signature (" not in ops_guide()
    _switch(monkeypatch, True)
    assert "signature (a drawn or typed signature" in ops_guide()
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", True)
    assert "signature (a drawn or typed signature" in ops_guide() and "date_range (" in ops_guide()
