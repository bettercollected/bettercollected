"""Responses as API-key callers read them (MCP ``list_responses`` /
``get_response`` and the public REST API).

The same rules as the dashboard's staff view: only the workspace's own copy
of a response (#768), answers and internal answers decrypted on this read
path only, and a deletion request's status shown on the response it covers.
Who answered (``dataOwnerIdentifier``, the anonymous identity hash) and the
captured URL parameters are never returned: an integration gets answers, not
identities. Anonymised submissions keep no identity in the first place.
"""

import datetime as dt
import json
from typing import Any, Dict, List, Optional, Tuple

from beanie import PydanticObjectId
from common.services.crypto_service import crypto_service

from backend.app.repositories.response_scope import (
    find_response_in_workspace,
    response_scope,
)

MAX_PAGE_SIZE = 100


def _c():
    # Resolved at call time: the container imports services this module uses.
    from backend.app.container import container

    return container


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.isoformat()
    return str(value)


def _status(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _decrypted(workspace_id: PydanticObjectId, form_id: str, data: Any) -> dict:
    if isinstance(data, (bytes, str)):
        data = json.loads(
            crypto_service.decrypt(
                workspace_id=workspace_id, form_id=form_id, data=data
            )
        )
    # JSON-safe (dates and the like as text)
    return json.loads(json.dumps(data if isinstance(data, dict) else {}, default=str))


async def list_response_summaries(
    workspace_id: PydanticObjectId, form_id: str, limit: int, skip: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    """(summaries of one page, most recent first; the form's total). The
    caller has checked that the form belongs to the workspace."""
    limit = max(1, min(int(limit), MAX_PAGE_SIZE))
    skip = max(0, int(skip))
    scope = await response_scope(_c().workspace_form_repo(), workspace_id, [form_id])
    repo = _c().form_response_repo()
    responses = await repo.list_recent_by_form_id(scope, limit, skip)
    total = await repo.count_responses_for_form_ids(scope)
    requests = {
        r.response_id: r for r in await repo.list_deletion_requests_for_form_ids(scope)
    }
    items = []
    for response in responses:
        request = requests.get(response.response_id)
        items.append(
            {
                "responseId": response.response_id,
                "formId": response.form_id,
                "submittedAt": _iso(getattr(response, "created_at", None)),
                # Answers are encrypted at rest: the count of a ciphertext's
                # characters means nothing, so only count a readable dict.
                "answerCount": (
                    len(response.answers)
                    if isinstance(response.answers, dict)
                    else None
                ),
                "deletionRequest": (
                    {"status": _status(request.status)} if request else None
                ),
            }
        )
    return items, total


async def response_detail(
    workspace_id: PydanticObjectId, response_id: str
) -> Optional[Dict[str, Any]]:
    """One response of the workspace with its answers, or None when the
    workspace has no copy of it (or its form is not one of the workspace's)."""
    response = await find_response_in_workspace(
        _c().form_response_repo(),
        _c().workspace_form_repo(),
        workspace_id,
        response_id,
    )
    if response is None:
        return None
    association = (
        await _c()
        .workspace_form_repo()
        .find_workspace_form(workspace_id, str(response.form_id))
    )
    if association is None:
        return None
    request = await _c().form_response_repo().find_deletion_request_for(response)
    return {
        "responseId": response.response_id,
        "formId": response.form_id,
        "submittedAt": _iso(getattr(response, "created_at", None)),
        "answers": _decrypted(workspace_id, response.form_id, response.answers),
        # staff-entered values of the form's internal fields: the key's
        # creator holds response.read, so they are staff
        "internalAnswers": _decrypted(
            workspace_id, response.form_id, response.internal_answers
        ),
        "deletionRequest": {"status": _status(request.status)} if request else None,
    }
