"""The body of a webhook delivery and its signature.

Pure functions. The body holds the mapped questions only (``data``, under the
key names the form's admin chose) and a few ids; nothing else about the
response leaves. Built at send time from the decrypted answers, never stored or
queued. The signature covers the exact bytes sent, bound to the timestamp so a
captured request cannot be replayed later:

    signature = "sha256=" + hex(HMAC_SHA256(secret, timestamp + "." + body))

Headers: ``X-Bettercollected-Signature``, ``-Timestamp`` (Unix seconds),
``-Delivery`` (one id for every attempt of one delivery, to drop a repeat) and
``-Event`` (``submission`` or ``test``).
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

from backend.app.services.registration import body as body_builder

SIGNATURE_HEADER = b"X-Bettercollected-Signature"
TIMESTAMP_HEADER = b"X-Bettercollected-Timestamp"
DELIVERY_HEADER = b"X-Bettercollected-Delivery"
EVENT_HEADER = b"X-Bettercollected-Event"
USER_AGENT = b"bettercollected-webhooks/1"
EVENT_SUBMISSION = "submission"
EVENT_TEST = "test"
MAX_BODY_BYTES = 1024 * 1024

KEY_PATTERN = body_builder.KEY_PATTERN


def files_unavailable(_file_id: str, _limit: int = 0) -> bytes:
    """Webhooks never carry files: a file question cannot be mapped, so this
    reader is never reached; it refuses if it ever is."""
    raise body_builder.FileMissing()


def sign(secret: str, timestamp: int, body: bytes) -> str:
    mac = hmac.new(
        secret.encode("utf-8"), f"{timestamp}.".encode("ascii") + body, hashlib.sha256
    )
    return "sha256=" + mac.hexdigest()


def verify(secret: str, timestamp: int, body: bytes, signature: str) -> bool:
    """What a receiver does (constant time); used by our tests and the docs."""
    return hmac.compare_digest(sign(secret, timestamp, body), signature or "")


def build_data(
    form: Any,
    mapping: Sequence[Tuple[str, str]],
    answers: Dict[str, Any],
    hidden_fields: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    """``{key: value}`` of the mapped questions of one response. A question the
    form no longer has is left out; a multiple choice question is a list of the
    chosen options' texts. The newer types follow the public API's answers
    (``registration/body.py`` ``scalar``): ``time`` "HH:MM", ``day`` a date,
    ``currency`` ``{"code", "amount"}`` (the amount a decimal string),
    ``date_range`` ``{"start", "end"}``, ``tags`` a list of strings, ``address``
    its six parts (``street``, ``house_number``, ``house_number_addition``,
    ``postcode``, ``city``, ``country``)."""
    index = body_builder.variables_of(form)
    values, _schema = body_builder.build_values(
        index,
        mapping,
        answers,
        hidden_fields,
        [source for source, _key in mapping],
        files_unavailable,
    )
    return values


def serialize(
    *,
    event: str,
    delivery_id: str,
    form_id: str,
    response_id: Optional[str],
    submitted_at: Optional[str],
    data: Dict[str, Any],
    source: Optional[str] = None,
) -> bytes:
    """``source``: ``"api"`` for a response an API key made; left out of the
    body for a respondent's (the key's id and name never leave)."""
    body = {
        "event": event,
        "delivery_id": delivery_id,
        "form_id": form_id,
        "response_id": response_id,
        "submitted_at": submitted_at,
        "data": data,
    }
    if source:
        body["source"] = source
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


_SAMPLES = {
    "short_text": "Example text",
    "long_text": "Example text on more than one line.",
    "email": "person@example.com",
    "url": "https://example.com",
    "phone_number": "+31 6 12345678",
    "number": 42,
    "rating": 4,
    "linear_rating": 4,
    "opinion_scale": 7,
    "yes_no": True,
    "date": "2026-01-31",
    "day": "2026-01-31",
    "time": "09:30",
    "date_range": {"start": "2026-01-31", "end": "2026-02-03"},
    "tags": ["example", "tags"],
    "address": {
        "street": "Example street",
        "house_number": "1",
        "house_number_addition": None,
        "postcode": "1234 AB",
        "city": "Example city",
        "country": "NL",
    },
    "calculated": 42,
}


def _multiple(field: Any) -> bool:
    properties = field.get("properties") if isinstance(field, dict) else getattr(field, "properties", None)
    if isinstance(properties, dict):
        return bool(properties.get("allow_multiple_selection"))
    return bool(getattr(properties, "allow_multiple_selection", False))


def _sample_currency(field: Any) -> str:
    """The question's default currency (the first it offers), else EUR."""
    offered = body_builder.currencies_of(field)
    return offered[0] if offered else "EUR"


def sample_data(form: Any, mapping: Iterable[Tuple[str, str]]) -> Dict[str, Any]:
    """Made-up values for a test event: never a real answer."""
    index = body_builder.variables_of(form)
    data: Dict[str, Any] = {}
    for source, key in mapping:
        variable = index.get(source)
        if variable is None or not variable.supported:
            continue
        if variable.kind == "hidden":
            data[key] = "example"
        elif variable.type == "group":
            data[key] = []
        elif variable.type in ("multiple_choice", "dropdown"):
            multiple = variable.type == "multiple_choice" and _multiple(variable.field)
            data[key] = ["Example option"] if multiple else "Example option"
        elif variable.type == "currency":
            data[key] = {"code": _sample_currency(variable.field), "amount": "12.50"}
        else:
            data[key] = copy.deepcopy(_SAMPLES.get(variable.type, "Example"))
    return data
