"""``insert_library_section`` for the edit operations.

The ops engine is pure and cannot read the library, so the writers that carry a
workspace (``persist_ops_to_form``: the chat, review fixes, accepted proposals,
MCP ``update_form``, the public API's ops and the builder's ops save; and the
dry runs) resolve the operation first:

1. ``fetch_fragments``: for each ``insert_library_section`` op, read the
   section **through the caller's workspace** and make its copy (new ids,
   references remapped, marker). A section that is not there, is another
   workspace's, or a switch that is off all give the same answer: nothing, and
   the op then fails alone with one plain message (it never says which).
2. ``substitute``: replace the op by the editor op ``splice_fields`` carrying
   that copy, so the engine's whole-save checks apply to it.
3. ``restore_names``: the results say ``insert_library_section`` again.

Nothing here is authorisation: the callers already hold ``form.edit`` for the
workspace (the ops write path), and ``fragments_for_ops`` still reads the section
only through that workspace.
"""

from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.services.reusable_sections import limits

LIBRARY_OP = "insert_library_section"
_GONE = (
    "That library section could not be inserted: it does not exist in this "
    "workspace, or reusable sections are not available here."
)


def _name(op: Any) -> Optional[str]:
    return op.get("op") if isinstance(op, dict) else getattr(op, "op", None)


def _get(op: Any, key: str, alias: str) -> Any:
    if isinstance(op, dict):
        return op.get(alias, op.get(key))
    return getattr(op, key, None)


def has_library_ops(ops: List[Any]) -> bool:
    return any(_name(op) == LIBRARY_OP for op in ops)


async def fetch_fragments(workspace_id, ops: List[Any], service) -> Dict[int, Any]:
    """``{op index: copy of the section, or the reason there is none}`` for each
    library op. The section is read once however many ops name it and the copies
    are made off the event loop (``ReusableSectionService.fragments_for_ops``).
    At most ``limits.LIBRARY_OPS_PER_BATCH`` library operations are resolved in a
    batch: beyond that the batch is refused whole (422 ``too_many_library_ops``)."""
    wanted: Dict[int, str] = {}
    for index, op in enumerate(ops):
        if _name(op) != LIBRARY_OP:
            continue
        section_id = _get(op, "section_id", "sectionId")
        wanted[index] = section_id if isinstance(section_id, str) else ""
    if len(wanted) > limits.LIBRARY_OPS_PER_BATCH:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": "too_many_library_ops",
                "message": f"At most {limits.LIBRARY_OPS_PER_BATCH} library sections can "
                "be inserted in one batch of operations; "
                f"this batch has {len(wanted)}. Split it.",
            },
        )
    if not wanted:
        return {}
    try:
        return await service.fragments_for_ops(workspace_id, wanted)
    except Exception as error:  # noqa: BLE001 - the ops then fail one by one
        logger.warning(
            "library sections could not be read for operations: {}",
            type(error).__name__,
        )
        return {index: _GONE for index in wanted}


def substitute(
    ops: List[Any], fragments: Dict[int, Any]
) -> Tuple[List[Any], Dict[int, str]]:
    """``ops`` with each resolved library op replaced by ``splice_fields``, and
    each one with no copy given the reason it failed. Returns the new list and
    ``{index: LIBRARY_OP}`` for the results."""
    from backend.app.services.ai.ops import EDITOR_CONTEXT, SpliceFieldsOp

    if not fragments:
        return ops, {}
    replaced: Dict[int, str] = {}
    out: List[Any] = []
    for index, op in enumerate(ops):
        fragment = fragments.get(index)
        if fragment is None:
            out.append(op)
            continue
        if isinstance(fragment, str):
            # the op stays and fails alone with this reason
            refused = op.model_copy()
            refused._refusal = fragment
            out.append(refused)
            continue
        out.append(
            SpliceFieldsOp.model_validate(
                {
                    "op": "splice_fields",
                    "pageId": op.page_id,
                    "index": op.index,
                    "fields": fragment.fields,
                    "containers": fragment.containers,
                },
                context={EDITOR_CONTEXT: True},
            )
        )
        replaced[index] = LIBRARY_OP
    return out, replaced


def restore_names(results: List[Any], replaced: Dict[int, str]) -> None:
    """Results of a batch that was resolved say what the caller asked for."""
    for result in results:
        name = replaced.get(result.index)
        if name is not None:
            result.op = name
