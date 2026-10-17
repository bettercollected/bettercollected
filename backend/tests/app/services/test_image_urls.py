"""Image addresses a form may hold (services/image_urls.py).

Our own storage and our Unsplash route are first-party; an Unsplash photo
address is accepted only to be rewritten to our route, so respondents'
browsers never contact Unsplash; anything else is refused."""

import pytest
from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
    Theme,
    ThemeBackground,
)

from backend.app.container import container
from backend.app.services.ai.ops import UpdateThemeOp, apply_form_ops, parse_ops
from backend.app.services.image_urls import (
    BUILTIN_IMAGE_URLS,
    allowed_image_url_or_none,
    checked_image_url,
    first_party_image_url,
    is_allowed_image_url,
    is_first_party_image_url,
)
from backend.config import settings

STORAGE = "https://cdn.example.org"
ENDPOINT = "https://s3.example-storage.test"
BUCKET = "forms-bucket"
UNSPLASH = "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?ixid=abc&ixlib=rb-4.0.3"
API = "https://forms.example.org/api/v1"
ROUTED = f"{API}/images/unsplash/photo-1500530855697-b586d89ba3ee"


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    aws = settings.aws_settings
    monkeypatch.setattr(aws, "PUBLIC_URL", STORAGE)
    monkeypatch.setattr(aws, "ENDPOINT_URL", ENDPOINT)
    monkeypatch.setattr(aws, "BUCKET", BUCKET)
    monkeypatch.setattr(settings.api_settings, "PUBLIC_URL", API + "/")


@pytest.mark.parametrize(
    "url",
    [
        f"{STORAGE}/{BUCKET}/public/20260101_bg.png",
        f"{STORAGE}/{BUCKET}/media_library/20260101_photo.jpg",
        f"{STORAGE}/{BUCKET}/images/v2_layout_image.webp",
        # objects stored before a CDN address was configured
        f"{ENDPOINT}/{BUCKET}/public/20260101_bg.png",
        f"  {STORAGE}/{BUCKET}/public/x.png  ",
        ROUTED,
        f"{ROUTED}?fit=crop&h=400&q=80&w=1080",
        f"{API}/images/unsplash/premium_photo-1",
        *sorted(BUILTIN_IMAGE_URLS),
    ],
)
def test_our_storage_and_our_unsplash_route_are_first_party(url):
    assert is_first_party_image_url(url)
    assert is_allowed_image_url(url)
    assert checked_image_url(url) == url.strip()


@pytest.mark.parametrize(
    "url,routed",
    [
        (UNSPLASH, ROUTED),
        ("https://images.unsplash.com/photo-1", f"{API}/images/unsplash/photo-1"),
        ("HTTPS://IMAGES.UNSPLASH.COM/photo-1", f"{API}/images/unsplash/photo-1"),
        (f"  {UNSPLASH}  ", ROUTED),
        # the AI image search's urls.regular: sizing kept, tracking dropped
        (
            "https://images.unsplash.com/photo-1?crop=entropy&cs=tinysrgb&fit=max"
            "&fm=jpg&ixid=M3w&ixlib=rb-4.0.3&q=80&w=1080",
            f"{API}/images/unsplash/photo-1?crop=entropy&fit=max&fm=jpg&q=80&w=1080",
        ),
        # a bad value is dropped, not forwarded
        (
            "https://images.unsplash.com/photo-1?w=huge&q=80",
            f"{API}/images/unsplash/photo-1?q=80",
        ),
    ],
)
def test_unsplash_photos_are_rewritten_to_our_route(url, routed):
    assert not is_first_party_image_url(url)
    assert is_allowed_image_url(url)
    assert first_party_image_url(url) == routed
    assert checked_image_url(url) == routed
    assert allowed_image_url_or_none(url) == routed
    assert is_first_party_image_url(routed)


@pytest.mark.parametrize(
    "url",
    [
        "https://tracker.example.com/pixel.png",
        "http://images.unsplash.com/photo-1",  # not https
        "https://images.unsplash.com.evil.test/photo-1",
        "https://evil.test/images.unsplash.com/photo-1",
        "https://user@images.unsplash.com/photo-1",
        "https://images.unsplash.com:8443/photo-1",
        "https://plus.unsplash.com/premium_photo-1",
        "https://images.unsplash.com/",
        f"{STORAGE}/other-bucket/public/x.png",  # someone else's bucket
        f"{STORAGE}/{BUCKET}/private/ws/form/resp/file",  # respondents' uploads
        f"{STORAGE}/{BUCKET}/public/../private/x",
        f"{STORAGE}/{BUCKET}/public/%2e%2e/private/x",
        f"{STORAGE}/{BUCKET}/public/x.png?redirect=https://evil.test",
        f"{STORAGE}.evil.test/{BUCKET}/public/x.png",
        f"http://cdn.example.org/{BUCKET}/public/x.png",  # scheme differs
        "javascript:alert(1)",
        "data:image/png;base64,AAAA",
        "//images.unsplash.com/photo-1",
        "/relative/path.png",
        'https://images.unsplash.com/photo-1")',
        "https://images.unsplash.com/photo-1 x",
        "https://images.unsplash.com/" + "a" * 2100,
        "https://images.unsplash.com/../x",
        "https://images.unsplash.com/a/b/c",
        # our route: only from our API's address, a photo path and known options
        "https://evil.test/api/v1/images/unsplash/photo-1",
        f"{API}/images/unsplash/",
        f"{API}/images/unsplash/../../workspaces",
        f"{API}/images/unsplash/photo-1?url=https://evil.test",
        f"{API}/images/unsplash/photo-1?w=abc",
        f"{API}/images/unsplash/photo-1?w=10&w=20",
        f"{API}/images/unsplash/photo-1#x",
        f"{API}/images/other/photo-1",
        "https://s3.eu-central-1.wasabisys.com/bettercollected/public/x.png",
    ],
)
def test_every_other_address_is_refused(url):
    assert not is_first_party_image_url(url)
    assert not is_allowed_image_url(url)
    with pytest.raises(ValueError, match="own storage or from Unsplash"):
        checked_image_url(url)
    assert allowed_image_url_or_none(url) is None


def test_blank_clears_and_absent_is_unchanged():
    assert checked_image_url(None) is None
    assert checked_image_url("") == ""
    assert checked_image_url("   ") == ""
    assert not is_allowed_image_url("")
    assert not is_allowed_image_url(None)


def test_storage_without_a_public_url_uses_the_endpoint(monkeypatch):
    monkeypatch.setattr(settings.aws_settings, "PUBLIC_URL", "")
    assert is_allowed_image_url(f"{ENDPOINT}/{BUCKET}/public/x.png")
    assert not is_allowed_image_url(f"{STORAGE}/{BUCKET}/public/x.png")


# -- the ops engine (AI chat, review fixes, MCP update_form) --------------------


def _form() -> StandardForm:
    page = StandardFormField(
        id="page-1",
        index=0,
        type=StandardFormFieldType.SLIDE,
        properties=StandardFieldProperty(fields=[]),
    )
    return StandardForm(
        builder_version="v2", form_id="form-1", title="Form", fields=[page]
    )


def _theme(image_url, bg_type="image") -> Theme:
    return Theme(
        title="Pictured",
        primary="#111827",
        secondary="#1D4ED8",
        tertiary="#2563EB",
        accent="#DBEAFE",
        background=ThemeBackground(type=bg_type, imageUrl=image_url),
    )


def test_update_theme_refuses_a_third_party_background():
    form = _form()
    new_form, results = apply_form_ops(
        form, [UpdateThemeOp(theme=_theme("https://tracker.example.com/bg.jpg"))]
    )
    assert not results[0].ok
    assert "Background image refused" in results[0].message
    assert "Unsplash" in results[0].message
    assert new_form.theme == form.theme


def test_a_refused_theme_does_not_stop_the_rest_of_the_turn():
    ops = parse_ops(
        [
            {
                "op": "update_theme",
                "theme": _theme("https://tracker.example.com/bg.jpg").model_dump(),
            },
            {"op": "update_form_info", "title": "Renamed"},
        ]
    )
    new_form, results = apply_form_ops(_form(), ops)
    assert [r.ok for r in results] == [False, True]
    assert new_form.title == "Renamed"


@pytest.mark.parametrize(
    "url,stored",
    [
        (UNSPLASH, ROUTED),
        (ROUTED, ROUTED),
        (
            f"{STORAGE}/{BUCKET}/media_library/20260101_photo.jpg",
            f"{STORAGE}/{BUCKET}/media_library/20260101_photo.jpg",
        ),
    ],
)
def test_update_theme_keeps_an_allowed_background_first_party(url, stored):
    new_form, results = apply_form_ops(_form(), [UpdateThemeOp(theme=_theme(url))])
    assert results[0].ok, results[0].message
    assert new_form.theme.background.imageUrl == stored


@pytest.mark.parametrize("url", [None, "", "  "])
def test_update_theme_without_an_image_is_fine(url):
    new_form, results = apply_form_ops(
        _form(), [UpdateThemeOp(theme=_theme(url, bg_type="color"))]
    )
    assert results[0].ok
    assert new_form.theme.background.imageUrl is None


# -- AI form creation (dashboard and MCP create_form_with_ai) -------------------


def test_ai_created_forms_keep_only_allowed_images():
    form = container.openai_service().convert_openai_form_to_standard_form(
        {
            "title": "Intake",
            "welcome_image_url": "https://tracker.example.com/welcome.jpg",
            "cover_image_url": "https://tracker.example.com/cover.jpg",
            "fields": [
                {
                    "type": "short_text",
                    "title": "Name",
                    "image_url": "https://tracker.example.com/page.jpg",
                    "layout": "TWO_COLUMN_IMAGE_LEFT",
                },
                {
                    "type": "short_text",
                    "title": "City",
                    "image_url": UNSPLASH,
                    "layout": "TWO_COLUMN_IMAGE_RIGHT",
                },
            ],
        }
    )
    assert form.welcome_page.imageUrl is None
    assert form.welcome_page.layout == "SINGLE_COLUMN_NO_BACKGROUND"
    assert form.cover_image is None
    refused, kept = form.fields
    assert refused.image_url is None
    assert refused.properties.layout != "TWO_COLUMN_IMAGE_LEFT"
    # kept, served through our server
    assert kept.image_url == ROUTED
    assert kept.properties.layout == "TWO_COLUMN_IMAGE_RIGHT"
