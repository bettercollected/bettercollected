"""What a ``signature`` answer may hold: a drawn image or a typed name.

An answer is ``{"type": "signature", "signature": {...}}`` with the slot
``StandardSignatureAnswer``:

- ``{"method": "typed", "name": "Fatima El Idrissi", "signedAt": "..."}``: the
  name is stored the way it is shown, trimmed, in Unicode form C, 1 to
  ``SIGNATURE_NAME_MAX`` characters, without control, format (zero-width,
  bidirectional marks, the byte order mark, the soft hyphen) or line and
  paragraph separator characters;
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

# Control (Cc), format (Cf) and line / paragraph separator (Zl, Zp)
# characters never belong in a name: they reverse or hide text in a view.
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})

# The id of a drawn image is part of a storage key: a plain id only (the same
# rule as an uploaded file's, services/form_response_service.is_plain_file_id).
_PLAIN_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")


def has_forbidden_character(value: str) -> bool:
    return any(unicodedata.category(char) in _FORBIDDEN_CATEGORIES for char in value)


def is_signature_name(value: object) -> bool:
    """Is ``value`` a well-formed typed name (the length is checked apart)?"""
    return (
        isinstance(value, str)
        and value != ""
        and value == value.strip()
        and unicodedata.is_normalized("NFC", value)
        and not has_forbidden_character(value)
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
    return text if text and not has_forbidden_character(text) else None
