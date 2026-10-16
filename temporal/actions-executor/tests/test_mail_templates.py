"""The respondent's copy of a response: rendered with autoescape, no web fonts
(a font CDN would learn who opened the mail), the Sireto line and the current
year in the copyright line."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from utilities.mail import response_mail_context

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
ENV = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape())


@pytest.mark.parametrize("name", sorted(p.name for p in TEMPLATES.glob("*.html")))
def test_templates_load_no_web_fonts(name):
    source = (TEMPLATES / name).read_text()
    assert "googleapis" not in source and "gstatic" not in source
    assert "@import" not in source


def _body():
    context = response_mail_context(
        fields=[{"title": "Name", "answer": "<b>Jane</b>"}],
        creator_mail=False,
        title="Job application",
        description="",
    )
    return ENV.get_template("response-mail.html").render(**context)


def test_response_mail_renders_escaped_with_sireto_footer():
    body = _body()
    assert "&lt;b&gt;Jane&lt;/b&gt;" in body and "<b>Jane</b>" not in body
    assert '<a href="https://sireto.com"' in body
    assert "Sireto&reg; is a registered trademark of Sireto B.V." in body


def test_copyright_year_is_the_year_the_mail_is_sent():
    year = datetime.now(timezone.utc).year
    assert f"&copy; {year} Sireto B.V. All rights reserved." in _body()
