"""Model replies that must be JSON of a known shape.

Every reply is validated with a Pydantic model. When it does not fit, the
model gets one more turn with the problems listed (locations and messages
only, never the values) and a reply that still does not fit fails cleanly
with ``ai_unusable`` instead of reaching the form. Providers that support it
are also asked for JSON mode or a strict JSON schema, so the retry is rare.
"""

from typing import Any, Callable, Dict, List, Literal, Optional, Type, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.app.services.ai.errors import ai_unusable

T = TypeVar("T", bound=BaseModel)

MAX_PROBLEMS = 20


class InvalidReply(Exception):
    """A reply that is no JSON object or does not fit its model."""

    def __init__(self, problems: List[str]):
        super().__init__(f"{len(problems)} problem(s)")
        self.problems = problems


def extract_json_object(text: str) -> dict:
    """Tolerant parse of a reply into a JSON object: strips markdown fences
    and trailing prose; ValueError when no object can be recovered."""
    import json

    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("The model reply contained no JSON object.")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(cleaned[start:])
    if not isinstance(obj, dict):
        raise ValueError("The model reply was not a JSON object.")
    return obj


def problems_of(error: Exception) -> List[str]:
    """What was wrong, as locations and messages without the values."""
    if isinstance(error, InvalidReply):
        return error.problems
    if isinstance(error, ValidationError):
        problems = []
        for item in error.errors(include_input=False, include_url=False):
            location = ".".join(str(part) for part in item.get("loc", ())) or "reply"
            problems.append(f"{location}: {item.get('msg', 'invalid')}")
        return problems[:MAX_PROBLEMS] or ["the reply does not fit the format"]
    if isinstance(error, ValueError):
        # json.JSONDecodeError and our own messages carry positions, no content
        return [str(error).split("\n")[0][:200] or "the reply is not valid JSON"]
    return ["the reply is not valid JSON"]


def correction_message(problems: List[str]) -> str:
    return (
        "Your previous reply could not be used. Problems:\n- "
        + "\n- ".join(problems[:MAX_PROBLEMS])
        + "\nReply again with only the corrected JSON object, nothing else."
    )


def parse_reply(text: str, model: Type[T], nulls_absent: bool = False) -> T:
    """The reply as ``model``; InvalidReply when it is not. With
    ``nulls_absent`` (a strict schema's nullable keys) null means absent;
    otherwise null keeps its meaning (``"logic": null`` clears)."""
    try:
        data = extract_json_object(text)
        return model.model_validate(drop_nulls(data) if nulls_absent else data)
    except (ValidationError, ValueError) as error:
        raise InvalidReply(problems_of(error)) from None


def drop_nulls(value: Any) -> Any:
    """Strict JSON schemas make optional keys nullable: null means absent."""
    if isinstance(value, dict):
        return {k: drop_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [drop_nulls(v) for v in value]
    return value


async def chat_structured(
    provider,
    system: str,
    messages: List[Dict[str, Any]],
    parse: Callable[[str], T],
    *,
    max_output_tokens: int,
    unusable_message: Optional[str] = None,
    json_schema: Optional[Dict[str, Any]] = None,
) -> T:
    """One chat call whose reply ``parse`` accepts (it raises InvalidReply
    otherwise), retried once with the problems; ``ai_unusable`` when the
    retry is not accepted either. ``json_schema`` ({"name", "schema"}, a
    strict schema) is passed to providers that support structured output;
    the others are asked for JSON mode and rely on ``parse``."""
    options: Dict[str, Any] = {"max_output_tokens": max_output_tokens, "json_mode": True}
    if json_schema is not None:
        options["json_schema"] = json_schema
    raw = await provider.chat(system, messages, **options)
    try:
        return parse(raw)
    except InvalidReply as invalid:
        problems = invalid.problems
    retry = list(messages) + [
        {"role": "assistant", "content": raw or ""},
        {"role": "user", "content": correction_message(problems)},
    ]
    raw = await provider.chat(system, retry, **options)
    try:
        return parse(raw)
    except InvalidReply:
        raise ai_unusable(unusable_message) from None


async def chat_json(
    provider,
    system: str,
    messages: List[Dict[str, Any]],
    model: Type[T],
    *,
    max_output_tokens: int,
    unusable_message: Optional[str] = None,
) -> T:
    """One chat call whose reply must be JSON fitting ``model``, retried
    once with the problems; ``ai_unusable`` when the retry does not fit."""
    return await chat_structured(
        provider,
        system,
        messages,
        lambda raw: parse_reply(raw, model),
        max_output_tokens=max_output_tokens,
        unusable_message=unusable_message,
    )


# ---------------------------------------------------------------------------
# A generated form (form generation's final answer)
# ---------------------------------------------------------------------------

QUESTION_TYPES = (
    "short_text",
    "long_text",
    "multiple_choice",
    "dropdown",
    "yes_no",
    "rating",
    "linear_rating",
    "number",
    "email",
    "phone_number",
    "date",
    "file_upload",
    "url",
)
QuestionType = Literal[QUESTION_TYPES]  # type: ignore[valid-type]
SlideType = Literal[("group",) + QUESTION_TYPES]  # type: ignore[valid-type]

MAX_GENERATED_PAGES = 50
MAX_GENERATED_FIELDS_PER_PAGE = 50
MAX_GENERATED_CHOICES = 100


class _Lenient(BaseModel):
    # keys the converter does not read are dropped
    model_config = ConfigDict(extra="ignore")


class GeneratedProperties(_Lenient):
    placeholder: Optional[str] = None
    required: Optional[bool] = None
    allowOther: Optional[bool] = None
    allowMultiple: Optional[bool] = None
    choices: Optional[List[str]] = Field(None, max_length=MAX_GENERATED_CHOICES)
    steps: Optional[int] = Field(None, ge=1, le=100)
    startFrom: Optional[int] = Field(None, ge=0, le=100)
    whyWeAsk: Optional[str] = None


class GeneratedQuestion(_Lenient):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    type: QuestionType
    properties: GeneratedProperties = Field(default_factory=GeneratedProperties)


class GeneratedSlideProperties(GeneratedProperties):
    fields: Optional[List[GeneratedQuestion]] = Field(
        None, max_length=MAX_GENERATED_FIELDS_PER_PAGE
    )


class GeneratedSlide(_Lenient):
    title: Optional[str] = None
    sectionTitle: Optional[str] = None
    description: Optional[str] = None
    type: SlideType
    layout: Optional[str] = None
    image_url: Optional[str] = None
    properties: GeneratedSlideProperties = Field(
        default_factory=GeneratedSlideProperties
    )


class GeneratedForm(_Lenient):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    theme_name: Optional[str] = None
    welcome_image_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    fields: List[GeneratedSlide] = Field(
        ..., min_length=1, max_length=MAX_GENERATED_PAGES
    )


def parse_generated_form(text: str) -> Dict[str, Any]:
    """A generation reply as the converter's dict; InvalidReply when it is
    not a form."""
    form = parse_reply(text, GeneratedForm, nulls_absent=True)
    return form.model_dump(exclude_none=True)


def _strict_object(properties: Dict[str, Any]) -> dict:
    """OpenAI strict mode: every property required, nothing else allowed."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _nullable(kind: str, **extra) -> dict:
    return {"type": [kind, "null"], **extra}


def _properties_schema(with_fields: bool) -> dict:
    properties = {
        "placeholder": _nullable("string"),
        "required": _nullable("boolean"),
        "allowOther": _nullable("boolean"),
        "allowMultiple": _nullable("boolean"),
        "choices": _nullable("array", items={"type": "string"}),
        "steps": _nullable("integer"),
        "startFrom": _nullable("integer"),
        "whyWeAsk": _nullable("string"),
    }
    if with_fields:
        properties["fields"] = _nullable("array", items=_question_schema())
    return _strict_object(properties)


def _question_schema() -> dict:
    return _strict_object(
        {
            "title": {"type": "string"},
            "description": _nullable("string"),
            "type": {"type": "string", "enum": list(QUESTION_TYPES)},
            "properties": _properties_schema(with_fields=False),
        }
    )


def generated_form_schema() -> dict:
    """The generated form as a strict JSON schema (OpenAI structured
    output): optional values are nullable, null means absent."""
    slide = _strict_object(
        {
            "title": _nullable("string"),
            "sectionTitle": _nullable("string"),
            "description": _nullable("string"),
            "type": {"type": "string", "enum": ["group", *QUESTION_TYPES]},
            "layout": _nullable("string"),
            "image_url": _nullable("string"),
            "properties": _properties_schema(with_fields=True),
        }
    )
    return _strict_object(
        {
            "title": {"type": "string"},
            "description": _nullable("string"),
            "theme_name": _nullable("string"),
            "welcome_image_url": _nullable("string"),
            "cover_image_url": _nullable("string"),
            "fields": {"type": "array", "items": slide},
        }
    )
