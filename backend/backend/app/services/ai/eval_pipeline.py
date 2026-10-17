"""A model reply through the real pipeline, then the quality checks.

Shared by the offline golden tests (``tests/app/services/test_ai_eval_fixtures.py``)
and the opt-in live runner (``scripts/ai_eval.py``), so both judge a reply
exactly as the product would turn it into a form:

- form generation: ``parse_generated_form`` (structured.py) →
  ``OpenAIService.convert_openai_form_to_standard_form`` → ``StandardForm``;
- chat editing: the chat turn's reply model → ``apply_form_ops`` (ops.py).

Nothing here calls a provider.
"""

import json
from typing import Any, Dict, List, Optional, Tuple, Union

from common.models.standard_form import StandardForm

from backend.app.services.ai.chat import _ChatTurnReply
from backend.app.services.ai.ops import OpResult, apply_form_ops
from backend.app.services.ai.quality import (
    QualityOptions,
    QualityReport,
    check_form_quality,
)
from backend.app.services.ai.structured import parse_generated_form, parse_reply

GENERATE = "generate"
CHAT = "chat"


def reply_text(reply: Union[str, Dict[str, Any]]) -> str:
    """A recorded reply as the text a provider returns."""
    return reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)


def _converter():
    from backend.app.container import container

    return container.openai_service()


def form_from_generation(raw: Dict[str, Any]) -> StandardForm:
    """A validated generation reply as the form the product would save."""
    form = _converter().convert_openai_form_to_standard_form(openai_form=raw)
    return StandardForm.model_validate(form.model_dump())


def generation_reply_to_form(
    reply: Union[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], StandardForm]:
    """(validated reply, form); ``InvalidReply`` when it is not a form."""
    raw = parse_generated_form(reply_text(reply))
    return raw, form_from_generation(raw)


def chat_reply_to_form(
    base_form: Union[StandardForm, Dict[str, Any]],
    reply: Union[str, Dict[str, Any]],
) -> Tuple[StandardForm, List[OpResult]]:
    """The base form with a chat turn's ops applied; ``InvalidReply`` when
    the reply does not fit the turn's shape."""
    base = (
        base_form
        if isinstance(base_form, StandardForm)
        else StandardForm.model_validate(base_form)
    )
    turn = parse_reply(reply_text(reply), _ChatTurnReply)
    return apply_form_ops(base, turn._parsed_ops)


def options_for(case: Dict[str, Any]) -> QualityOptions:
    """Quality options from a fixture or prompt entry."""
    kwargs: Dict[str, Any] = {
        "language": case.get("language"),
        "theme_requested": bool(case.get("theme_requested")),
    }
    if case.get("max_questions_per_page"):
        kwargs["max_questions_per_page"] = int(case["max_questions_per_page"])
    if case.get("max_questions"):
        kwargs["max_questions"] = int(case["max_questions"])
    if case.get("expected_types"):
        kwargs["expected_types"] = frozenset(case["expected_types"])
    return QualityOptions(**kwargs)


def score(
    form: StandardForm,
    case: Dict[str, Any],
    raw: Optional[Dict[str, Any]] = None,
) -> QualityReport:
    return check_form_quality(form, options_for(case), raw=raw)
