"""The image addresses on a form, checked when a person saves it.

Every place a form holds an image that respondent pages load: the theme
background (the form's and each page's own theme), the welcome and ending
images, each page's layout image and each question's image, and the cover
image. On a save each one is:

- kept when it is first-party (``services/image_urls.py``);
- rewritten to our Unsplash route when it is an ``images.unsplash.com`` photo;
- kept as is when the stored draft already holds exactly that address, so a
  form saved before these checks keeps working and can still be edited
  (nothing a respondent's browser loads changes because of the save);
- otherwise refused (422), or dropped for a copy (a template), where nobody
  can fix it by hand.

The editor copies a pasted address in first (``POST .../images/import``), so
a person never meets the refusal from the builder itself.
"""

from http import HTTPStatus
from typing import Callable, FrozenSet, Iterable, Optional, Set

from common.models.standard_form import StandardForm, StandardFormField

from backend.app.exceptions import HTTPException
from backend.app.services.image_urls import IMAGE_URL_ERROR, first_party_image_url

Fix = Callable[[Optional[str]], Optional[str]]


def _theme(theme, fix: Fix) -> None:
    background = getattr(theme, "background", None) if theme else None
    if background is not None:
        background.imageUrl = fix(background.imageUrl)


def _fields(fields: Optional[Iterable[StandardFormField]], fix: Fix) -> None:
    for field in fields or []:
        if field is None:
            continue
        field.image_url = fix(field.image_url)
        properties = field.properties
        if properties is not None:
            _theme(properties.theme, fix)
            _fields(properties.fields, fix)


def map_form_images(form: StandardForm, fix: Fix) -> None:
    """Replace every image address on ``form`` with ``fix(address)``."""
    _theme(form.theme, fix)
    if form.welcome_page is not None:
        form.welcome_page.imageUrl = fix(form.welcome_page.imageUrl)
    for page in form.thankyou_page or []:
        if page is not None:
            page.imageUrl = fix(page.imageUrl)
    form.cover_image = fix(form.cover_image)
    _fields(form.fields, fix)


def form_image_urls(form: Optional[StandardForm]) -> FrozenSet[str]:
    """Every non-blank image address on ``form``."""
    found: Set[str] = set()
    if form is None:
        return frozenset()

    def collect(url: Optional[str]) -> Optional[str]:
        if isinstance(url, str) and url.strip():
            found.add(url.strip())
        return url

    map_form_images(form.model_copy(deep=True), collect)
    return frozenset(found)


def refused_image() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"code": "image_not_allowed", "message": IMAGE_URL_ERROR},
    )


def first_party_or_kept(
    url: Optional[str], keep: FrozenSet[str] = frozenset(), drop: bool = False
) -> Optional[str]:
    """The address to store for one image (see the module docstring)."""
    if url is None or not isinstance(url, str) or not url.strip():
        return url
    stored = first_party_image_url(url)
    if stored is not None:
        return stored
    if url.strip() in keep:
        return url
    if drop:
        return None
    raise refused_image()


def check_form_images(
    form: StandardForm,
    stored: Optional[StandardForm] = None,
    drop: bool = False,
) -> None:
    """Make every image address on ``form`` first-party (in place), keeping
    the ones ``stored`` already holds, or raise 422."""
    keep = form_image_urls(stored)
    map_form_images(form, lambda url: first_party_or_kept(url, keep, drop))
