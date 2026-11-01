"""The signed link to a job's file.

``<expiry>.<HMAC-SHA256>`` over the export's id, workspace, form, the
requester's id and the expiry, under a key derived from the server's secret
with a label of its own:

* **Bound to the export and the user.** The signature covers both ids, so a
  link cannot be used for another export, and it belongs to the requester: the
  download route also needs that user's sign-in and refuses a link made for
  someone else.
* **Short-lived.** ``LINK_TTL_SECONDS`` after it was issued. The status of an
  export that is ready issues a fresh one, so a reader who is still entitled
  gets a new link; a copied or logged one is useless minutes later.
* **Not a credential on its own.** The file is delivered only to the signed-in
  requester who still holds ``response.export``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Optional

LABEL = b"bettercollected/response-export/link/v1"
LINK_TTL_SECONDS = 5 * 60
VALID, EXPIRED, INVALID = "valid", "expired", "invalid"


def _keys() -> list:
    """One signing key per member of the JWT key ring (current first;
    docs/auth-key-rotation.md): the first signs, every one verifies."""
    from common.settings import key_ring

    from backend.config import settings

    members = key_ring.token_members(settings.auth_settings.JWT_SECRET)
    if not members:
        raise RuntimeError("AUTH_JWT_SECRET is not set: no export link can be signed")
    return key_ring.derive_all(members, LABEL)


def _sign(export_id, workspace_id, form_id, user_id, expiry: int, key=None) -> str:
    message = json.dumps(
        [str(export_id), str(workspace_id), str(form_id), str(user_id), expiry]
    ).encode()
    return hmac.new(key or _keys()[0], message, hashlib.sha256).hexdigest()


def issue(export_id, workspace_id, form_id, user_id, now: Optional[float] = None) -> str:
    expiry = int((time.time() if now is None else now) + LINK_TTL_SECONDS)
    return f"{expiry}.{_sign(export_id, workspace_id, form_id, user_id, expiry)}"


def check(
    token: str,
    export_id,
    workspace_id,
    form_id,
    user_id,
    now: Optional[float] = None,
) -> str:
    """``VALID``, ``EXPIRED`` (ours, past its time) or ``INVALID`` (anything
    else: malformed, another export, another user, tampered)."""
    expiry_text, _, signature = (token or "").partition(".")
    if not expiry_text.isascii() or not expiry_text.isdigit() or not signature:
        return INVALID
    expiry = int(expiry_text)
    right = False
    for key in _keys():
        expected = _sign(export_id, workspace_id, form_id, user_id, expiry, key)
        right = hmac.compare_digest(signature.encode(), expected.encode()) or right
    if not right:
        return INVALID
    return EXPIRED if (time.time() if now is None else now) > expiry else VALID
