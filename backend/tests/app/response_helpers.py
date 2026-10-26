"""Reading responses back in tests: responses belong to a workspace (#768)."""

from common.ids import RecordId

from backend.app.container import container
from backend.app.repositories.response_scope import ResponseScope, response_scope


async def form_scope(form_id: str, workspace_id=None) -> ResponseScope:
    """The scope a form's own workspace reads it with (the first workspace it
    is linked to unless ``workspace_id`` is given)."""
    if workspace_id is None:
        links = await container.workspace_form_repo().get_workspace_forms_form_ids(
            [form_id]
        )
        workspace_id = links[0].workspace_id
    return await response_scope(
        container.workspace_form_repo(), workspace_id, [form_id]
    )


async def deletion_requests_of(workspace_id, form_id: str, response_id: str) -> list:
    """The deletion requests stored for ``response_id`` in ``workspace_id`` (or
    stored without a workspace), read from the read store."""
    requests = await container.form_response_repo().list_deletion_requests_for_form_ids(
        unlinked_scope(workspace_id, form_id)
    )
    return [r for r in requests if r.response_id == str(response_id)]


async def deletion_request_of(workspace_id, form_id: str, response_id: str):
    """The one deletion request of ``response_id`` in ``workspace_id``, or None."""
    requests = await deletion_requests_of(workspace_id, form_id, response_id)
    assert len(requests) <= 1, requests
    return requests[0] if requests else None


def unlinked_scope(workspace_id, form_id: str) -> ResponseScope:
    """A form's responses in ``workspace_id``, stamped or not, whether or not the
    form is still linked (for checking that a deletion removed them)."""
    return ResponseScope(
        workspace_id=RecordId(workspace_id),
        form_ids=(str(form_id),),
        legacy_form_ids=(str(form_id),),
    )
