"""Theme checks for whole-form saves.

A form's theme (and a page's own theme) may carry type, shape and highlight
keys (``titleFont``, ``radius``, ``highlight``, ...). Each must be absent or
one of its listed values (common.models.standard_form.theme_problems); the
edit operations check the same in ops.py.
"""

from http import HTTPStatus
from typing import Any, Iterator, List, Optional, Tuple

from common.models.standard_form import theme_problems

from backend.app.exceptions import HTTPException

ERROR_CODE = "theme_not_allowed"


def _get(value: Any, key: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _themes(form: Any) -> Iterator[Tuple[str, Any]]:
    yield "theme", _get(form, "theme")
    pending: List[Tuple[str, Any]] = [
        (f"fields.{i}", field) for i, field in enumerate(_get(form, "fields") or [])
    ]
    while pending:
        path, field = pending.pop(0)
        properties = _get(field, "properties")
        theme: Optional[Any] = _get(properties, "theme")
        if theme is not None:
            yield f"{path}.properties.theme", theme
        for i, child in enumerate(_get(properties, "fields") or []):
            pending.append((f"{path}.properties.fields.{i}", child))


def form_theme_problems(form: Any) -> List[str]:
    """Every problem with the form's theme and its pages' and questions' own
    themes, each naming where it is."""
    problems: List[str] = []
    for path, theme in _themes(form):
        problems += theme_problems(theme, path)
    return problems


def ensure_valid_themes(form: Any) -> None:
    """422 with every theme problem, before anything is stored."""
    problems = form_theme_problems(form)
    if problems:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": ERROR_CODE,
                "message": " ".join(problems),
                "errors": problems,
            },
        )
