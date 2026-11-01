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
    # each test's event loop gets a fresh gate
    monkeypatch.setattr(signatures, "_gate", None)


async def _read(part):
    # an UploadFile (what the module hands on) reads async
    return await part.read() if hasattr(part, "read") else part.file.read()


def test_the_signature_questions_of_a_form_are_found():
    form = _form("short_text", "signature", "signature")
    assert sorted(signature_fields(form)) == ["s1", "s2"]
    assert signature_fields(_form("short_text")) == {}


async def test_a_form_without_a_signature_question_is_left_alone():
    form = _form("file_upload")
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


async def test_a_sandbox_call_that_does_not_end_in_time_is_a_503_and_frees_its_slot(monkeypatch):
    import asyncio

    async def stuck(data):
        await asyncio.sleep(5)

    monkeypatch.setattr(signatures, "CALL_LIMIT_S", 0.05)
    monkeypatch.setattr(signatures, "_process_in_sandbox", stuck)
    gate = signatures._signature_gate()
    free = gate._value
    with pytest.raises(HTTPException) as slow:
        await prepare_signatures(_form("signature"), {"s0": _drawn()}, [Part("s0", "img-1", _png())])
    assert slow.value.status_code == 503
    assert gate._value == free


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
    if isinstance(refused.value.content, dict):
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


async def test_replaced_images_are_deleted_by_key_and_a_failure_never_fails_the_edit():
    deleted = []

    class Store:
        def delete_file_from_s3(self, key, bucket=None):
            if key.endswith("/bad"):
                raise RuntimeError("storage down")
            deleted.append(key)

    await delete_stored_images(Store(), "ws", "form", "resp", ["a", "bad", "../x", "b"])
    assert deleted == ["private/ws/form/resp/a", "private/ws/form/resp/b"]


def test_nothing_in_the_module_decodes_an_image_in_this_process():
    import inspect

    source = inspect.getsource(signatures)
    assert "Image.open" not in source and "from PIL" not in source and "import PIL" not in source
    assert SimpleNamespace  # the module imports no image library


# --- what a part may be, and what an edit may overwrite or delete ------------------------


def _file_form():
    return StandardForm(
        title="Signed",
        builder_version="v2",
        fields=[
            {
                "id": "p1",
                "index": 0,
                "type": "slide",
                "properties": {
                    "fields": [
                        {"id": "doc", "type": "file_upload", "title": "Upload"},
                        {"id": "other_doc", "type": "file_upload", "title": "Upload 2"},
                        {"id": "name", "type": "short_text", "title": "Name"},
                        {"id": "sigA", "type": "signature", "title": "A"},
                        {"id": "sigB", "type": "signature", "title": "B"},
                    ]
                },
            }
        ],
    )


def _held(**ids):
    """Stored answers: question id -> the id of the file it holds (a signature question's drawing, an upload's file)."""
    out = {}
    for key, file_id in ids.items():
        if key.startswith("sig"):
            out[key] = {"type": "signature", "signature": {"method": "drawn", "file_id": file_id, "signed_at": "2026-01-01T10:00:00Z"}}
        else:
            out[key] = {"type": "file_upload", "file_metadata": {"id": file_id, "name": "a.pdf"}}
    return out


async def test_a_part_must_belong_to_a_file_or_signature_question_of_the_form():
    form = _file_form()
    # an upload for its own question passes untouched, whatever the form's other questions
    ok = [Part("doc", "doc-1", b"%PDF")]
    assert (await prepare_signatures(form, {}, ok)).form_files == ok
    for field_id in ("name", "nope", "p1", ""):
        with pytest.raises(HTTPException) as refused:
            await prepare_signatures(form, {}, [Part(field_id, "x-1", b"raw")])
        assert refused.value.status_code == 422
    # and in a form with no signature question at all
    plain = _form("file_upload", "short_text")
    with pytest.raises(HTTPException):
        await prepare_signatures(plain, {}, [Part("q1", "x-1", b"raw")])
    assert (await prepare_signatures(plain, {}, [Part("q0", "x-1", b"raw")])).form_files is not None


async def test_the_draft_versions_questions_count_for_a_part_too():
    published = _form("short_text")
    draft = _file_form()
    parts = [Part("doc", "doc-1", b"%PDF")]
    with pytest.raises(HTTPException):
        await prepare_signatures(published, {}, parts)
    assert (await prepare_signatures(published, {}, parts, also=[draft])).form_files == parts


async def test_an_edit_cannot_overwrite_a_stored_drawing_through_another_question():
    form = _file_form()
    stored = _held(sigA="img-A", doc="doc-1")
    # raw bytes under the stored drawing's id, as another question's file
    for field_id in ("doc", "other_doc"):
        with pytest.raises(HTTPException):
            await prepare_signatures(form, {}, [Part(field_id, "img-A", b"raw")], stored=stored)
    # nor another question's upload, nor the other signature question's drawing
    with pytest.raises(HTTPException):
        await prepare_signatures(form, {}, [Part("other_doc", "doc-1", b"raw")], stored=stored)
    with pytest.raises(HTTPException):
        await prepare_signatures(form, {"sigB": _drawn("img-A")}, [Part("sigB", "img-A", _png())], stored=stored)
    # an upload may replace its own file, and a drawing is redrawn under a new id
    own = [Part("doc", "doc-1", b"%PDF-new")]
    assert (await prepare_signatures(form, {}, own, stored=stored)).form_files == own


async def test_a_drawing_cannot_name_a_file_another_question_holds_or_another_signature_names():
    form = _file_form()
    with pytest.raises(HTTPException):
        await prepare_signatures(form, {"sigA": _drawn("doc-1")}, [Part("sigA", "doc-1", _png())], stored=_held(doc="doc-1"))
    with pytest.raises(HTTPException):
        await prepare_signatures(form, {"sigA": _drawn("img-1")}, None, stored=_held(sigB="img-1"))
    # two signature answers naming one id: the second is refused
    with pytest.raises(HTTPException):
        await prepare_signatures(
            form,
            {"sigA": _drawn("same"), "sigB": _drawn("same")},
            [Part("sigA", "same", _png())],
        )


async def test_an_edit_never_deletes_an_image_another_question_still_holds():
    form = _file_form()
    stored = _held(sigA="img-A", sigB="img-B", doc="doc-1")
    # A retyped, B untouched: only A's image goes
    prepared = await prepare_signatures(form, {"sigA": _typed()}, None, stored=stored)
    assert prepared.replaced == ["img-A"]
    # both retyped: both go
    both = await prepare_signatures(form, {"sigA": _typed(), "sigB": _typed("Bo")}, None, stored=stored)
    assert sorted(both.replaced) == ["img-A", "img-B"]
    # B redrawn under a new id and A cleared: each old image goes once
    redrawn = await prepare_signatures(
        form,
        {"sigB": _drawn("img-B2"), "sigA": {"type": "signature"}},
        [Part("sigB", "img-B2", _png())],
        stored=stored,
    )
    assert sorted(redrawn.replaced) == ["img-A", "img-B"]
    # a file an upload question holds is never in the list, even if an old image shares its id
    shared = _held(sigA="doc-1", doc="doc-1")
    assert (await prepare_signatures(form, {"sigA": _typed()}, None, stored=shared)).replaced == []


async def test_a_signature_slot_on_a_question_that_is_not_a_signature_one_is_dropped():
    form = _file_form()
    answers = {
        "name": {"type": "text", "text": "Ada", "signature": {"method": "typed", "name": "Ada"}},
        "draft-only": {"type": "signature", "signature": {"method": "typed", "name": "Ada"}},
        "sigA": _typed(),
    }
    prepared = await prepare_signatures(form, answers, None)
    assert "signature" not in prepared.answers["name"] and prepared.answers["name"]["text"] == "Ada"
    assert "signature" not in prepared.answers["draft-only"]
    assert prepared.answers["sigA"]["signature"]["name"] == "Fatima El Idrissi"


async def test_drawn_signatures_take_a_bounded_share_of_the_sandbox_and_fail_fast(monkeypatch):
    import asyncio

    monkeypatch.setattr(signatures, "GATE_WAIT_S", 0.05)
    gate = signatures._signature_gate()
    assert gate._value >= 1 and gate._value <= 1 + signatures_parallel() // 2
    held = [await gate.acquire() for _ in range(gate._value)]
    try:
        with pytest.raises(HTTPException) as busy:
            await prepare_signatures(_form("signature"), {"s0": _drawn()}, [Part("s0", "img-1", _png())])
        assert busy.value.status_code == 503
        # a typed signature is not held up
        assert (await prepare_signatures(_form("signature"), {"s0": _typed()}, None)).answers["s0"]
    finally:
        for _ in held:
            gate.release()
    prepared = await prepare_signatures(_form("signature"), {"s0": _drawn()}, [Part("s0", "img-1", _png())])
    assert prepared.form_files


def signatures_parallel():
    from backend.config import settings

    return settings.pdf_import.MAX_PARALLEL_SANDBOXES


async def test_the_throttle_is_asked_once_per_drawn_image_and_not_for_typing():
    calls = []

    async def throttle():
        calls.append(1)

    form = _file_form()
    await prepare_signatures(form, {"sigA": _typed()}, None, throttle=throttle)
    assert calls == []
    await prepare_signatures(
        form,
        {"sigA": _drawn("a"), "sigB": _drawn("b")},
        [Part("sigA", "a", _png()), Part("sigB", "b", _png())],
        throttle=throttle,
    )
    assert calls == [1, 1]
    # a refusal by the throttle stops it before the sandbox
    async def refuse():
        raise HTTPException(status_code=429, content="slow down")

    with pytest.raises(HTTPException) as slow:
        await prepare_signatures(form, {"sigA": _drawn("a")}, [Part("sigA", "a", _png())], throttle=refuse)
    assert slow.value.status_code == 429


async def test_a_part_for_a_signature_question_is_never_passed_through_raw():
    form = _file_form()
    stored = _held(sigA="img-A")
    raw = b"<svg onload=alert(1)>"
    # no answers at all (an edit that sends none): the stored drawing's own id
    for answers in (None, "x", []):
        with pytest.raises(HTTPException) as refused:
            await prepare_signatures(form, answers, [Part("sigA", "img-A", raw)], stored=stored)
        assert refused.value.status_code == 422
    # any part for a signature question, with no answers to bind it
    with pytest.raises(HTTPException):
        await prepare_signatures(form, None, [Part("sigB", "new-1", raw)])
    # uploads of other questions still pass when there are no answers
    ok = [Part("doc", "doc-2", b"%PDF")]
    assert (await prepare_signatures(form, None, ok, stored=stored)).form_files == ok
    # with answers that do not name it, the part is dropped, never stored
    kept = await prepare_signatures(form, {}, [Part("sigA", "img-A", raw)], stored=stored)
    assert not kept.form_files


async def test_a_part_for_a_signature_question_of_another_version_only_is_refused():
    published = _form("short_text", "file_upload")
    draft = _file_form()  # has the signature questions the published version lacks
    raw = b"<svg onload=alert(1)>"
    for answers in ({}, {"q0": {"type": "text", "text": "a"}}):
        with pytest.raises(HTTPException) as refused:
            await prepare_signatures(published, answers, [Part("sigA", "x-1", raw)], also=[draft])
        assert refused.value.status_code == 422
    # a file upload question of the published version keeps its parts, even when
    # an older version had a signature question with that id
    old = _form("signature")
    old_id = next(iter(signature_fields(old)))
    clash = StandardForm(
        title="t",
        builder_version="v2",
        fields=[{"id": "p1", "index": 0, "type": "slide", "properties": {"fields": [
            {"id": old_id, "type": "file_upload", "title": "now an upload"}]}}],
    )
    ok = [Part(old_id, "f-1", b"%PDF")]
    assert (await prepare_signatures(clash, {}, ok, also=[old])).form_files == ok


async def test_clients_with_no_readable_address_share_a_small_bucket_per_form_only(monkeypatch):
    from backend.app.container import container

    hits = []

    class Limiter:
        async def hit(self, scope, key, limit, window):
            hits.append((scope, key, limit))
            return SimpleNamespace(allowed=True, retry_after=1)

    monkeypatch.setattr(container, "rate_limiter", lambda: Limiter())
    await signatures.signature_throttle("w1", "f1", None)
    await signatures.signature_throttle("w1", "f1", "not an address")
    await signatures.signature_throttle("w1", "f1", "203.0.113.7")
    await signatures.signature_throttle("w1", "f1", "2001:db8:1:2:3:4:5:6")
    unknown = [("signature_unknown_client", "w1:f1", signatures.PER_UNKNOWN_PER_FORM_PER_MINUTE)]
    assert hits[0] == hits[2] == unknown[0]
    assert hits[1] == ("signature_form", "w1:f1", signatures.PER_FORM_PER_MINUTE)
    # a known address has its own bucket, never the shared "unknown" one
    assert hits[4] == ("signature_client", "203.0.113.7", signatures.PER_CLIENT_PER_MINUTE)
    assert hits[6][1] == "2001:db8:1:2::/64"
    assert all(h[1] != "unknown" for h in hits)
