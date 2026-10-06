"""Reading responses back in tests: responses belong to a workspace (#768)."""

from beanie import PydanticObjectId

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


def unlinked_scope(workspace_id, form_id: str) -> ResponseScope:
    """A form's responses in ``workspace_id``, stamped or not, whether or not the
    form is still linked (for checking that a deletion removed them)."""
    return ResponseScope(
        workspace_id=PydanticObjectId(workspace_id),
        form_ids=(str(form_id),),
        legacy_form_ids=(str(form_id),),
    )
