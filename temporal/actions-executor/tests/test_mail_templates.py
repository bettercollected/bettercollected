"""The respondent's copy of a response: rendered with autoescape, no web fonts
(a font CDN would learn who opened the mail), and the Sireto line."""

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
ENV = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape())


@pytest.mark.parametrize("name", sorted(p.name for p in TEMPLATES.glob("*.html")))
def test_templates_load_no_web_fonts(name):
    source = (TEMPLATES / name).read_text()
    assert "googleapis" not in source and "gstatic" not in source
    assert "@import" not in source


def test_response_mail_renders_escaped_with_sireto_footer():
    body = ENV.get_template("response-mail.html").render(
        form=[{"title": "Name", "answer": "<b>Jane</b>"}],
        creator_mail=False,
        title="Job application",
        description="",
    )
    assert "&lt;b&gt;Jane&lt;/b&gt;" in body and "<b>Jane</b>" not in body
    assert '<a href="https://sireto.com"' in body
    assert "Sireto&reg; is a registered trademark of Sireto B.V." in body
