"""Recover the text layer: every word with its box, font, size, weight and
colour, legacy-font words decoded to Unicode.

Import-safe for the sandbox child: no imports from the backend package.
Words keep the document's own characters (principle: labels, options and
legal text must come from the document); only legacy-font words are
transformed, and only by a decoder whose output passed the plausibility check.
"""

from __future__ import annotations

import io
import unicodedata
from typing import Dict, List, Optional

from .fonts import base_font_name, is_legacy_font
from .legacy_decode import decoder_for, plausibility, starts_with_sign, word_ok

# decoded legacy text on a page must score at least this to be trusted
PAGE_PLAUSIBILITY = 0.9
# a page with a larger share of untrusted words is read from its image instead
PAGE_UNTRUSTED_SHARE_FOR_VISION = 0.1
LINE_TOLERANCE = 2.0
# a dense page of legal terms has ~1,500 words; these caps are far above real forms
MAX_WORDS_PER_PAGE = 5_000
MAX_WORDS_PER_DOCUMENT = 50_000
MAX_WORD_CHARS = 200


class TooMuchText(Exception):
    """More text than any form: refused rather than silently cut."""


def colour_hex(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        value = (value,)
    value = tuple(value)
    if len(value) == 1:
        value = value * 3
    elif len(value) == 4:  # CMYK
        c, m, y, k = value
        value = ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
    if len(value) != 3:
        return None
    try:
        return "#%02x%02x%02x" % tuple(
            max(0, min(255, round(float(v) * 255))) for v in value
        )
    except (TypeError, ValueError):
        return None


def script_of(text: str) -> str:
    counts: Dict[str, int] = {}
    for ch in text:
        if ch.isalpha() or unicodedata.category(ch).startswith("M"):
            name = unicodedata.name(ch, "")
            script = (
                "devanagari"
                if "DEVANAGARI" in name
                else ("latin" if "LATIN" in name else "other")
            )
            counts[script] = counts.get(script, 0) + 1
    if not counts:
        return "digits" if any(ch.isdigit() for ch in text) else "symbols"
    return max(counts, key=counts.get)


def _is_bold(font: str) -> bool:
    lower = font.lower()
    return (
        "bold" in lower or "black" in lower or "heavy" in lower or lower.endswith(",b")
    )


def _merge(a: dict, b: dict) -> dict:
    a = dict(a)
    a["text"] += b["text"]
    a["x0"], a["top"] = min(a["x0"], b["x0"]), min(a["top"], b["top"])
    a["x1"], a["bottom"] = max(a["x1"], b["x1"]), max(a["bottom"], b["bottom"])
    return a


def _lines(words: List[dict]) -> List[List[dict]]:
    lines: List[List[dict]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(lines[-1][0]["top"] - word["top"]) <= LINE_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])
    return lines


def _resource_legacy_font(page) -> Optional[str]:
    """The page's only legacy font, from its resource dictionary. pdfminer names
    fonts without a descriptor "unknown"; the resources still name them."""
    try:
        from pdfminer.pdftypes import resolve1

        fonts = resolve1((page.page_obj.resources or {}).get("Font")) or {}
        names = set()
        for ref in fonts.values():
            base = resolve1(ref).get("BaseFont")
            name = getattr(base, "name", base)
            if isinstance(name, bytes):
                name = name.decode("latin-1")
            if name and is_legacy_font(str(name)):
                names.add(base_font_name(str(name)))
        return names.pop() if len(names) == 1 else None
    except Exception:  # noqa: BLE001 — a broken resource dictionary is ignored
        return None


def page_words(page) -> dict:
    """Words of one pdfplumber page, legacy fonts decoded when plausible."""
    raw = page.dedupe_chars().extract_words(
        extra_attrs=["fontname", "size", "non_stroking_color"],
        keep_blank_chars=False,
        use_text_flow=False,
    )
    if len(raw) > MAX_WORDS_PER_PAGE:
        raise TooMuchText()
    fallback_font = _resource_legacy_font(page)
    words: List[dict] = []
    legacy_raw: List[str] = []
    legacy_decoded: List[str] = []
    for w in raw:
        font = base_font_name(w.get("fontname", ""))
        if font == "unknown" and fallback_font:
            font = fallback_font
        text = w["text"][:MAX_WORD_CHARS]
        source = "text"
        if is_legacy_font(font):
            decoder = decoder_for(font)
            if decoder is None:
                source = "untrusted"
            else:
                decoded = decoder(text)
                legacy_raw.append(text)
                legacy_decoded.append(decoded)
                text, source = decoded, "decoded"
        word = {
            "text": text,
            "x0": round(float(w["x0"]), 2),
            "top": round(float(w["top"]), 2),
            "x1": round(float(w["x1"]), 2),
            "bottom": round(float(w["bottom"]), 2),
            "font": font[:64],
            "size": round(float(w.get("size") or 0), 2),
            "bold": _is_bold(font),
            "colour": colour_hex(w.get("non_stroking_color")),
            "source": source,
        }
        prev = words[-1] if words else None
        if (
            source == "decoded"
            and prev is not None
            and prev["source"] == "decoded"
            and starts_with_sign(text)
            and abs(prev["top"] - word["top"]) < 2
        ):
            words[-1] = _merge(prev, word)  # a vowel sign split off its syllable
            continue
        words.append(word)
    score = plausibility(" ".join(legacy_decoded)) if legacy_decoded else None
    trusted = score is None or score >= PAGE_PLAUSIBILITY
    if not trusted:
        for word in words:
            if word["source"] == "decoded":
                word["source"] = "untrusted"
    else:
        # a malformed decoded word taints its whole line: glyph order inside
        # justified text can be scrambled, and neighbours may be wrong too
        for line in _lines(words):
            if any(w["source"] == "decoded" and not word_ok(w["text"]) for w in line):
                for w in line:
                    if w["source"] == "decoded":
                        w["source"] = "untrusted"
    for word in words:
        word["script"] = script_of(word["text"])
    untrusted = sum(1 for w in words if w["source"] == "untrusted")
    return {
        "words": words,
        "read_from_image": bool(words)
        and untrusted / len(words) > PAGE_UNTRUSTED_SHARE_FOR_VISION,
        "legacy_words": len(legacy_raw),
        "decoded_plausibility": None if score is None else round(score, 3),
        "decoded_trusted": trusted,
        "untrusted_words": untrusted,
    }


def extract_text_layer(data: bytes, skip_pages: Optional[set] = None) -> dict:
    import pdfplumber

    pages = []
    total = 0
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for index, page in enumerate(pdf.pages):
            number = index + 1
            if skip_pages and number in skip_pages:
                pages.append({"number": number, "skipped": True, "words": []})
                continue
            pages.append(
                {
                    "number": number,
                    "skipped": False,
                    "width": float(page.width),
                    "height": float(page.height),
                    **page_words(page),
                }
            )
            total += len(pages[-1]["words"])
            if total > MAX_WORDS_PER_DOCUMENT:
                raise TooMuchText()
    return {"pages": pages}
