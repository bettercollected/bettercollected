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
workspace (the ops write path), and ``fragment_for_ops`` still reads the section
only through that workspace.
"""

from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from backend.app.exceptions import HTTPException

LIBRARY_OP = "insert_library_section"


def _name(op: Any) -> Optional[str]:
    return op.get("op") if isinstance(op, dict) else getattr(op, "op", None)


def _get(op: Any, key: str, alias: str) -> Any:
    if isinstance(op, dict):
        return op.get(alias, op.get(key))
    return getattr(op, key, None)


def has_library_ops(ops: List[Any]) -> bool:
    return any(_name(op) == LIBRARY_OP for op in ops)


async def fetch_fragments(workspace_id, ops: List[Any], service) -> Dict[int, Any]:
    """``{op index: copy of the section}`` for each library op that resolves."""
    found: Dict[int, Any] = {}
    for index, op in enumerate(ops):
        if _name(op) != LIBRARY_OP:
            continue
        section_id = _get(op, "section_id", "sectionId")
        if not isinstance(section_id, str):
            continue
        try:
            found[index] = await service.fragment_for_ops(workspace_id, section_id)
        except HTTPException:
            # not found, not this workspace's, or the switch is off: the op fails
            continue
        except Exception as error:  # noqa: BLE001 - one bad section fails one op
            logger.warning(
                "library section could not be read for an operation: {}",
                type(error).__name__,
            )
    return found


def substitute(
    ops: List[Any], fragments: Dict[int, Any]
) -> Tuple[List[Any], Dict[int, str]]:
    """``ops`` with each resolved library op replaced by ``splice_fields``.
    Returns the new list and ``{index: LIBRARY_OP}`` for the results."""
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
