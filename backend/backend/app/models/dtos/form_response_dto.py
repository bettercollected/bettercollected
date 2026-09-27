from typing import Any, Dict, List, Optional

from common.models.standard_form import InternalAnswerMeta
from fastapi_camelcase import CamelModel

from backend.app.models.dtos.minified_form import FormDtoCamelModel
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


class InternalAnswersPatch(CamelModel):
    """Staff edit of a submission's internal answers.

    ``answers`` maps internal field id -> answer (the same shape as a
    respondent answer, e.g. ``{"text": "..."}``) or ``null`` to clear it.
    Fields not named are left untouched."""

    answers: Dict[str, Optional[Dict[str, Any]]]


class InternalAnswersResponse(CamelModel):
    internal_answers: Dict[str, Any]
    internal_answers_meta: Dict[str, InternalAnswerMeta]
