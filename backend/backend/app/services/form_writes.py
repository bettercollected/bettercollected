"""The one write path for a form's content.

Everything that changes a form's content in the backend (AI chat edits,
review fixes, MCP ``update_form`` via ``persist_ops_to_form``, and the PDF
import's compile stage) saves through ``persist_form``, so checks or
sanitising added here cover every writer.
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from backend.app.schemas.standard_form import FormDocument

# the parts of a form its content writers may replace
FORM_PARTS = (
    "title",
    "description",
    "fields",
    "theme",
    "welcome_page",
    "thankyou_page",
)


async def persist_form(
    repo,
    form_document: FormDocument,
    new_form,
    *,
    parts: Sequence[str] = FORM_PARTS,
    guard: Optional[Callable[[FormDocument], bool]] = None,
) -> bool:
    """Copy ``parts`` of ``new_form`` onto the stored form and save it.

    With ``guard``, the form is read again right before writing and saved
    only if ``guard(current)`` holds (otherwise nothing is written and the
    result is False): a writer that worked on an older copy must not
    overwrite changes made since.
    """
    unknown = set(parts) - set(FORM_PARTS)
    if unknown:
        raise ValueError(f"not a form content part: {sorted(unknown)}")
    if guard is not None:
        current = await repo.get_form_document_by_id(form_document.form_id)
        if current is None or not guard(current):
            return False
        form_document = current
    for part in parts:
        setattr(form_document, part, getattr(new_form, part))
    await repo.save_form(form_document)
    return True
