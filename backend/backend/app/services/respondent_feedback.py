"""Respondent feedback: staff updates on a submission that its respondent sees.

A form opts in (``WorkspaceFormSettings.respondent_feedback_enabled``, forms
built here only) and lists the statuses staff can give (``feedback_statuses``).
Workspace admins and the owner post an update: a status from that list and/or
a message. Updates are kept as history (``StandardFormResponse.
respondent_feedback``, appended only); the message is encrypted at rest with
the form's answers key and decrypted in ``decrypt_form_response``.

Who sees what:

- Workspace members see every update with who posted it (``staff_feedback``).
- The respondent sees the current status and every update with its date, the
  workspace as the author and never the staff member (``respondent_view``):
  on their submission page, on the public submission-number receipt (the same
  as the answers there) and, as the current status only, in "my submissions".
- The respondent view is included when the form has feedback on or when
  updates exist (turning it off stops new updates but keeps what was said).

Email: a notice with a link only, never the status or the message, sent when
the form requires a verified identity and the submitter is identified
(``dataOwnerIdentifier``, which anonymised submissions don't carry).

Helpers here work on pydantic models and raw dicts alike, like
``internal_fields``.
"""

from typing import Any, List, Optional

from common.models.standard_form import RespondentFeedback
from common.services.crypto_service import crypto_service

from backend.app.models.dtos.respondent_feedback_dto import (
    RespondentFeedbackEntry,
    RespondentFeedbackView,
    StaffFeedbackEntry,
)

FEEDBACK_KEY = "respondent_feedback"
_FEEDBACK_KEYS = (FEEDBACK_KEY, "respondentFeedback")


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def feedback_entries(response: Any) -> List[RespondentFeedback]:
    """The stored history of a response payload, as models."""
    for key in _FEEDBACK_KEYS:
        entries = _get(response, key)
        if entries:
            return [
                (
                    entry
                    if isinstance(entry, RespondentFeedback)
                    else RespondentFeedback.model_validate(entry)
                )
                for entry in entries
            ]
    return []


def encrypt_message(workspace_id, form_id: str, message: Optional[str]):
    if message is None:
        return None
    return crypto_service.encrypt(
        workspace_id=workspace_id, form_id=form_id, data=message
    )


def decrypt_message(workspace_id, form_id: str, message) -> Optional[str]:
    if message is None:
        return None
    if isinstance(message, (bytes, bytearray)):
        plain = crypto_service.decrypt(
            workspace_id=workspace_id, form_id=form_id, data=bytes(message)
        )
        return plain.decode("utf-8") if isinstance(plain, bytes) else plain
    return message


def decrypt_feedback(workspace_id, form_id: str, entries) -> List[RespondentFeedback]:
    """Copies of ``entries`` with their messages decrypted."""
    decrypted = []
    for entry in entries or []:
        entry = (
            entry
            if isinstance(entry, RespondentFeedback)
            else RespondentFeedback.model_validate(entry)
        )
        decrypted.append(
            entry.model_copy(
                update={
                    "message": decrypt_message(workspace_id, form_id, entry.message)
                }
            )
        )
    return decrypted


def current_status(entries: List[RespondentFeedback]) -> Optional[str]:
    """The status of the latest update that gave one: a message-only update
    keeps the status as it was."""
    for entry in reversed(entries or []):
        if entry.status:
            return entry.status
    return None


def staff_feedback(entries: List[RespondentFeedback]) -> List[StaffFeedbackEntry]:
    """For workspace members: every update with who posted it. Messages must
    already be decrypted."""
    return [
        StaffFeedbackEntry(
            id=entry.id,
            status=entry.status,
            message=_text(entry.message),
            created_at=entry.created_at,
            created_by=entry.created_by,
            created_by_email=entry.created_by_email,
        )
        for entry in entries or []
    ]


def respondent_view(
    entries: List[RespondentFeedback],
    author: Optional[str],
    with_entries: bool = True,
) -> RespondentFeedbackView:
    """For the respondent: the organisation as the author, no staff identity.
    Messages must already be decrypted."""
    return RespondentFeedbackView(
        author=author,
        current_status=current_status(entries),
        updated_at=entries[-1].created_at if entries else None,
        entries=(
            [
                RespondentFeedbackEntry(
                    status=entry.status,
                    message=_text(entry.message),
                    created_at=entry.created_at,
                )
                for entry in entries
            ]
            if with_entries
            else None
        ),
    )


def present_to_respondent(
    response: Any,
    author: Optional[str],
    enabled: bool,
    with_entries: bool = True,
) -> Any:
    """Replace the stored history on a respondent-facing response payload by
    the respondent view (in place; returns the payload). Messages must already
    be decrypted (``decrypt_form_response``)."""
    entries = feedback_entries(response)
    view = (
        respondent_view(entries, author, with_entries) if entries or enabled else None
    )
    if isinstance(response, dict):
        for key in _FEEDBACK_KEYS:
            response.pop(key, None)
        response["feedback"] = (
            view.model_dump(mode="json", by_alias=True) if view else None
        )
    else:
        if hasattr(response, FEEDBACK_KEY):
            setattr(response, FEEDBACK_KEY, None)
        setattr(response, "feedback", view)
    return response


def emails_respondent(form_settings: Any, response: Any) -> bool:
    """Whether a new update emails the respondent: only when the form
    requires a verified identity and the submitter is identified (an
    anonymised submission keeps no ``dataOwnerIdentifier``)."""
    owner = _get(response, "dataOwnerIdentifier")
    return bool(
        _get(form_settings, "require_verified_identity")
        and isinstance(owner, str)
        and "@" in owner
    )


def _text(message) -> Optional[str]:
    # an undecrypted message must never be shown as if it were text
    return message if isinstance(message, str) else None
