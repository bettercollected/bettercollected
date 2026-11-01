"""Layout containers on the server: the switch and the save-time checks.

A page's ``properties.containers`` (panels, field sets and tabs; the model is
``common.models.standard_form.LayoutContainer``, the structure rules are in
``common.layout_containers``) is layout only: the flat question list is what
answers, logic, rules and exports read.

**The switch** ``LAYOUT_CONTAINERS_ENABLED`` (off by default, until the release
that turns it on). While it is off, every write that gives a form a container
or changes one is refused with 422 ``layout_containers_disabled``: the
builder's save, the spec API, the edit operations (both engines), MCP and AI,
a template and an import all end in ``ensure_question_types_allowed`` (which
calls ``ensure_layout_allowed``) or, for operations, ``layout_problem``. What a
form already holds keeps working: it renders, a save that leaves a container
as it is passes, and a container may lose questions or go. Stored data is
never touched.

**The structure** is checked on every save (``ensure_valid_layout``): what a
removal or a move by a client that does not know containers broke is repaired
(a member that is gone, internal or in a group; an emptied container; one out
of page order; a question left between the members joins them), never refused;
what repair cannot mend (ids used twice, a question in two containers, members
not next to each other after an explicit write, logic reading a later
question) is 422 ``invalid_layout``.
"""

from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple

from backend.app.exceptions import HTTPException
from common.layout_containers import (
    all_containers,
    container_tabs,
    form_problems,
    members_of,
    repair_form,
)

LAYOUT_DISABLED_CODE = "layout_containers_disabled"
INVALID_LAYOUT_CODE = "invalid_layout"
PROBLEMS_MAX = 50

# Operations that can leave a container new or changed.
LAYOUT_OPS = frozenset(
    {
        "set_page_containers",
        "add_field",
        "add_group",
        "insert_field",
        "move_field",
        "replace_field",
        "add_page",
        "insert_page",
        "duplicate_page",
    }
)

LAYOUT_DISABLED_MESSAGE = (
    "Layout containers (panels, tabs and field sets) cannot be added or changed "
    "on this server yet (LAYOUT_CONTAINERS_ENABLED is off). Containers that a "
    "form already has are kept, and may lose questions or be removed."
)


def layout_containers_enabled() -> bool:
    """Is ``LAYOUT_CONTAINERS_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "LAYOUT_CONTAINERS_ENABLED", False))


def _shape(container: Any) -> str:
    """What makes a container the same one: everything but its members."""
    import json

    data = container.model_dump(mode="json", by_alias=True, exclude_none=True)
    data.pop("fields", None)
    for tab in data.get("tabs") or []:
        tab.pop("fields", None)
    return json.dumps(data, sort_keys=True, default=str)


def layout_signatures(form: Any) -> Dict[str, Tuple[str, List[frozenset]]]:
    """``{container id: (shape, [members of each tab])}`` of a form."""
    found: Dict[str, Tuple[str, List[frozenset]]] = {}
    for _, container in all_containers(form):
        found[str(container.id)] = (
            _shape(container),
            [
                frozenset(map(str, tab.fields or []))
                for tab in container_tabs(container)
            ],
        )
    return found


def new_or_changed_containers(
    form: Any, existing: Any = None, stored: Optional[dict] = None
) -> List[str]:
    """Ids of the containers of ``form`` that ``existing`` (the stored form,
    or None) does not have as they are, or with fewer questions. ``stored``
    is ``layout_signatures(existing)`` when the caller has it."""
    if stored is None:
        stored = layout_signatures(existing) if existing is not None else {}
    changed: List[str] = []
    for _, container in all_containers(form):
        before = stored.get(str(container.id))
        if before is None:
            changed.append(str(container.id))
            continue
        shape, tab_members = before
        now = [
            frozenset(map(str, tab.fields or [])) for tab in container_tabs(container)
        ]
        if (
            _shape(container) != shape
            or len(now) != len(tab_members)
            or any(not mine <= theirs for mine, theirs in zip(now, tab_members))
        ):
            changed.append(str(container.id))
    return changed


def ensure_layout_allowed(form: Any, existing: Any = None) -> None:
    """While the switch is off, refuse (422 ``layout_containers_disabled``) a
    save that brings a new container or changes one (anything but removing
    questions or the container). Containers stored and unchanged pass."""
    if layout_containers_enabled():
        return
    changed = new_or_changed_containers(form, existing)
    if changed:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": LAYOUT_DISABLED_CODE,
                "message": LAYOUT_DISABLED_MESSAGE,
                "errors": [
                    {
                        "containerId": container_id,
                        "message": f"The container '{container_id}' is new or changed.",
                    }
                    for container_id in changed[:PROBLEMS_MAX]
                ],
            },
        )


def layout_problem(form: Any, stored: dict, op_name: str) -> Optional[str]:
    """For the edit operations: the refusal an operation earns when it left
    ``form`` with a container that is new or changed against ``stored``
    (``layout_signatures`` of the form the batch started from), or None.
    Always None while the switch is on or for an operation that cannot do it."""
    if op_name not in LAYOUT_OPS or layout_containers_enabled():
        return None
    if new_or_changed_containers(form, None, stored):
        return LAYOUT_DISABLED_MESSAGE
    return None


def ensure_valid_layout(form: Any, drop: bool = True) -> int:
    """Repair what a removal or move broke in the form's containers (when
    ``drop``) and refuse what is still wrong (422 ``invalid_layout``). Returns
    how many things were repaired."""
    repaired = repair_form(form) if drop else 0
    problems = form_problems(form)
    if problems:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": INVALID_LAYOUT_CODE,
                "message": "The layout containers of this form are not valid.",
                "errors": [
                    {"pageId": page_id, "containerId": container_id, "message": message}
                    for page_id, container_id, message in problems[:PROBLEMS_MAX]
                ],
            },
        )
    return repaired


def layout_problem_texts(form: Any) -> List[str]:
    """The problems of the form's containers as plain sentences (the spec
    check and the operations use them)."""
    return [message for _, _, message in form_problems(form)]


def has_containers(form: Any) -> bool:
    return any(True for _ in all_containers(form))


def member_ids(form: Any) -> set:
    """Ids of every question that is in a container."""
    found: set = set()
    for _, container in all_containers(form):
        found.update(members_of(container))
    return found
