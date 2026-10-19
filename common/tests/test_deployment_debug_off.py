"""The shipped deployment never turns debug mode on (HTML tracebacks)."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SERVICES = ("backend", "auth", "integrations-googleform")


def _service_block(compose: str, name: str) -> str:
    match = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  \S|\Z)", compose, re.M | re.S)
    assert match, name
    return match.group(1)


def test_deployment_compose_does_not_pin_debug():
    """A value pinned in compose silently wins over the portal (an environment
    value beats the settings store). The code default is off."""
    compose = (REPO / "docker-compose.deployment.yml").read_text()
    for name in SERVICES:
        assert not re.search(r"^\s+DEBUG\s*:", _service_block(compose, name), re.M), name


def test_no_shipped_deployment_file_enables_debug():
    for name in (
        "docker-compose.deployment.yml",
        "docker-compose.sso-deployment.yml",
        ".env.deployment",
    ):
        text = (REPO / name).read_text()
        assert not re.search(r"^\s*DEBUG\s*[:=]\s*[\"']?(true|1|yes|on)", text, re.M | re.I), name
    env = (REPO / ".env.deployment").read_text()
    assert not re.search(r"^DEBUG=", env, re.M)
