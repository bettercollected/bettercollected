"""An imported form's address of the original (``settings.embed_url``) is
opened or framed by the respondent page, so only an http(s) address is
stored; anything else is dropped at import."""

import pytest

from backend.app.container import container
from backend.app.services.form_import_service import http_url_or_none

FORM_ID = "1FAIpQLSe-embed-url-form"


def _converted(embed_url) -> dict:
    return {
        "form": {
            "form_id": FORM_ID,
            "title": "Imported form",
            "settings": {"provider": "google", "embed_url": embed_url},
            "fields": [{"id": "q1", "type": "short_text", "title": "Name"}],
        },
        "responses": [],
    }


async def _import(workspace, embed_url):
    form = await container.form_import_service().save_converted_form_and_responses(
        _converted(embed_url), None, workspace_id=workspace.id
    )
    stored = await container.form_repo().get_form_document_by_id(FORM_ID)
    return form.settings.embed_url, stored.settings.embed_url


@pytest.mark.parametrize(
    "embed_url",
    [
        "https://docs.google.com/forms/d/e/1FAIpQLSe-embed-url-form/viewform",
        "http://forms.example.test/f/1",
    ],
)
async def test_an_http_address_is_kept(workspace, embed_url):
    assert await _import(workspace, embed_url) == (embed_url, embed_url)


@pytest.mark.parametrize(
    "embed_url",
    [
        "javascript:alert(1)",
        " JavaScript:alert(1)",
        "data:text/html,<p>x</p>",
        "//forms.example.test/f/1",
        "/relative/path",
        "https://",
        "",
    ],
)
async def test_anything_else_is_dropped(workspace, embed_url):
    assert await _import(workspace, embed_url) == (None, None)


def test_the_check():
    assert http_url_or_none(" https://a.example/x ") == "https://a.example/x"
    assert http_url_or_none("HTTPS://a.example/x") == "HTTPS://a.example/x"
    assert http_url_or_none(None) is None
    assert http_url_or_none("ftp://a.example/x") is None
    assert http_url_or_none("http://[::1") is None
