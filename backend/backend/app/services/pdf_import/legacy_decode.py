"""Decode text set in legacy (pre-Unicode) Devanagari fonts.

Fonts of the Preeti family (Preeti, Aakriti, …) draw Devanagari glyphs over
the codes of a Latin keyboard layout, so the PDF text layer says ``kl/ro``
where the page shows ``परिचय``. Decoding is three steps:

1. map each code (sometimes a pair) to its Devanagari sequence;
2. undo the visual order the layout stores: the i-matra (ि) is typed before
   the consonant cluster it follows, and the reph (र्) after the syllable it
   precedes;
3. normalise the compositions the layout builds out of parts (half form +
   ा stroke = full consonant; ा + े = ो; अ + ा = आ …).

Written from the layout itself for this project (Apache-2.0); the known
converters are GPL. ``plausibility`` scores a decoded string so the caller
can fall back to reading the page image when a font is not what its name
suggests.

Import-safe for the sandbox child: no imports from the backend package.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# --- Preeti layout -----------------------------------------------------------

# pairs first: the "m" stroke modifies the preceding glyph
_PREETI_PAIRS = {
    "km": "फ",
    "Km": "फ्",
    "Qm": "क्त",
    "qm": "क्र",
    "em": "झ",
    "Em": "झ्",
    "cf": "आ",
    "c]": "ओ",
    "c}": "औ",
    "O{": "ई",
    "P]": "ऐ",
}

_PREETI = {
    # unshifted number row: letters
    "1": "ज्ञ",
    "2": "द्द",
    "3": "घ",
    "4": "द्ध",
    "5": "छ",
    "6": "ट",
    "7": "ठ",
    "8": "ड",
    "9": "ढ",
    "0": "ण्",
    # shifted number row: digits
    "!": "१",
    "@": "२",
    "#": "३",
    "$": "४",
    "%": "५",
    "^": "६",
    "&": "७",
    "*": "८",
    "(": "९",
    ")": "०",
    "-": "(",
    "_": ")",
    "=": ".",
    "+": "ं",
    "q": "त्र",
    "Q": "त्त",
    "w": "ध",
    "W": "ध्",
    "e": "भ",
    "E": "भ्",
    "r": "च",
    "R": "च्",
    "t": "त",
    "T": "त्",
    "y": "थ",
    "Y": "थ्",
    "u": "ग",
    "U": "ग्",
    "i": "ष्",
    "I": "क्ष्",
    "o": "य",
    "O": "इ",
    "p": "उ",
    "P": "ए",
    "[": "ृ",
    "{": "र्",
    "]": "े",
    "}": "ै",
    "\\": "्",
    "|": "्र",
    "a": "ब",
    "A": "ब्",
    "s": "क",
    "S": "क्",
    "d": "म",
    "D": "म्",
    "f": "ा",
    "F": "ँ",
    "g": "न",
    "G": "न्",
    "h": "ज",
    "H": "ज्",
    "j": "व",
    "J": "व्",
    "k": "प",
    "K": "प्",
    "l": "ि",
    "L": "ी",
    "'": "ु",
    '"': "ू",
    ";": "स",
    ":": "स्",
    "z": "श",
    "Z": "श्",
    "x": "ह",
    "X": "ह्",
    "c": "अ",
    "C": "ऋ",
    "v": "ख",
    "V": "ख्",
    "b": "द",
    "B": "द्य",
    "n": "ल",
    "N": "ल्",
    "m": "ः",
    "M": ":",
    ",": ",",
    "<": "?",
    ".": "।",
    ">": "श्र",
    "/": "र",
    "?": "रु",
    "`": "ञ",
    "~": "ञ्",
    # Latin-1 range used by the layout for conjuncts and punctuation
    "«": "्र",
    "»": "्र",
    "Ø": "्य",
    "ª": "ङ्",
    "§": "ट्ट",
    "Ý": "ट्ठ",
    "å": "द्व",
    "ß": "द्म",
    "Í": "ङ्क",
    "Ë": "ङ्ग",
    "Î": "ङ्ख",
    "Ì": "न्न",
    "¿": "रू",
    "Å": "हृ",
    "˜": "ऽ",
    "ˆ": "फ्",
    "‰": "झ्",
    "Š": "घ्",
    "Œ": "त्त्",
    "¢": "द्घ",
    "£": "घ्",
    "¥": "र्",
    "°": "ङ्ग",
    "Ö": "=",
    "÷": "/",
    "×": "×",
    "Ù": ";",
    "Ú": "'",
    "Û": "!",
    "Ü": "%",
    "±": "+",
    "·": "ङ्ग",
    "“": "ँ",
    "\uf000": "फ्",
    # typographic quotes and dashes are real punctuation in these fonts: kept
}

_CONSONANT = "[क-हक़-य़]"
_CLUSTER = f"(?:{_CONSONANT}्)*{_CONSONANT}"
_MATRA = "[ा-ौॢॣ]"
_I_MATRA = "ि"
_REPH = "र्"

# the PDF may store other vowel signs between ि and its cluster; they stay put
_RE_I = re.compile(f"{_I_MATRA}({_MATRA}*)({_CLUSTER})")
_RE_REPH = re.compile(f"({_CLUSTER}{_MATRA}*[ँं]?){_REPH}")


def _map(text: str, table: dict, pairs: dict) -> str:
    out, i = [], 0
    while i < len(text):
        pair = text[i : i + 2]
        if pair in pairs:
            out.append(pairs[pair])
            i += 2
            continue
        ch = text[i]
        out.append(table.get(ch, ch))
        i += 1
    return "".join(out)


def _reorder(text: str) -> str:
    # ि is stored before its consonant cluster: move it after
    text = _RE_I.sub(lambda m: m.group(1) + m.group(2) + _I_MATRA, text)
    # र् (reph) is stored after its syllable: move it before
    text = _RE_REPH.sub(lambda m: _REPH + m.group(1), text)
    return text


def _normalise(text: str) -> str:
    text = text.replace("्ा", "")  # half form + ा stroke = full consonant
    for parts, whole in (
        ("ाे", "ो"),
        ("ेा", "ो"),  # ा + े = ो
        ("ाै", "ौ"),
        ("ैा", "ौ"),  # ा + ै = ौ
        ("अा", "आ"),
        ("आे", "ओ"),
        ("आै", "औ"),
        ("एे", "ऐ"),
        ("ंँ", "ँ"),
    ):
        text = text.replace(parts, whole)
    return unicodedata.normalize("NFC", text)


def decode_preeti(text: str) -> str:
    return _normalise(_reorder(_map(text, _PREETI, _PREETI_PAIRS)))


# font name fragment (lowercase) -> decoder
_DECODERS = {
    "preeti": decode_preeti,
    "aakriti": decode_preeti,
}


def decoder_for(font_name: str):
    name = (font_name or "").lower()
    for fragment, decoder in _DECODERS.items():
        if fragment in name:
            return decoder
    return None


# --- plausibility --------------------------------------------------------------

_DEVANAGARI = re.compile("[ऀ-ॿ]")
_BAD_START = re.compile(f"^{_MATRA}|^[ँ-ः्]")
_DOUBLE_MATRA = re.compile(f"{_MATRA}{_MATRA}")
_DANGLING_I = re.compile(f"{_I_MATRA}(?!$)(?={_CONSONANT})")


LEADING_SIGN = re.compile("^[\u093e-\u094c\u0901-\u0903\u094d\u0962\u0963]")


def starts_with_sign(word: str) -> bool:
    """A decoded word beginning with a vowel sign belongs to the previous word
    (the PDF put a gap inside the syllable)."""
    return bool(LEADING_SIGN.match(word))


def _word_ok(word: str) -> bool:
    letters = [
        c for c in word if c.isalpha() or unicodedata.category(c).startswith("M")
    ]
    if not letters:
        return True
    if not all(_DEVANAGARI.match(c) for c in letters):
        return False
    return not (_BAD_START.search(word) or _DOUBLE_MATRA.search(word))


def word_ok(word: str) -> bool:
    """Is this decoded word well-formed? Punctuation around it is ignored."""
    return _word_ok(word.strip(".,;:()[]{}'\"।?!/-‘’“”"))


def plausibility(decoded: str) -> float:
    """Share of words that are well-formed Devanagari (0..1). Latin-looking
    leftovers, matras at word starts and doubled vowel signs all count
    against it; digits and punctuation are neutral."""
    words = [w.strip(".,;:()[]{}'\"।?!/-") for w in decoded.split()]
    words = [w for w in words if any(c.isalpha() for c in w)]
    if not words:
        return 1.0
    return sum(_word_ok(w) for w in words) / len(words)


def decode_if_plausible(
    text: str, font_name: str, threshold: float = 0.85
) -> Optional[str]:
    decoder = decoder_for(font_name)
    if decoder is None:
        return None
    decoded = decoder(text)
    return decoded if plausibility(decoded) >= threshold else None
