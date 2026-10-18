"""The shipped deployment never turns debug mode on (HTML tracebacks)."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SERVICES = ("backend", "auth", "integrations-googleform")


def _service_block(compose: str, name: str) -> str:
    match = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  \S|\Z)", compose, re.M | re.S)
    assert match, name
    return match.group(1)


def test_deployment_compose_sets_debug_false_for_each_service():
    compose = (REPO / "docker-compose.deployment.yml").read_text()
    for name in SERVICES:
        assert re.search(r'^\s+DEBUG: "false"$', _service_block(compose, name), re.M), name


def test_no_shipped_deployment_file_enables_debug():
    for name in (
        "docker-compose.deployment.yml",
        "docker-compose.sso-deployment.yml",
        ".env.deployment",
    ):
        text = (REPO / name).read_text()
        assert not re.search(r"^\s*DEBUG\s*[:=]\s*[\"']?(true|1|yes|on)", text, re.M | re.I), name
    env = (REPO / ".env.deployment").read_text()
    assert re.search(r"^DEBUG=false$", env, re.M)
