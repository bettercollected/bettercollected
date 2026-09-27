"""Legacy-font decoding and text-layer recovery, on generated documents."""

import io

import pdfplumber
import pytest

from backend.app.services.pdf_import.analysis import analyze_pdf
from backend.app.services.pdf_import.legacy_decode import (
    decode_preeti,
    decoder_for,
    plausibility,
    starts_with_sign,
    word_ok,
)
from backend.app.services.pdf_import.text_layer import (
    colour_hex,
    extract_text_layer,
    page_words,
    script_of,
)
from tests.app.pdf_import import documents

# (stored codes, what the page shows) for common form vocabulary
PREETI_WORDS = [
    ("kl/ro kqsf] ljj/0f", "परिचय पत्रको विवरण"),  # ि before its consonant, half ण + ा
    ("gful/stf k|df0f kq", "नागरिकता प्रमाण पत्र"),  # ्र from "|"
    ("/fli6«o", "राष्ट्रिय"),  # ि after a whole conjunct
    ("hGd btf{", "जन्म दर्ता"),  # reph stored after its syllable
    ("-gfafnssf] xsdf_", "(नाबालकको हकमा)"),  # ा + े = ो, brackets
    ("g+=", "नं."),  # anusvara, full stop
    ("hf/L u/]sf] :yfg", "जारी गरेको स्थान"),  # half स from ":"
    ("JolQmut", "व्यक्तिगत"),  # "Qm" pair
    ("kmf/d", "फारम"),  # "km" pair
    (";“u", "सँग"),  # chandrabindu
    ("/fli6«otfM", "राष्ट्रियता:"),  # colon
    ("a}+ls·", "बैंकिङ्ग"),  # ङ्ग
    ("adfl]hd", "बमोजिम"),  # ि stored before another vowel sign and its consonant
    ("cfˆgf]", "आफ्नो"),  # अ + ा = आ, half फ
    ("!@#", "१२३"),  # digits on the shifted number row
]


@pytest.mark.parametrize("stored,shown", PREETI_WORDS)
def test_preeti_words_decode(stored, shown):
    assert decode_preeti(stored) == shown


def test_plausibility_separates_decoded_text_from_raw_codes():
    decoded = " ".join(decode_preeti(s) for s, _ in PREETI_WORDS)
    assert plausibility(decoded) == 1.0
    assert plausibility(" ".join(s for s, _ in PREETI_WORDS[:8])) < 0.2
    assert not word_ok("ाणपत्र") and not word_ok("कोे") and word_ok("(नाम)")
    assert starts_with_sign("ै") and not starts_with_sign("नाम")


def test_decoders_are_chosen_by_font_name():
    assert decoder_for("Preeti") and decoder_for("AakritiBold")
    assert decoder_for("Kantipur") is None and decoder_for("ArialMT") is None


def test_helpers():
    assert colour_hex((1, 0, 0)) == "#ff0000"
    assert colour_hex(0.75) == "#bfbfbf"
    assert colour_hex((0, 1, 1, 0)) == "#ff0000"  # CMYK red
    assert colour_hex(None) is None
    assert script_of("परिचय") == "devanagari" and script_of("Name") == "latin"
    assert script_of("123") == "digits" and script_of("/") == "symbols"


def _words(data):
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return page_words(pdf.pages[0])


def test_legacy_font_words_are_decoded_with_their_boxes():
    page = _words(
        documents.text_pdf(["kl/ro kqsf] ljj/0f", "gful/stf k|df0f kq"], font="Preeti")
    )
    texts = [w["text"] for w in page["words"]]
    assert texts == ["परिचय", "पत्रको", "विवरण", "नागरिकता", "प्रमाण", "पत्र"]
    assert all(
        w["source"] == "decoded" and w["script"] == "devanagari" for w in page["words"]
    )
    assert page["decoded_trusted"] and not page["read_from_image"]
    assert all(w["x1"] > w["x0"] and w["bottom"] > w["top"] for w in page["words"])


def test_unicode_words_are_kept_as_they_are():
    page = _words(documents.text_pdf(["Full name", "Email address"]))
    assert [w["text"] for w in page["words"]] == ["Full", "name", "Email", "address"]
    assert {w["source"] for w in page["words"]} == {"text"}
    assert page["legacy_words"] == 0 and page["decoded_plausibility"] is None


def test_a_malformed_word_taints_its_line_only():
    good = "kl/ro kqsf] ljj/0f gful/stf k|df0f kq /fxbfgL dtbftf ;jf/L rfns"
    # the second line holds one malformed word (doubled vowel signs) and one good one
    page = _words(documents.text_pdf([good, good, good, "f]]s gfd"], font="Preeti"))
    assert page["decoded_trusted"] and not page["read_from_image"]
    by_line = {}
    for w in page["words"]:
        by_line.setdefault(round(w["top"]), []).append(w["source"])
    lines = [set(by_line[k]) for k in sorted(by_line)]
    assert lines == [{"decoded"}, {"decoded"}, {"decoded"}, {"untrusted"}]


def test_an_undecodable_page_is_read_from_its_image():
    page = _words(documents.text_pdf(["]]f] ff]]", "f]]f ]]"], font="Preeti"))
    assert page["read_from_image"] and page["untrusted_words"] == len(page["words"])


def test_routes_for_decodable_and_unknown_legacy_fonts():
    decodable = analyze_pdf(
        documents.text_pdf(["kl/ro kqsf]"], font="Preeti"), max_pages=30
    )
    assert decodable["pages"][0]["route"] == "text"
    assert "decoded" in decodable["pages"][0]["reasons"][0]
    unknown = analyze_pdf(
        documents.text_pdf(["kl/ro kqsf]"], font="Kantipur"), max_pages=30
    )
    assert unknown["pages"][0]["route"] == "vision"


def test_scanned_pages_are_skipped():
    result = extract_text_layer(documents.text_pdf(pages=2), skip_pages={2})
    assert [p["skipped"] for p in result["pages"]] == [False, True]


def _dense_pdf(words_per_line=60, lines=100) -> bytes:
    """A page full of tiny words: far more than any real form."""
    line = " ".join("ab" for _ in range(words_per_line))
    return documents.text_pdf([line] * lines)


@pytest.mark.asyncio
async def test_a_page_with_more_words_than_any_form_is_refused():
    from backend.app.services.pdf_import.analysis import DocumentRefused
    from backend.app.services.pdf_import.sandbox import run_text_layer

    limits = dict(
        max_pages=30,
        max_pixels=60_000_000,
        timeout_s=60,
        memory_mb=1536,
        max_parallel=2,
    )
    with pytest.raises(DocumentRefused) as raised:
        await run_text_layer(_dense_pdf(), **limits)
    assert raised.value.code == "too_complex"


def test_the_document_word_cap(monkeypatch):
    from backend.app.services.pdf_import import text_layer

    monkeypatch.setattr(text_layer, "MAX_WORDS_PER_DOCUMENT", 5)
    with pytest.raises(text_layer.TooMuchText):
        text_layer.extract_text_layer(documents.text_pdf(pages=3))


@pytest.mark.asyncio
async def test_the_parent_reads_at_most_the_result_cap():
    from backend.app.services.pdf_import.analysis import DocumentRefused
    from backend.app.services.pdf_import.sandbox import run_text_layer

    limits = dict(
        max_pages=30,
        max_pixels=60_000_000,
        timeout_s=60,
        memory_mb=1536,
        max_parallel=2,
    )
    result = await run_text_layer(documents.text_pdf(), **limits)
    assert result["pages"][0]["words"]
    with pytest.raises(DocumentRefused) as raised:
        await run_text_layer(
            documents.text_pdf(pages=3), max_result_bytes=500, **limits
        )
    assert raised.value.code == "too_complex"
