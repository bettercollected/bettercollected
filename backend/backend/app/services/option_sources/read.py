"""Reading a form's option sources: forms arrive as models or plain dicts."""

from typing import Any, Dict, Iterator, List, Optional, Tuple

PAGE = "slide"
GROUP = "group"
CHOICE_TYPES = frozenset({"multiple_choice", "dropdown"})
# What another form's answers may become options from (docs/option-sources.md).
ANSWER_SOURCE_TYPES = frozenset({"short_text", "multiple_choice", "dropdown"})


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


def get(item: Any, name: str, default: Any = None) -> Any:
    """``item.name`` of a model, or of a dict in snake_case or (as a form
    served to respondents holds its properties) camelCase."""
    if item is None:
        return default
    if isinstance(item, dict):
        if name in item:
            return item[name]
        if "_" in name:
            return item.get(_camel(name), default)
        return default
    return getattr(item, name, default)


def field_type(field: Any) -> Optional[str]:
    kind = get(field, "type")
    return getattr(kind, "value", kind)


def props(field: Any) -> Any:
    return get(field, "properties")


def page_questions(form: Any) -> Iterator[Any]:
    """The questions that sit directly on a page, in the order respondents
    meet them (a flat form's top-level fields count as one page)."""
    for field in get(form, "fields") or []:
        if field_type(field) == PAGE:
            yield from get(props(field), "fields") or []
        else:
            yield field


def every_field(form: Any) -> Iterator[Tuple[Any, bool]]:
    """``(field, at page level)`` of every question, group children included
    (iterative: forms can be nested)."""
    pending: List[Tuple[Any, bool]] = [
        (field, True) for field in get(form, "fields") or []
    ]
    pending.reverse()
    while pending:
        field, top = pending.pop()
        if field_type(field) == PAGE:
            children = [(child, True) for child in get(props(field), "fields") or []]
        else:
            yield field, top
            children = [(child, False) for child in get(props(field), "fields") or []]
        pending.extend(reversed(children))


def source_dict(field: Any) -> Optional[Dict[str, Any]]:
    """The field's ``optionSource`` as a plain dict with snake_case keys
    (kind, list_id, parent_field_id, form_id, question_id), or None."""
    source = get(props(field), "option_source")
    if source is None:
        return None
    if hasattr(source, "model_dump"):
        return source.model_dump(exclude_none=True)
    if isinstance(source, dict):
        camel = {
            "listId": "list_id",
            "parentFieldId": "parent_field_id",
            "formId": "form_id",
            "questionId": "question_id",
        }
        return {camel.get(k, k): v for k, v in source.items() if v is not None}
    return None


def sourced_questions(form: Any) -> Iterator[Tuple[Any, Dict[str, Any]]]:
    """``(question, source)`` of every question with an option source, at any
    depth."""
    for field, _ in every_field(form):
        source = source_dict(field)
        if source is not None:
            yield field, source


def has_source(field: Any) -> bool:
    return source_dict(field) is not None


def static_labels(field: Any) -> Dict[str, str]:
    """``{option id: text}`` of a question's own choices (the text people see:
    ``value``, else ``label``)."""
    labels: Dict[str, str] = {}
    for choice in get(props(field), "choices") or []:
        choice_id = get(choice, "id")
        text = get(choice, "value") or get(choice, "label")
        if choice_id and isinstance(text, str):
            labels[str(choice_id)] = text
    return labels
