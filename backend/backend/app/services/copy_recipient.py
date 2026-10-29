"""Who the "send me a copy" action may mail.

The ``creator_copy_mail`` action sends each new response to its
``Receiving Mail Address`` through the instance's mail server. That address is
the e-mail address of a current, enabled member of the form's workspace. The
form's creator counts like any member: their own address is allowed only
while they are still such a member, so a creator who was removed or disabled
stops receiving copies.

Anything else is refused, at save (:meth:`CopyRecipientService.ensure_allowed`,
a 422 with the stable code :data:`COPY_RECIPIENT_NOT_ALLOWED`) and again right
before sending (the actions executor asks ``POST
/temporal/workspaces/{id}/forms/{id}/copy-recipient``, which answers
:meth:`CopyRecipientService.is_allowed`). The second check is the one that
counts: a member (the creator included) removed or disabled after the action
was saved stops receiving copies.

Addresses are compared after trimming whitespace and case-folding the whole
address (:func:`normalize_address`). Plus tags and dots are *not* stripped: a
member's ``+tag`` address counts only when it matches exactly. The refusal
message names the rule and never lists members.
"""

from http import HTTPStatus
from typing import Any, Iterable, List, Optional, Set

from common.records import RecordId

from backend.app.exceptions import HTTPException
from backend.app.services.internal_auth import auth_service_headers
from backend.config import settings

#: the action this rule belongs to (``temporal/actions-executor``'s
#: ``PredefinedActions.CREATOR_COPY``)
CREATOR_COPY_ACTION = "creator_copy_mail"
#: the parameter the executor reads the recipient from
RECIPIENT_PARAMETER = "Receiving Mail Address"
COPY_RECIPIENT_NOT_ALLOWED = "copy_recipient_not_allowed"
COPY_RECIPIENT_MESSAGE = (
    "The receiving mail address must be the address of a member of this "
    "workspace or of the person who created the form."
)

_ADDRESS_MAX = 254
#: characters an address in a header or an address list could not carry
_FORBIDDEN = set('<>(),;:"\\[]')


def normalize_address(value: Any) -> Optional[str]:
    """``value`` trimmed and case-folded, or None when it cannot be one plain
    address: not text, empty, over 254 characters, not exactly one ``@`` with
    something on both sides, or holding whitespace, a control character, or
    one of ``<>(),;:"\\[]`` (so a second address, a display name or an extra
    header line never gets through)."""
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


def recipient_values(parameters: Optional[Iterable[Any]]) -> List[Optional[str]]:
    """The values the parameters give for the recipient (the parameter name
    compared ignoring case and surrounding space, as a looser reader would),
    empty ones left out: an empty recipient sends nothing."""
    values: List[Optional[str]] = []
    for parameter in parameters or []:
        name = getattr(parameter, "name", None)
        if not isinstance(name, str):
            continue
        if name.strip().casefold() != RECIPIENT_PARAMETER.casefold():
            continue
        value = getattr(parameter, "value", None)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        values.append(value)
    return values


def not_allowed() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={
            "code": COPY_RECIPIENT_NOT_ALLOWED,
            "message": COPY_RECIPIENT_MESSAGE,
        },
    )


class CopyRecipientService:
    def __init__(self, workspace_user_service, workspace_form_repository, http_client):
        self._workspace_users = workspace_user_service
        self._workspace_forms = workspace_form_repository
        self._http_client = http_client

    async def _allowed_addresses(self, workspace_id, form_id) -> Set[str]:
        """The normalised addresses allowed now: those of the workspace's
        members that are not disabled (the form's creator is one of them only
        while they are). Empty when the form does not belong to the workspace
        (nothing is allowed for a form that is not there)."""
        link = await self._workspace_forms.find_workspace_form(
            RecordId(str(workspace_id)), str(form_id)
        )
        if link is None:
            return set()
        user_ids = {
            str(member.user_id)
            for member in await self._workspace_users.get_users_in_workspace(
                workspace_id=RecordId(str(workspace_id))
            )
            if not member.disabled
        }
        if not user_ids:
            return set()
        response = await self._http_client.get(
            settings.auth_settings.BASE_URL + "/users",
            params={"user_ids": sorted(user_ids)},
            headers=auth_service_headers(),
        )
        allowed = set()
        for info in (response or {}).get("users_info") or []:
            address = normalize_address((info or {}).get("email"))
            if address:
                allowed.add(address)
        return allowed

    async def is_allowed(self, address: Any, workspace_id, form_id) -> bool:
        wanted = normalize_address(address)
        if wanted is None:
            return False
        return wanted in await self._allowed_addresses(workspace_id, form_id)

    async def ensure_allowed(self, address: Any, workspace_id, form_id) -> None:
        """Raise the 422 unless ``address`` may receive the form's copies."""
        if not await self.is_allowed(address, workspace_id, form_id):
            raise not_allowed()

    async def ensure_parameters_allowed(
        self, parameters: Optional[Iterable[Any]], workspace_id, form_id
    ) -> None:
        """Raise the 422 unless every recipient the parameters set may
        receive the form's copies. No recipient set, nothing to check."""
        values = recipient_values(parameters)
        if not values:
            return
        allowed = await self._allowed_addresses(workspace_id, form_id)
        for value in values:
            address = normalize_address(value)
            if address is None or address not in allowed:
                raise not_allowed()
