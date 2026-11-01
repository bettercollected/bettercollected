"""Signature questions: the drawn image and the stamp (services/signatures.py).

The document sandbox is replaced by the real re-encoder it runs
(``pdf_import/logo_image.reencode_image``), so a real PNG, a JPEG, a text file
and a polyglot go through the real decoder; what the sandbox would return is
also faked wrong, to see that the API checks it again."""

import base64
import io
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from backend.app.exceptions import HTTPException
from backend.app.services import signatures
from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.logo_image import reencode_image
from backend.app.services.pdf_import.sandbox import SandboxUnavailable
from backend.app.services.signatures import (
    delete_stored_images,
    prepare_signatures,
    signature_fields,
)
from common.models.standard_form import StandardForm


def _png(width=600, height=200, ink=True, mode="RGBA", extra=None):
    image = Image.new(mode, (width, height), (0, 0, 0, 0) if mode == "RGBA" else 255)
    if ink:
        draw = ImageDraw.Draw(image)
        draw.line((20, 150, 200, 40, 380, 160, 560, 60), fill=(20, 20, 20, 255) if mode == "RGBA" else 0, width=5)
    out = io.BytesIO()
    image.save(out, format="PNG", **(extra or {}))
    return out.getvalue()


def _form(*types):
    fields = [
        {"id": f"s{i}" if t == "signature" else f"q{i}", "type": t, "title": t}
        for i, t in enumerate(types)
    ]
    return StandardForm(
        title="Signed",
        builder_version="v2",
        fields=[
            {"id": "p1", "index": 0, "type": "slide", "properties": {"fields": fields}}
        ],
    )


class Part:
    """An uploaded part, as FormFileResponse hands it over."""

    def __init__(self, field_id, file_id, data):
        from fastapi import UploadFile

        self.field_id, self.file_id = field_id, file_id
        self.filename = "x.png"
        self.file = UploadFile(file=io.BytesIO(data), filename="x.png")


def _typed(name="Fatima El Idrissi"):
    return {"type": "signature", "signature": {"method": "typed", "name": name}}


def _drawn(file_id="img-1"):
    return {"type": "signature", "signature": {"method": "drawn", "file_id": file_id}}


@pytest.fixture(autouse=True)
def real_reencoder(monkeypatch):
    async def process(data):
        return reencode_image(data, signatures.MAX_PIXELS)

    monkeypatch.setattr(signatures, "_process_in_sandbox", process)


async def _read(part):
    # an UploadFile (what the module hands on) reads async
    return await part.read() if hasattr(part, "read") else part.file.read()


def test_the_signature_questions_of_a_form_are_found():
    form = _form("short_text", "signature", "signature")
    assert sorted(signature_fields(form)) == ["s1", "s2"]
    assert signature_fields(_form("short_text")) == {}


async def test_a_form_without_a_signature_question_is_left_alone():
    form = _form("short_text")
    parts = [Part("q0", "f1", b"anything at all")]
    answers = {"q0": {"type": "text", "text": "hi"}}
    prepared = await prepare_signatures(form, answers, parts)
    assert prepared.answers is answers and prepared.form_files is parts


async def test_a_typed_signature_is_stamped_by_the_server_and_needs_no_image():
    form = _form("signature")
    answers = {"s0": {"type": "signature", "signature": {"method": "typed", "name": "Ada Lovelace", "signed_at": "1999-01-01T00:00:00Z", "url": "https://elsewhere.test/x"}}}
    prepared = await prepare_signatures(form, answers, None)
    signature = prepared.answers["s0"]["signature"]
    assert signature["method"] == "typed" and signature["name"] == "Ada Lovelace"
    assert signature["signed_at"].endswith("Z") and not signature["signed_at"].startswith("1999")
    assert "url" not in signature and "file_id" not in signature
    assert prepared.form_files is None and prepared.replaced == []


async def test_a_drawn_signature_stores_the_re_encoded_image_never_the_upload():
    form = _form("short_text", "signature")
    upload = _png(extra={"pnginfo": _info("Comment", "secret metadata")})
    assert b"secret metadata" in upload
    prepared = await prepare_signatures(form, {"s1": _drawn()}, [Part("s1", "img-1", upload)])
    stored = await _read(prepared.form_files[0].file)
    assert stored.startswith(b"\x89PNG") and b"secret metadata" not in stored
    assert prepared.form_files[0].file_id == "img-1"
    signature = prepared.answers["s1"]["signature"]
    assert signature["method"] == "drawn" and signature["file_id"] == "img-1"
    assert signature["signed_at"].endswith("Z")


def _info(key, value):
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text(key, value)
    return info


async def test_other_parts_of_the_submission_pass_through_untouched():
    form = _form("file_upload", "signature")
    other = Part("q0", "doc-1", b"%PDF-1.4 whatever")
    prepared = await prepare_signatures(
        form, {"s1": _drawn()}, [other, Part("s1", "img-1", _png())]
    )
    assert [p.file_id for p in prepared.form_files] == ["doc-1", "img-1"]
    assert prepared.form_files[0] is other


@pytest.mark.parametrize(
    "upload",
    [
        b"",
        b"not an image at all",
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
        b"\xff\xd8\xff\xe0" + b"0" * 200,  # a JPEG's first bytes
        b"\x89PNG\r\n\x1a\n" + b"<script>alert(1)</script>" * 20,  # a polyglot, not a PNG
        _png()[:60],  # a PNG cut short
    ],
)
async def test_a_bad_image_is_refused_before_anything_is_stored(upload):
    with pytest.raises(HTTPException) as refused:
        await prepare_signatures(_form("signature"), {"s0": _drawn()}, [Part("s0", "img-1", upload)])
    body = refused.value.content
    assert refused.value.status_code == 422
    assert body["code"] == "invalid_answers"
    assert body["errors"] == [{"fieldId": "s0", "rule": "signature_image"}]


async def test_a_real_jpeg_is_refused_because_only_png_is_taken():
    out = io.BytesIO()
    Image.new("RGB", (300, 100), "white").save(out, format="JPEG")
    with pytest.raises(HTTPException) as refused:
        await prepare_signatures(_form("signature"), {"s0": _drawn()}, [Part("s0", "img-1", out.getvalue())])
    assert refused.value.status_code == 422


async def test_an_image_over_the_size_cap_is_refused_without_reaching_the_sandbox(monkeypatch):
    called = []

    async def process(data):
        called.append(len(data))
        return {}

    monkeypatch.setattr(signatures, "_process_in_sandbox", process)
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (signatures.UPLOAD_MAX_BYTES + 10)
    with pytest.raises(HTTPException) as refused:
        await prepare_signatures(_form("signature"), {"s0": _drawn()}, [Part("s0", "img-1", big)])
    assert refused.value.status_code == 422 and called == []


async def test_too_many_pixels_and_too_small_are_refused():
    for width, height in ((1400, 900), (4000, 20), (8, 8)):
        with pytest.raises(HTTPException) as refused:
            await prepare_signatures(
                _form("signature"),
                {"s0": _drawn()},
                [Part("s0", "img-1", _png(width, height, ink=False))],
            )
        assert refused.value.status_code == 422, (width, height)


async def test_what_the_sandbox_returns_is_checked_again(monkeypatch):
    good = reencode_image(_png(), signatures.MAX_PIXELS)
    wrong = {
        "not a dict": "x",
        "a jpeg": {**good, "format": "jpeg"},
        "huge": {**good, "width": 5000},
        "tiny": {**good, "height": 4},
        "bool size": {**good, "width": True},
        "not base64": {**good, "data": "***not base64***"},
        "not a png": {**good, "data": base64.b64encode(b"GIF89a....").decode()},
        "empty": {**good, "data": ""},
        "too long": {**good, "data": "A" * (3 * signatures.STORED_MAX_BYTES)},
    }
    for name, result in wrong.items():

        async def process(data, result=result):
            return result

        monkeypatch.setattr(signatures, "_process_in_sandbox", process)
        with pytest.raises(HTTPException) as refused:
            await prepare_signatures(_form("signature"), {"s0": _drawn()}, [Part("s0", "img-1", _png())])
        assert refused.value.status_code == 422, name


async def test_a_document_the_sandbox_refuses_is_a_422_and_no_sandbox_is_a_503(monkeypatch):
    async def refuse(data):
        raise DocumentRefused("unreadable", "nope")

    async def down(data):
        raise SandboxUnavailable("gone")

    monkeypatch.setattr(signatures, "_process_in_sandbox", refuse)
    with pytest.raises(HTTPException) as refused:
        await prepare_signatures(_form("signature"), {"s0": _drawn()}, [Part("s0", "img-1", _png())])
    assert refused.value.status_code == 422
    monkeypatch.setattr(signatures, "_process_in_sandbox", down)
    with pytest.raises(HTTPException) as unavailable:
        await prepare_signatures(_form("signature"), {"s0": _drawn()}, [Part("s0", "img-1", _png())])
    assert unavailable.value.status_code == 503
    # a typed signature never needs the sandbox
    prepared = await prepare_signatures(_form("signature"), {"s0": _typed()}, None)
    assert prepared.answers["s0"]["signature"]["method"] == "typed"


@pytest.mark.parametrize(
    "answers,parts",
    [
        # an id with no image
        ({"s0": _drawn("img-1")}, []),
        # an image for another id
        ({"s0": _drawn("img-1")}, [("s0", "img-2")]),
        # an image of another question
        ({"s0": _drawn("img-1")}, [("q1", "img-1")]),
        # two images for one question
        ({"s0": _drawn("img-1")}, [("s0", "img-1"), ("s0", "img-3")]),
        # a typed answer that names an image, a drawn one that names a name
        ({"s0": {"type": "signature", "signature": {"method": "typed", "name": "A", "file_id": "img-1"}}}, [("s0", "img-1")]),
        ({"s0": {"type": "signature", "signature": {"method": "drawn", "file_id": "img-1", "name": "A"}}}, [("s0", "img-1")]),
        # an id that could name another key
        ({"s0": _drawn("../other/img")}, [("s0", "../other/img")]),
        ({"s0": _drawn("a/b")}, [("s0", "a/b")]),
        # unknown method, unknown key, not text
        ({"s0": {"type": "signature", "signature": {"method": "stamp", "name": "A"}}}, []),
        ({"s0": {"type": "signature", "signature": {"method": "typed", "name": "A", "extra": "x"}}}, []),
        ({"s0": {"type": "signature", "signature": {"method": "typed", "name": 7}}}, []),
        ({"s0": {"type": "signature", "signature": "Fatima"}}, []),
    ],
)
async def test_an_answer_that_does_not_hold_together_is_refused(answers, parts):
    form = _form("signature", "short_text")
    sent = [Part(field, file_id, _png()) for field, file_id in parts]
    with pytest.raises(HTTPException) as refused:
        await prepare_signatures(form, answers, sent)
    assert refused.value.status_code == 422
    assert refused.value.content["errors"][0]["fieldId"] == "s0"


async def test_two_parts_with_one_id_are_refused_so_one_cannot_overwrite_another():
    form = _form("file_upload", "signature")
    with pytest.raises(HTTPException) as refused:
        await prepare_signatures(
            form,
            {"s1": _drawn("same")},
            [Part("q0", "same", b"pdf"), Part("s1", "same", _png())],
        )
    assert refused.value.status_code == 422


async def test_an_image_nobody_names_is_dropped_never_stored():
    form = _form("signature")
    prepared = await prepare_signatures(form, {"s0": _typed()}, [Part("s0", "img-1", _png())])
    assert prepared.form_files is None
    prepared = await prepare_signatures(form, {}, [Part("s0", "img-1", _png())])
    assert prepared.form_files is None


STORED = {"s0": {"type": "signature", "signature": {"method": "typed", "name": "Ada", "signed_at": "2026-01-01T10:00:00Z"}}}
STORED_DRAWN = {"s0": {"type": "signature", "signature": {"method": "drawn", "file_id": "old-img", "signed_at": "2026-01-01T10:00:00Z", "url": "https://signed.test/a"}}}


async def test_an_edit_that_leaves_the_signature_alone_changes_nothing():
    form = _form("signature")
    prepared = await prepare_signatures(form, {}, None, stored=STORED_DRAWN)
    assert prepared.answers == {} and prepared.replaced == []


async def test_an_edit_that_sends_the_same_typed_name_keeps_the_stamp():
    form = _form("signature")
    prepared = await prepare_signatures(form, {"s0": _typed("Ada")}, None, stored=STORED)
    assert prepared.answers["s0"]["signature"]["signed_at"] == "2026-01-01T10:00:00Z"
    prepared = await prepare_signatures(form, {"s0": _typed("Ada L.")}, None, stored=STORED)
    assert prepared.answers["s0"]["signature"]["signed_at"] != "2026-01-01T10:00:00Z"


async def test_an_edit_that_sends_the_stored_drawn_answer_back_needs_no_image_and_keeps_it():
    form = _form("signature")
    prepared = await prepare_signatures(form, {"s0": STORED_DRAWN["s0"]}, None, stored=STORED_DRAWN)
    signature = prepared.answers["s0"]["signature"]
    assert signature == {"method": "drawn", "file_id": "old-img", "signed_at": "2026-01-01T10:00:00Z"}
    assert prepared.replaced == [] and prepared.form_files is None


async def test_an_edit_cannot_name_an_image_the_response_does_not_hold():
    form = _form("signature")
    with pytest.raises(HTTPException):
        await prepare_signatures(form, {"s0": _drawn("someone-elses")}, None, stored=STORED_DRAWN)
    with pytest.raises(HTTPException):
        await prepare_signatures(form, {"s0": _drawn("someone-elses")}, None, stored=None)


async def test_redrawing_retyping_or_clearing_names_the_old_image_as_replaced():
    form = _form("signature")
    redrawn = await prepare_signatures(
        form, {"s0": _drawn("new-img")}, [Part("s0", "new-img", _png())], stored=STORED_DRAWN
    )
    assert redrawn.replaced == ["old-img"]
    retyped = await prepare_signatures(form, {"s0": _typed()}, None, stored=STORED_DRAWN)
    assert retyped.replaced == ["old-img"]
    cleared = await prepare_signatures(form, {"s0": {"type": "signature"}}, None, stored=STORED_DRAWN)
    assert cleared.replaced == ["old-img"]


def test_replaced_images_are_deleted_by_key_and_a_failure_never_fails_the_edit():
    deleted = []

    class Store:
        def delete_file_from_s3(self, key, bucket=None):
            if key.endswith("/bad"):
                raise RuntimeError("storage down")
            deleted.append(key)

    delete_stored_images(Store(), "ws", "form", "resp", ["a", "bad", "../x", "b"])
    assert deleted == ["private/ws/form/resp/a", "private/ws/form/resp/b"]


def test_nothing_in_the_module_decodes_an_image_in_this_process():
    import inspect

    source = inspect.getsource(signatures)
    assert "Image.open" not in source and "from PIL" not in source and "import PIL" not in source
    assert SimpleNamespace  # the module imports no image library
