"""Theme checks for whole-form saves and a workspace's saved themes.

A form's theme (and a page's own theme) may carry type, shape and highlight
keys (``titleFont``, ``radius``, ``highlight``, ...). Each must be absent or
one of its listed values (common.models.standard_form.theme_problems); the
edit operations check the same in ops.py.

A workspace's saved themes are also held to the publish check's contrast
rules (services/theme_contrast.py): a theme whose own colours fail WCAG AA
would fail every form that uses it at publish, so it is refused when saved,
as the Themes page already does. Colours the workspace already has stored are
kept as they are, so deleting or renaming one theme never trips on another.
"""

from http import HTTPStatus
from typing import Any, Dict, FrozenSet, Iterable, Iterator, List, Optional, Tuple

from common.models.standard_form import theme_problems

from backend.app.constants.themes import GATED_ARTWORKS, artwork_offered, offered_artworks
from backend.app.exceptions import HTTPException
from backend.app.services.publish_checks import (
    THEME_CONTRAST,
    theme_contrast_problems,
)
from backend.app.services.theme_contrast import contrast_key, theme_contrast_guard

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


def _artwork(theme: Any) -> Optional[str]:
    artwork = _get(_get(theme, "background"), "artwork")
    return artwork if isinstance(artwork, str) else None


def _unoffered(artwork: Optional[str]) -> bool:
    return artwork is not None and artwork in GATED_ARTWORKS and not artwork_offered(artwork)


def _artwork_message(path: str) -> str:
    # word for word what an unlisted artwork earns (common theme_problems)
    return f"{path}.background.artwork must be one of: {', '.join(offered_artworks())}."


def unoffered_artwork_problems(form: Any, stored: Any = None) -> List[str]:
    """While the switch of a gated artwork (``GATED_ARTWORKS``) is off, one
    problem for each theme of the form, and of its pages and questions, that
    names it, unless the stored form has the same artwork at the same path:
    a form that already wears it stays saveable. ``stored`` None: nothing is
    stored (a new form)."""
    if not any(_unoffered(a) for a in GATED_ARTWORKS):
        return []
    problems: List[str] = []
    kept: Optional[Dict[str, Optional[str]]] = None
    for path, theme in _themes(form):
        artwork = _artwork(theme)
        if not _unoffered(artwork):
            continue
        if stored is not None:
            if kept is None:
                kept = {p: _artwork(t) for p, t in _themes(stored)}
            if kept.get(path) == artwork:
                continue
        problems.append(_artwork_message(path))
    return problems


def ensure_artwork_offered(form: Any, stored: Any = None) -> None:
    """422 ``theme_not_allowed`` for a theme that brings a gated artwork the
    server does not offer (see ``unoffered_artwork_problems``)."""
    refuse_theme_problems(unoffered_artwork_problems(form, stored))


async def ensure_artwork_offered_for_save(form: Any, load_stored: Any) -> None:
    """The same for a save of an existing form: the stored draft (``load_stored``,
    an async callable) is read only when a theme names an artwork that is off."""
    problems = unoffered_artwork_problems(form)
    if problems:
        problems = unoffered_artwork_problems(form, await load_stored())
    refuse_theme_problems(problems)


def ensure_saved_artwork_offered(themes: List[Any], stored: Optional[Iterable[Any]] = None) -> None:
    """The same for a workspace's saved themes (``customThemes.<i>``): one a
    stored theme of the same title already has is kept."""
    if not any(_unoffered(a) for a in GATED_ARTWORKS):
        return
    kept = {
        str(_get(theme, "title")).casefold(): _artwork(theme) for theme in (stored or [])
    }
    problems = [
        _artwork_message(f"customThemes.{i}")
        for i, theme in enumerate(themes or [])
        if _unoffered(_artwork(theme))
        and kept.get(str(_get(theme, "title")).casefold()) != _artwork(theme)
    ]
    refuse_theme_problems(problems)


def ensure_valid_themes(form: Any) -> None:
    """422 with every theme problem, before anything is stored."""
    refuse_theme_problems(form_theme_problems(form))


def ensure_valid_saved_themes(themes: List[Any]) -> None:
    """The same 422 for a workspace's saved themes (``customThemes.<i>``)."""
    problems: List[str] = []
    for i, theme in enumerate(themes or []):
        problems += theme_problems(theme, f"customThemes.{i}")
    refuse_theme_problems(problems)


def refuse_theme_problems(problems: List[str]) -> None:
    if problems:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": ERROR_CODE,
                "message": " ".join(problems),
                "errors": problems,
            },
        )


def ensure_readable_saved_themes(
    themes: List[Any], stored: Optional[Iterable[Any]] = None
) -> None:
    """422 ``theme_contrast`` when a saved theme's colours fail WCAG AA where
    the respondent form shows them, naming each theme (``customThemes.<i>``)
    with its failing pairings and the nearest colours that pass. A theme
    whose colours the workspace already stores (``stored``) is kept as it is.
    The body holds only what was sent and what is computed from it."""
    kept: FrozenSet[Tuple[Any, ...]] = frozenset(
        contrast_key(theme) for theme in (stored or [])
    )
    errors: List[str] = []
    details: List[Dict[str, Any]] = []
    for i, theme in enumerate(themes or []):
        if contrast_key(theme) in kept:
            continue
        problems = theme_contrast_problems(theme)
        if not problems:
            continue
        path = f"customThemes.{i}"
        guard = theme_contrast_guard(theme)
        errors += [f"{path}: {problem['message']}" for problem in problems]
        details.append(
            {
                "index": i,
                "path": path,
                "issues": [
                    {"key": issue.key, "ratio": issue.ratio, "minimum": issue.minimum}
                    for issue in guard.issues
                ],
                "fix": guard.fix,
            }
        )
    if errors:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": THEME_CONTRAST,
                "message": " ".join(errors),
                "errors": errors,
                "themes": details,
            },
        )
