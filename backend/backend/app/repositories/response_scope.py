"""Which responses a workspace may read (#768).

A provider form (Google Forms, Typeform) can be linked to more than one
workspace, and its ``form_id`` is the provider's id, the same in each. A
response therefore belongs to the workspace it was collected in or imported
into, stored as its ``workspace_id``; every workspace-facing read filters on
``(workspace_id, form_id)``, never on ``form_id`` alone.

Responses stored before ``workspace_id`` existed carry none. Until the
backfill (``scripts/backfill_response_workspaces.py``) has stamped them, they
are read as the workspace's only where that is unambiguous: the form is linked
to this workspace and to no other (``legacy_form_ids``). Those of a form linked
to several workspaces stay hidden from all of them until the backfill has
attributed them.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Set, Tuple

from beanie import PydanticObjectId


@dataclass(frozen=True)
class ResponseScope:
    """The responses of ``form_ids`` that belong to ``workspace_id``."""

    workspace_id: PydanticObjectId
    form_ids: Tuple[str, ...]
    # forms linked to this workspace only: unstamped responses are its own
    legacy_form_ids: Tuple[str, ...] = ()

    def mongo_filter(self) -> Dict[str, Any]:
        """The Mongo query for responses (or deletion requests) in scope."""
        return {
            "$or": [
                {
                    "workspace_id": self.workspace_id,
                    "form_id": {"$in": list(self.form_ids)},
                },
                {
                    # null or missing: stored before #768
                    "workspace_id": None,
                    "form_id": {"$in": list(self.legacy_form_ids)},
                },
            ]
        }


def owners_by_form(workspace_forms: Iterable[Any]) -> Dict[str, Set[str]]:
    """form_id -> the ids of every workspace the form is linked to."""
    owners: Dict[str, Set[str]] = defaultdict(set)
    for workspace_form in workspace_forms:
        owners[str(workspace_form.form_id)].add(str(workspace_form.workspace_id))
    return owners


async def response_scope(
    workspace_form_repo, workspace_id: PydanticObjectId, form_ids: Iterable[str]
) -> ResponseScope:
    """The scope of ``workspace_id`` over ``form_ids`` (forms the caller has
    already checked belong to it); ``workspace_form_repo`` is the routed
    ``WorkspaceFormRepository``."""
    form_ids = tuple(dict.fromkeys(str(f) for f in form_ids))
    owners = (
        owners_by_form(
            await workspace_form_repo.get_workspace_forms_form_ids(list(form_ids))
        )
        if form_ids
        else {}
    )
    workspace = str(workspace_id)
    return ResponseScope(
        workspace_id=PydanticObjectId(workspace_id),
        form_ids=form_ids,
        legacy_form_ids=tuple(f for f in form_ids if owners.get(f) == {workspace}),
    )


async def response_in_workspace(
    workspace_form_repo, response: Optional[Any], workspace_id: PydanticObjectId
) -> bool:
    """Whether one stored response (or deletion request) belongs to
    ``workspace_id``: by its ``workspace_id``, or, stored before #768 without
    one, when its form is linked to this workspace and no other."""
    if response is None:
        return False
    stamped = getattr(response, "workspace_id", None)
    if stamped is not None:
        return str(stamped) == str(workspace_id)
    scope = await response_scope(workspace_form_repo, workspace_id, [response.form_id])
    return str(response.form_id) in scope.legacy_form_ids
