"""Page analysis and routing, on synthetic documents, in-process and through the sandbox."""

import asyncio
import os
import pathlib

import pytest

from backend.app.services.pdf_import import sandbox

from backend.app.services.pdf_import.analysis import (
    DocumentRefused,
    analyze_image,
    analyze_pdf,
)
from backend.app.services.pdf_import.fonts import base_font_name, is_legacy_font
from backend.app.services.pdf_import.intake import (
    inspect_upload,
    sniff,
    title_from_file_name,
)
from backend.app.services.pdf_import.sandbox import run_analysis
from tests.app.pdf_import import documents

pytestmark = pytest.mark.asyncio

LIMITS = dict(
    max_pages=30, max_pixels=60_000_000, timeout_s=60, memory_mb=1536, max_parallel=2
)


def routes(result):
    return [page["route"] for page in result["pages"]]


def test_text_pdf_is_read_from_its_text_layer():
    result = analyze_pdf(documents.text_pdf(), max_pages=30)
    assert result["page_count"] == 1 and routes(result) == ["text"]
    page = result["pages"][0]
    assert (
        page["chars"] > 20
        and page["fonts"] == ["Helvetica"]
        and page["legacy_fonts"] == []
    )


def test_legacy_font_pages_are_read_from_the_image():
    # "kl/ro kqsf] ljj/0f" is how a Preeti-layout font stores a Devanagari heading
    result = analyze_pdf(
        documents.text_pdf(["kl/ro kqsf] ljj/0f"], font="ABCDEF+Preeti"), max_pages=30
    )
    page = result["pages"][0]
    assert page["route"] == "vision" and page["legacy_fonts"] == ["Preeti"]
    assert "legacy fonts" in page["reasons"][0]


def test_fillable_pdf_is_read_from_its_fields():
    result = analyze_pdf(documents.fillable_pdf(), max_pages=30)
    assert routes(result) == ["widgets"] and result["pages"][0]["widgets"] == 1


def test_scanned_page_is_a_scan():
    result = analyze_pdf(documents.scan_pdf(), max_pages=30)
    page = result["pages"][0]
    assert (
        page["route"] == "scan" and page["image_coverage"] > 0.9 and page["chars"] == 0
    )


def test_photo_upload_is_one_scan_page():
    result = analyze_image(documents.photo_png(), max_pixels=60_000_000)
    assert result["kind"] == "image" and routes(result) == ["scan"]


def test_refusals_carry_stable_codes():
    with pytest.raises(DocumentRefused) as raised:
        analyze_pdf(documents.encrypted_pdf(), max_pages=30)
    assert raised.value.code == "encrypted"
    with pytest.raises(DocumentRefused) as raised:
        analyze_pdf(documents.text_pdf(pages=4), max_pages=3)
    assert raised.value.code == "too_many_pages"
    with pytest.raises(DocumentRefused) as raised:
        analyze_pdf(b"%PDF-1.7\nnot really a pdf", max_pages=30)
    assert raised.value.code in ("unreadable", "empty")
    with pytest.raises(DocumentRefused) as raised:
        analyze_image(documents.photo_png(), max_pixels=1000)
    assert raised.value.code == "too_large"


async def test_sandbox_returns_the_same_analysis_and_refusals():
    result = await run_analysis(documents.fillable_pdf(), "application/pdf", **LIMITS)
    assert routes(result) == ["widgets"]
    with pytest.raises(DocumentRefused) as raised:
        await run_analysis(documents.encrypted_pdf(), "application/pdf", **LIMITS)
    assert raised.value.code == "encrypted"
    with pytest.raises(DocumentRefused) as raised:
        await run_analysis(b"\x89PNG\r\n\x1a\ngarbage", "image/png", **LIMITS)
    assert raised.value.code == "unreadable"


async def test_sandbox_memory_limit_contains_a_hostile_document():
    # 64 MB of address space is far too little to start Python with the PDF libraries
    with pytest.raises(DocumentRefused):
        await run_analysis(
            documents.text_pdf(), "application/pdf", **{**LIMITS, "memory_mb": 64}
        )


def test_upload_type_is_decided_by_the_bytes():
    assert sniff(documents.text_pdf()) == ("application/pdf", "pdf")
    assert sniff(documents.photo_png()) == ("image/png", "png")
    assert sniff(b"PK\x03\x04 a zip file") is None
    upload = inspect_upload(
        documents.text_pdf(), "Account_Opening form.pdf", max_bytes=10_000_000
    )
    assert (
        upload.content_type == "application/pdf"
        and upload.title == "Account Opening form"
    )
    assert len(upload.sha256) == 64
    for data, code in (
        (b"", "empty"),
        (b"x" * 101, "too_large"),
        (b"hello world", "unsupported_type"),
    ):
        with pytest.raises(DocumentRefused) as raised:
            inspect_upload(data, "x.pdf", max_bytes=100)
        assert raised.value.code == code


def test_titles_and_legacy_font_names():
    assert title_from_file_name("C:\\Users\\me\\KYC_form v2.PDF") == "KYC form v2"
    assert title_from_file_name(None) == "Imported form"
    assert base_font_name("ABCDEF+Kantipur-Bold") == "Kantipur-Bold"
    for name in ("Preeti", "ABCDEF+AakritiBold", "Kruti Dev 010", "PCS NEPALI"):
        assert is_legacy_font(name), name
    for name in ("ArialMT", "Helvetica", "NotoSansDevanagari-Regular", "Mangal"):
        assert not is_legacy_font(name), name


def test_font_names_from_the_document_are_bounded():
    names = [f"Preeti{'X' * 200}{i}" for i in range(20)]
    page = analyze_pdf(documents.many_fonts_pdf(names), max_pages=30)["pages"][0]
    assert page["route"] == "vision"
    assert len(page["legacy_fonts"]) <= 8 and len(page["fonts"]) <= 8
    assert all(len(name) <= 64 for name in page["legacy_fonts"] + page["fonts"])


def test_the_child_gets_no_secrets_and_runs_isolated():
    os.environ["BC_TEST_CANARY_SECRET"] = "should-not-leak"
    try:
        env = sandbox.child_env("/tmp/scratch")
        assert set(env) == {
            "PATH",
            "HOME",
            "LANG",
            "LC_ALL",
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONHASHSEED",
        }
        assert "should-not-leak" not in env.values()
    finally:
        del os.environ["BC_TEST_CANARY_SECRET"]
    command = sandbox.child_command("application/pdf", 30, 1000, 512, 30)
    assert command[1] == "-I" and command[2].endswith("_child.py")


def test_child_modules_never_import_the_backend_package():
    """The child must not load the backend's settings or .env."""
    folder = pathlib.Path(sandbox.__file__).parent
    for name in ("_child.py", "analysis.py", "fonts.py"):
        source = (folder / name).read_text()
        assert "from backend" not in source and "import backend" not in source, name


async def test_sandboxes_are_capped_across_all_imports(monkeypatch):
    real = asyncio.create_subprocess_exec
    running, peak = 0, 0

    async def counting(*args, **kwargs):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        process = await real(*args, **kwargs)
        original_communicate = process.communicate

        async def communicate(data):
            nonlocal running
            try:
                await asyncio.sleep(0.05)
                return await original_communicate(data)
            finally:
                running -= 1

        process.communicate = communicate
        return process

    monkeypatch.setattr(sandbox.asyncio, "create_subprocess_exec", counting)
    results = await asyncio.gather(
        *[
            run_analysis(documents.text_pdf(), "application/pdf", **LIMITS)
            for _ in range(6)
        ]
    )
    assert len(results) == 6 and all(r["page_count"] == 1 for r in results)
    assert peak <= 2
