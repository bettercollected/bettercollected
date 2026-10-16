"""The organisation logo of a form (services/form_logo.py): which files are
taken, that the API never decodes them (the document sandbox does, and only
its re-encoding is stored), where they are stored, and that replacing,
removing, copying and deleting a form never leave a respondent page pointing
at a missing file or at someone else's server.

The sandbox is replaced by a fake here; the real operation is tested in
tests/app/pdf_import/test_logo_image.py."""

import ast
import base64
import io
import json
import pathlib

import pytest
from httpx import AsyncClient
from PIL import Image

from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services import form_logo
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.form_logo import (
    LOGO_MAX_BYTES,
    check_logo_bytes,
    sniff_image_format,
)
from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.sandbox import SandboxUnavailable
from tests.app.controllers.data import formData, testUser


def image_bytes(fmt: str = "PNG", size=(120, 48), colour=(11, 61, 145)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format=fmt)
    return buffer.getvalue()


SVG = (
    b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg">'
    b"<script>alert(1)</script></svg>"
)
_CONTENT_TYPES = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}


class FakeSandbox:
    """Answers like the sandbox's logo mode with a recognisably different
    file of the same format, so a test can tell what got stored."""

    def __init__(self):
        self.calls = []
        self.raises = None
        self.result = None

    async def __call__(self, data: bytes) -> dict:
        self.calls.append(data)
        if self.raises:
            raise self.raises
        if self.result is not None:
            return self.result
        kind = sniff_image_format(data)
        fmt = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}[kind]
        reencoded = image_bytes(fmt, size=(120, 48), colour=(1, 2, 3))
        return {
            "format": kind,
            "content_type": _CONTENT_TYPES[kind],
            "width": 120,
            "height": 48,
            "data": base64.b64encode(reencoded).decode("ascii"),
        }


@pytest.fixture(autouse=True)
def fake_sandbox(monkeypatch):
    fake = FakeSandbox()
    monkeypatch.setattr(form_logo, "_process_in_sandbox", fake)
    return fake


# --- which files are taken -----------------------------------------------------


@pytest.mark.parametrize(
    "fmt,kind,content_type",
    [
        ("PNG", "png", "image/png"),
        ("JPEG", "jpeg", "image/jpeg"),
        ("WEBP", "webp", "image/webp"),
    ],
)
async def test_png_jpeg_and_webp_are_taken_as_the_sandbox_reencoded_them(
    fake_sandbox, fmt, kind, content_type
):
    upload = image_bytes(fmt)
    assert sniff_image_format(upload) == kind
    checked = await check_logo_bytes(upload)
    assert fake_sandbox.calls == [upload]
    assert checked.content_type == content_type
    assert (checked.width, checked.height) == (120, 48)
    # what is kept is the sandbox's encoding, never the upload
    assert checked.data != upload
    assert checked.data == base64.b64decode((await fake_sandbox(upload))["data"])


@pytest.mark.parametrize(
    "data,status",
    [
        (SVG, 415),
        (b"<html><script>alert(1)</script></html>", 415),
        (image_bytes("GIF"), 415),
        (image_bytes("BMP"), 415),
        (b"", 422),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * LOGO_MAX_BYTES, 413),
    ],
    ids=["svg", "html", "gif", "bmp", "empty", "over-1mb"],
)
async def test_other_files_are_refused_before_the_sandbox(fake_sandbox, data, status):
    with pytest.raises(HTTPException) as refused:
        await check_logo_bytes(data)
    assert refused.value.status_code == status
    assert fake_sandbox.calls == []


@pytest.mark.parametrize(
    "code,status",
    [
        ("bad_size", 422),
        ("unreadable", 422),
        ("unsupported_type", 415),
        ("too_large", 422),
    ],
)
async def test_sandbox_refusals_become_plain_answers(fake_sandbox, code, status):
    fake_sandbox.raises = DocumentRefused(code, "no")
    with pytest.raises(HTTPException) as refused:
        await check_logo_bytes(image_bytes())
    assert refused.value.status_code == status


async def test_without_the_sandbox_uploads_are_refused_not_decoded(fake_sandbox):
    fake_sandbox.raises = SandboxUnavailable("down")
    with pytest.raises(HTTPException) as refused:
        await check_logo_bytes(image_bytes())
    assert refused.value.status_code == 503
    assert "unavailable" in str(refused.value.content)


async def test_without_a_configured_sandbox_the_real_client_refuses(monkeypatch):
    # the real client with no socket configured: native work never runs locally
    monkeypatch.undo()
    monkeypatch.setattr(form_logo.settings.pdf_import, "SANDBOX_SOCKET", "")
    with pytest.raises(HTTPException) as refused:
        await check_logo_bytes(image_bytes())
    assert refused.value.status_code == 503


@pytest.mark.parametrize(
    "result",
    [
        ["not", "a", "dict"],
        {"format": "jpeg", "width": 120, "height": 48, "data": ""},
        {"format": "png", "width": "120", "height": 48, "data": ""},
        {"format": "png", "width": 120, "height": 48, "data": "not base64!"},
        {
            "format": "png",
            "width": 120,
            "height": 48,
            "data": base64.b64encode(SVG).decode("ascii"),
        },
        {
            "format": "png",
            "width": 9000,
            "height": 48,
            "data": base64.b64encode(image_bytes()).decode("ascii"),
        },
    ],
    ids=[
        "nothing",
        "other-format",
        "bad-width",
        "bad-base64",
        "not-an-image",
        "too-wide",
    ],
)
async def test_what_the_sandbox_returns_is_checked(fake_sandbox, result):
    fake_sandbox.result = result
    with pytest.raises(HTTPException) as refused:
        await check_logo_bytes(image_bytes())
    assert refused.value.status_code == 422


def test_the_api_never_imports_an_image_decoder():
    source = pathlib.Path(form_logo.__file__).read_text()
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "PIL" not in imported
    assert "MAX_IMAGE_PIXELS" not in source
    assert "Image.open" not in source
    # nor does anything else in the API outside the sandbox's own modules
    app = pathlib.Path(form_logo.__file__).parents[1]
    for path in app.rglob("*.py"):
        if "pdf_import" in path.parts:
            continue
        text = path.read_text()
        assert "MAX_IMAGE_PIXELS" not in text, path
        assert "from PIL" not in text and "import PIL" not in text, path


def test_only_urls_in_our_own_public_storage_are_ours():
    ours = AWSS3Service.public_url_of("public/form-logos/f/a.png")
    assert AWSS3Service.public_key_of(ours) == "public/form-logos/f/a.png"
    for url in (
        "https://example.org/logo.png",
        ours.replace("/public/", "/private/"),
        ours.replace("form-logos/f", "form-logos/../private"),
        ours + "?x=1",
        "",
        None,
    ):
        assert AWSS3Service.public_key_of(url) is None


# --- storage, with the bucket replaced by a dictionary ----------------------------


class FakeBucket:
    def __init__(self):
        self.objects = {}

    def put(self, body, key, content_type):
        self.objects[key] = (body, content_type)
        return AWSS3Service.public_url_of(key)

    def copy(self, source_url, key):
        source = AWSS3Service.public_key_of(source_url)
        if source not in self.objects:
            return None
        self.objects[key] = self.objects[source]
        return AWSS3Service.public_url_of(key)

    def delete(self, url):
        return self.objects.pop(AWSS3Service.public_key_of(url), None) is not None

    def delete_folder(self, prefix):
        for key in [k for k in self.objects if k.startswith(prefix)]:
            del self.objects[key]

    def has(self, url):
        return AWSS3Service.public_key_of(url) in self.objects


@pytest.fixture()
def bucket(monkeypatch):
    fake = FakeBucket()
    aws = container.aws_service()
    monkeypatch.setattr(
        aws,
        "put_public_object",
        lambda body, key, content_type: fake.put(body, key, content_type),
    )
    monkeypatch.setattr(aws, "copy_public_object", lambda url, key: fake.copy(url, key))
    monkeypatch.setattr(aws, "delete_public_object", lambda url: fake.delete(url))
    monkeypatch.setattr(
        aws, "delete_folder_from_s3", lambda prefix: fake.delete_folder(prefix)
    )
    return fake


def _logo_url(workspace, form_id):
    return f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/logo"


async def _upload(
    client, workspace, form_id, cookies, data, name="logo.png", type_="image/png"
):
    return await client.put(
        _logo_url(workspace, form_id),
        files={"file": (name, data, type_)},
        cookies=cookies,
    )


async def _draft(form_id):
    return await container.form_service().get_form_document_by_id(str(form_id))


async def test_an_uploaded_logo_is_stored_in_our_bucket_with_its_type(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, bucket
):
    reply = await _upload(
        client,
        workspace,
        workspace_form.form_id,
        test_user_cookies,
        image_bytes("WEBP"),
        "logo.webp",
        "image/webp",
    )
    assert reply.status_code == 200, reply.text
    url = reply.json()["logo"]
    key = AWSS3Service.public_key_of(url)
    assert key.startswith(f"public/form-logos/{workspace_form.form_id}/")
    assert key.endswith(".webp")
    assert bucket.objects[key][1] == "image/webp"
    assert (await _draft(workspace_form.form_id)).logo == url


@pytest.mark.parametrize(
    "data,name,type_",
    [
        (SVG, "logo.svg", "image/svg+xml"),
        # an SVG named and typed as a PNG
        (SVG, "logo.png", "image/png"),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * LOGO_MAX_BYTES, "big.png", "image/png"),
    ],
    ids=["svg", "fake-extension", "oversize"],
)
async def test_a_refused_upload_stores_nothing(
    client: AsyncClient,
    workspace,
    workspace_form,
    test_user_cookies,
    bucket,
    data,
    name,
    type_,
):
    reply = await _upload(
        client, workspace, workspace_form.form_id, test_user_cookies, data, name, type_
    )
    assert reply.status_code in (413, 415)
    assert bucket.objects == {}
    assert (await _draft(workspace_form.form_id)).logo is None


async def test_the_multipart_form_update_checks_the_logo_too(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, bucket
):
    reply = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}",
        data={"form_body": json.dumps(formData)},
        files={"logo": ("logo.png", SVG, "image/png")},
        cookies=test_user_cookies,
    )
    assert reply.status_code == 415
    assert bucket.objects == {}


async def test_replacing_a_draft_logo_deletes_the_old_file(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, bucket
):
    first = (
        await _upload(
            client, workspace, workspace_form.form_id, test_user_cookies, image_bytes()
        )
    ).json()["logo"]
    second = (
        await _upload(
            client,
            workspace,
            workspace_form.form_id,
            test_user_cookies,
            image_bytes("JPEG"),
            "l.jpg",
            "image/jpeg",
        )
    ).json()["logo"]
    assert first != second
    assert not bucket.has(first) and bucket.has(second)


async def test_the_live_logo_stays_until_a_publish_replaces_it(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, bucket
):
    service = container.workspace_form_service()
    live = (
        await _upload(
            client, workspace, workspace_form.form_id, test_user_cookies, image_bytes()
        )
    ).json()["logo"]
    await service.publish_form(workspace.id, workspace_form.form_id, testUser)

    reply = await client.delete(
        _logo_url(workspace, workspace_form.form_id), cookies=test_user_cookies
    )
    assert reply.status_code == 200, reply.text
    assert reply.json().get("logo") is None, reply.text
    assert (await _draft(workspace_form.form_id)).logo is None
    # respondents still see the published form, logo included
    assert bucket.has(live)

    await service.publish_form(workspace.id, workspace_form.form_id, testUser)
    assert not bucket.has(live)


async def test_removing_an_unpublished_logo_deletes_its_file(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, bucket
):
    url = (
        await _upload(
            client, workspace, workspace_form.form_id, test_user_cookies, image_bytes()
        )
    ).json()["logo"]
    reply = await client.delete(
        _logo_url(workspace, workspace_form.form_id), cookies=test_user_cookies
    )
    assert reply.status_code == 200
    assert not bucket.has(url)


async def test_logo_settings_round_trip_and_a_sent_logo_url_is_ignored(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, bucket
):
    url = (
        await _upload(
            client, workspace, workspace_form.form_id, test_user_cookies, image_bytes()
        )
    ).json()["logo"]
    body = {
        **formData,
        "logo": "https://tracker.example.org/pixel.png",
        "logoPosition": "center",
        "logoAlt": "Wijkcentrum De Kroon",
        "useWorkspaceLogo": True,
    }
    reply = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}",
        data={"form_body": json.dumps(body)},
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    saved = reply.json()
    assert saved["logo"] == url
    assert (saved["logoPosition"], saved["logoAlt"], saved["useWorkspaceLogo"]) == (
        "center",
        "Wijkcentrum De Kroon",
        True,
    )
    # an older client that doesn't send the settings keeps them
    reply = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}",
        data={"form_body": json.dumps(formData)},
        cookies=test_user_cookies,
    )
    assert reply.json()["logoPosition"] == "center"
    # and they go live with the form
    await container.workspace_form_service().publish_form(
        workspace.id, workspace_form.form_id, testUser
    )
    live = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}",
        params={"published": True},
    )
    assert live.status_code == 200, live.text
    assert (
        live.json()["logo"],
        live.json()["logoPosition"],
        live.json()["logoAlt"],
    ) == (
        url,
        "center",
        "Wijkcentrum De Kroon",
    )


async def test_an_unknown_logo_position_is_refused(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, bucket
):
    reply = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}",
        data={"form_body": json.dumps({**formData, "logoPosition": "right"})},
        cookies=test_user_cookies,
    )
    assert reply.status_code == 422


async def test_a_new_form_takes_only_a_logo_in_our_storage_and_copies_it(
    workspace, bucket
):
    service = container.workspace_form_service()
    foreign = await service.create_form(
        workspace.id,
        StandardForm(**{**formData, "logo": "https://example.org/x.png"}),
        testUser,
    )
    assert foreign.logo is None

    source = bucket.put(image_bytes(), "public/form-logos/templates/t.png", "image/png")
    copied = await service.create_form(
        workspace.id, StandardForm(**{**formData, "logo": source}), testUser
    )
    assert copied.logo and copied.logo != source
    assert AWSS3Service.public_key_of(copied.logo).startswith(
        f"public/form-logos/{copied.form_id}/"
    )
    assert bucket.has(source) and bucket.has(copied.logo)


async def test_a_duplicate_has_its_own_logo_file(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, bucket
):
    original = (
        await _upload(
            client, workspace, workspace_form.form_id, test_user_cookies, image_bytes()
        )
    ).json()["logo"]
    reply = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/duplicate",
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    copy = reply.json()
    assert copy["logo"] and copy["logo"] != original

    # removing it from the copy leaves the original's file alone
    await client.delete(_logo_url(workspace, copy["formId"]), cookies=test_user_cookies)
    assert bucket.has(original) and not bucket.has(copy["logo"])


async def test_deleting_a_form_deletes_its_logo_files(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, bucket
):
    url = (
        await _upload(
            client, workspace, workspace_form.form_id, test_user_cookies, image_bytes()
        )
    ).json()["logo"]
    await container.workspace_form_service().publish_form(
        workspace.id, workspace_form.form_id, testUser
    )
    reply = await client.delete(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}",
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    assert not bucket.has(url)
