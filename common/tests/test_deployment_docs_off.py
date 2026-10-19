"""The shipped deployment does not serve the internal APIs' docs."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SERVICES = ("backend", "auth", "integrations-googleform")
TRUE = r"[\"']?(true|1|yes|on)"


def _service_block(compose: str, name: str) -> str:
    match = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  \S|\Z)", compose, re.M | re.S)
    assert match, name
    return match.group(1)


def test_deployment_compose_does_not_pin_docs():
    """A value pinned in compose silently wins over the portal (an environment
    value beats the settings store). The code default is off."""
    compose = (REPO / "docker-compose.deployment.yml").read_text()
    for name in SERVICES:
        block = _service_block(compose, name)
        assert not re.search(r"^\s+API_DOCS_ENABLED\s*:", block, re.M), name


def test_no_shipped_deployment_file_enables_docs():
    for name in (
        "docker-compose.deployment.yml",
        "docker-compose.sso-deployment.yml",
        ".env.deployment.example",
    ):
        text = (REPO / name).read_text()
        assert not re.search(rf"^\s*API_DOCS_ENABLED\s*[:=]\s*{TRUE}", text, re.M | re.I), name
    assert not re.search(r"^API_DOCS_ENABLED=", (REPO / ".env.deployment.example").read_text(), re.M)


def test_no_healthcheck_depends_on_the_internal_docs_route():
    compose = (REPO / "docker-compose.deployment.yml").read_text()
    assert "/api/v1/docs" not in compose
