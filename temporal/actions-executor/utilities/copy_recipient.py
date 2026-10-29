"""Who the "send me a copy" action (``creator_copy_mail``) may mail.

The backend refuses any other address when the action is saved
(``backend/app/services/copy_recipient.py``), but a membership can end after
that, so the executor asks again right before it sends: the address must be
that of a current, enabled member of the form's workspace (the form's creator
only while they are one). The
executor has no database access to workspaces, so it asks the backend's
in-network route (``POST /temporal/workspaces/{id}/forms/{id}/copy-recipient``,
the ``api-key`` it already uses for the secrets route), which answers yes or no
and never lists anyone.

Addresses are compared after trimming whitespace and case-folding the whole
address; plus tags and dots are kept. Nothing here puts an address in a log
line or an exception message: both name the action and the form by id only.
"""

import logging
from typing import Any, Optional

import httpx

from settings.application import settings

logger = logging.getLogger(__name__)

NOT_ALLOWED_CODE = "copy_recipient_not_allowed"
_ADDRESS_MAX = 254
_FORBIDDEN = set('<>(),;:"\\[]')
_TIMEOUT_SECONDS = 10


class CopyRecipientError(Exception):
    """The copy is not sent. The message never holds an address."""


class CopyRecipientRefused(CopyRecipientError):
    """The address is not that of a current member of the workspace."""


class CopyRecipientUnavailable(CopyRecipientError):
    """Whether the address is allowed could not be found out; nothing is sent."""


def normalize_address(value: Any) -> Optional[str]:
    """``value`` trimmed and case-folded, or None when it is not one plain
    address: not text, empty, over 254 characters, not exactly one ``@`` with
    something on both sides, or holding whitespace, a control character or one
    of ``<>(),;:"\\[]`` (a second address, a display name or an extra header
    line never gets through)."""
    if not isinstance(value, str):
        return None
    address = value.strip().casefold()
    if not address or len(address) > _ADDRESS_MAX:
        return None
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in address):
        return None
    if any(ch in _FORBIDDEN for ch in address):
        return None
    local, separator, domain = address.partition("@")
    if not separator or not local or not domain or "@" in domain:
        return None
    return address


def approved_copy_recipient(
    address: Any,
    workspace_id: Any,
    form_id: Any,
    action_id: Any = None,
) -> str:
    """The normalised address to send to, when it may receive the form's
    copies now. Raises :class:`CopyRecipientRefused` when it may not and
    :class:`CopyRecipientUnavailable` when that cannot be found out (the
    backend is unreachable or answers something unexpected): fail closed."""
    where = f"action={action_id} form={form_id}"
    normalized = normalize_address(address)
    if normalized is None:
        logger.warning(
            "creator_copy_mail not sent: the address is not valid (%s)", where
        )
        raise CopyRecipientRefused(
            f"{NOT_ALLOWED_CODE}: the receiving address is not a valid single address"
        )
    if not workspace_id or not form_id:
        logger.warning("creator_copy_mail not sent: no workspace or form (%s)", where)
        raise CopyRecipientUnavailable(
            "the receiving address cannot be checked: the job names no workspace or form"
        )
    try:
        response = httpx.post(
            # in-network (SERVER_URL), never the public BACKEND_URL: the
            # backend refuses its internal routes through the public ingress
            url=f"{settings.server_url}/temporal/workspaces/{workspace_id}"
            f"/forms/{form_id}/copy-recipient",
            headers={"api-key": settings.api_key},
            json={"address": normalized},
            timeout=_TIMEOUT_SECONDS,
        )
        answer = response.json() if response.status_code == 200 else None
    except (httpx.HTTPError, ValueError) as error:
        logger.warning(
            "creator_copy_mail not sent: the check failed (%s, %s)",
            type(error).__name__,
            where,
        )
        raise CopyRecipientUnavailable(
            "the receiving address could not be checked; nothing was sent"
        ) from None
    if not isinstance(answer, dict) or not isinstance(answer.get("allowed"), bool):
        logger.warning(
            "creator_copy_mail not sent: the check answered %s (%s)",
            response.status_code,
            where,
        )
        raise CopyRecipientUnavailable(
            "the receiving address could not be checked; nothing was sent"
        )
    if not answer["allowed"]:
        logger.warning(
            "creator_copy_mail not sent: the address is no member of the "
            "workspace (%s)",
            where,
        )
        raise CopyRecipientRefused(
            f"{NOT_ALLOWED_CODE}: the receiving address is not a member of the "
            "workspace"
        )
    return normalized
