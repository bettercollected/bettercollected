"""Static checks on templates and the stylesheet (no database)."""

import re
from pathlib import Path

import pytest

from backend.admin.portal import STATIC_DIR, TEMPLATE_DIR, make_templates
from backend.admin.portal_config import PortalConfigError, PortalSettings, normalise_origin

TEMPLATES = sorted(TEMPLATE_DIR.glob("*.html"))


def test_there_are_templates():
    assert len(TEMPLATES) >= 5


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.name)
def test_no_safe_filter_or_autoescape_off(path: Path):
    source = path.read_text()
    assert not re.search(r"\|\s*safe\b|\|\s*forceescape|Markup|autoescape\s+(false|off)", source)


TEXT_ASSETS = [p for p in sorted(STATIC_DIR.glob("*")) if p.is_file()]
SELF_HOSTED_FONT = re.compile(r"url\(/static/fonts/[a-z0-9-]+\.woff2\) format\(\"woff2\"\)")


@pytest.mark.parametrize("path", [*TEMPLATES, *TEXT_ASSETS], ids=lambda p: p.name)
def test_no_external_urls_or_inline_code(path: Path):
    source = path.read_text()
    if path.suffix == ".css":
        # the only url(): the self-hosted woff2 faces, root-relative
        source = SELF_HOSTED_FONT.sub("", source)
    assert not re.search(r"https?://|//[a-z0-9.-]+\.[a-z]{2,}|@import|url\(", source, re.I)
    if path.suffix == ".html":
        # the one allowed script: a self-hosted file, no inline code
        source = re.sub(r'<script src="/static/[a-z0-9._-]+\.js" defer></script>', "", source)
        assert not re.search(r"<script|<style|\sstyle=|\son\w+\s*=", source, re.I)


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.name)
def test_every_visible_string_goes_through_gettext(path: Path):
    source = path.read_text()
    body = re.sub(r"\{\{.*?\}\}|\{%.*?%\}|<[^>]+>", "", source, flags=re.S)
    body = re.sub(r"[\s.,:;!?()-]+", "", body)  # punctuation between pieces is fine
    assert not body, f"untranslated text in {path.name}: {body[:60]!r}"


def test_autoescape_is_on_and_undefined_is_strict():
    env = make_templates()
    assert env.autoescape is True
    source = '{% extends "shell.html" %}{% block content %}{{ email }}{% endblock %}'
    page = env.from_string(source).render(csrf_token="t", email="<b>x</b>")
    assert "&lt;b&gt;x&lt;/b&gt;" in page and "<b>x" not in page
    with pytest.raises(Exception):
        env.from_string(source).render(csrf_token="t")


def test_origin_settings():
    assert normalise_origin("HTTPS://Admin.Example.org:8443/") == "https://admin.example.org:8443"
    for bad in ("admin.example.org", "ftp://a.org", "https://a.org/path", "https://u:p@a.org", "https://a.org?x=1", ""):
        with pytest.raises(PortalConfigError):
            normalise_origin(bad)
    assert PortalSettings.from_env({}).public_origins == (
        "http://localhost:8100",
        "http://127.0.0.1:8100",
    )


def test_session_lifetimes_can_only_be_shortened():
    s = PortalSettings.from_env(
        {"ADMIN_SESSION_IDLE_MINUTES": "10", "ADMIN_SESSION_ABSOLUTE_HOURS": "2"}
    )
    assert (s.idle_minutes, s.absolute_hours) == (10, 2)
    for env in (
        {"ADMIN_SESSION_IDLE_MINUTES": "31"},
        {"ADMIN_SESSION_ABSOLUTE_HOURS": "9"},
        {"ADMIN_SESSION_IDLE_MINUTES": "0"},
        {"ADMIN_SESSION_IDLE_MINUTES": "abc"},
    ):
        with pytest.raises(PortalConfigError):
            PortalSettings.from_env(env)


def test_admin_emails_are_case_insensitive():
    s = PortalSettings.from_env({"PLATFORM_ADMIN_EMAILS": " A@X.org ; b@y.org,,junk"})
    assert s.is_admin("a@x.ORG") and s.is_admin(" B@y.org ") and not s.is_admin("junk")


def test_every_font_face_points_at_a_shipped_file():
    css = (STATIC_DIR / "admin.css").read_text()
    names = set(re.findall(r"/static/fonts/([a-z0-9-]+\.woff2)", css))
    assert names and names == {p.name for p in (STATIC_DIR / "fonts").glob("*.woff2")}
    assert css.count("font-display: swap") >= len(names)
    assert (STATIC_DIR / "fonts" / "LICENSE").read_text().startswith("The woff2 files")


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.name)
def test_preloads_are_same_origin_fonts(path: Path):
    for link in re.findall(r"<link[^>]*rel=\"preload\"[^>]*>", path.read_text()):
        assert re.search(r'href="/static/fonts/[a-z0-9-]+\.woff2"', link) and 'as="font"' in link and "crossorigin" in link


def test_only_the_font_cache_value_survives_the_header_rewrite():
    from backend.admin.headers import FONT_CACHE_CONTROL, with_security_headers

    def cache(headers):
        return [v for k, v in headers if k == b"cache-control"]

    assert cache(with_security_headers([(b"cache-control", b"public, max-age=60")])) == [b"no-store"]
    assert cache(with_security_headers([])) == [b"no-store"]
    font = FONT_CACHE_CONTROL.encode()
    assert cache(with_security_headers([(b"cache-control", font)])) == [font]
