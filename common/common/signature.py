"""What a ``signature`` answer may hold: a drawn image or a typed name.

An answer is ``{"type": "signature", "signature": {...}}`` with the slot
``StandardSignatureAnswer``:

- ``{"method": "typed", "name": "Fatima El Idrissi", "signedAt": "..."}``: the
  name is stored the way it is shown, trimmed, in Unicode form C, 1 to
  ``SIGNATURE_NAME_MAX`` characters, without control, format (zero-width,
  bidirectional marks, the byte order mark, the soft hyphen), line and
  paragraph separator, surrogate, private-use or unassigned characters, nor
  the invisible fillers (Hangul fillers, blank braille); with at least one
  letter or digit, and no more than four combining marks in a row;
- ``{"method": "drawn", "fileId": "<plain id>", "signedAt": "..."}``: the PNG
  itself is a private stored object under the response's folder (the
  uploaded-file store), never part of the answer.

``signedAt`` is stamped by the server when the answer is stored; a value the
client sends is ignored. The webapp keeps the same name rules
(``webapp/src/utils/signature.ts``). Nothing here claims a signature has any
legal weight: it records a drawn or typed name and does not check who signed.
"""

import re
import unicodedata
from typing import Optional

SIGNATURE_METHODS = ("drawn", "typed")
SIGNATURE_NAME_MAX = 100

# Control (Cc), format (Cf), line / paragraph separator (Zl, Zp), surrogate
# (Cs), private-use (Co) and unassigned (Cn) characters never belong in a name:
# they reverse or hide text in a view.
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp", "Cs", "Co", "Cn"})
# Characters that draw nothing but are letters or symbols to Unicode: the
# Hangul fillers and the blank braille pattern. A name made of them would look
# empty.
_INVISIBLE_FILLERS = frozenset({"\u115f", "\u1160", "\u3164", "\uffa0", "\u2800"})
# More combining marks than this in a row only stack on top of each other.
_MARKS_IN_A_ROW_MAX = 4

# The id of a drawn image is part of a storage key: a plain id only (the same
# rule as an uploaded file's, services/form_response_service.is_plain_file_id).
_PLAIN_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")


def has_forbidden_character(value: str) -> bool:
    return any(
        char in _INVISIBLE_FILLERS
        or unicodedata.category(char) in _FORBIDDEN_CATEGORIES
        for char in value
    )


def _marks_stack(value: str) -> bool:
    run = 0
    for char in value:
        run = run + 1 if unicodedata.category(char)[0] == "M" else 0
        if run > _MARKS_IN_A_ROW_MAX:
            return True
    return False


def _has_letter_or_digit(value: str) -> bool:
    return any(unicodedata.category(char)[0] in ("L", "N") for char in value)


def is_signature_name(value: object) -> bool:
    """Is ``value`` a well-formed typed name (the length is checked apart)?"""
    return (
        isinstance(value, str)
        and value != ""
        and value == value.strip()
        and unicodedata.is_normalized("NFC", value)
        and not has_forbidden_character(value)
        and _has_letter_or_digit(value)
        and not _marks_stack(value)
    )


def is_plain_image_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and _PLAIN_ID.fullmatch(value) is not None
        and value not in (".", "..")
    )


def normalised_name(value: str) -> Optional[str]:
    """What the respondent form stores for what was typed: trimmed, in form
    C, or None when that leaves nothing (or something forbidden)."""
    text = unicodedata.normalize("NFC", value.strip())
    return text if is_signature_name(text) else None
