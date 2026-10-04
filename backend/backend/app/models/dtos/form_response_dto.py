from typing import Any, Dict, List, Optional

from common.models.standard_form import InternalAnswerMeta
from fastapi_camelcase import CamelModel

from backend.app.models.dtos.minified_form import FormDtoCamelModel
from backend.app.models.dtos.respondent_feedback_dto import StaffFeedback
from backend.app.models.dtos.response_dtos import (
    StandardFormFieldCamelModel,
    StandardFormResponseCamelModel,
)


class SingleSubmissionResponse(CamelModel):
    form: FormDtoCamelModel
    response: StandardFormResponseCamelModel
    # Workspace members only: the form's current internal fields (from the
    # latest published version, or the draft when never published), so staff
    # can fill in fields added after this response was submitted.
    internal_fields: Optional[List[StandardFormFieldCamelModel]] = None
    # Workspace members only: the updates posted for the respondent, with who
    # posted each (the respondent's own view is ``response.feedback``).
    feedback: Optional[StaffFeedback] = None


class InternalAnswersPatch(CamelModel):
    """Staff edit of a submission's internal answers.

    ``answers`` maps internal field id -> answer (the same shape as a
    respondent answer, e.g. ``{"text": "..."}``) or ``null`` to clear it.
    Fields not named are left untouched."""

    answers: Dict[str, Optional[Dict[str, Any]]]
    # The internal_answers_version the editor loaded (optimistic concurrency).
    version: Optional[int] = None


class InternalAnswersResponse(CamelModel):
    internal_answers: Dict[str, Any]
    internal_answers_meta: Dict[str, InternalAnswerMeta]
    internal_answers_version: int = 0
