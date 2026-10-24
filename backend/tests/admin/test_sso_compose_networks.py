"""Polis's network isolation (docs/sso.md, "Network isolation"): in every compose
file that runs Polis, each network Polis is on is shared with at most one other
service, which is either its own database or one service that calls it. Checked
on the files as written and on what `docker compose config` renders from them
(the deployment with its SSO overlay, and the local development file)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
DEPLOYMENT = "docker-compose.deployment.yml"
SSO_OVERLAY = "docker-compose.sso-deployment.yml"
SSO_LOCAL = "docker-compose.sso.yml"

# the services that call Polis, each over a network of its own: the backend (admin
# API, SCIM; Polis posts SCIM events back), the jobs worker (SCIM resync, releasing
# deleted workspaces' connections) and auth (the sign-in code exchange)
CALLER_NETWORKS = {"backend": "sso-backend", "jobs-worker": "sso-jobs", "auth": "sso-auth"}
# Polis's own: internet egress (nobody else on it) and its database's
EGRESS = "polis-egress"
DATABASE = "polis-db"


def _network_names(service: dict) -> set[str]:
    networks = service.get("networks") or {}
    return set(networks) if isinstance(networks, dict) else set(networks)


def _members(services: dict) -> dict[str, set[str]]:
    """{network: services on it}; a service without `networks` is on `default`."""
    out: dict[str, set[str]] = {}
    for name, service in services.items():
        if service.get("network_mode"):
            continue
        for network in _network_names(service) or {"default"}:
            out.setdefault(network, set()).add(name)
    return out


def _check_deployment(services: dict, networks: dict) -> None:
    members = _members(services)
    polis_networks = _network_names(services["polis"])
    assert polis_networks == {EGRESS, DATABASE, *CALLER_NETWORKS.values()}
    # egress: Polis alone
    assert members[EGRESS] == {"polis"}
    # its database: Polis and polis-postgres, and polis-postgres is on nothing else
    assert members[DATABASE] == {"polis", "polis-postgres"}
    assert _network_names(services["polis-postgres"]) == {DATABASE}
    # one network per caller, shared by Polis and that caller only, no egress
    for caller, network in CALLER_NETWORKS.items():
        assert members[network] == {"polis", caller}, (network, members[network])
        assert networks[network].get("internal") is True, network
        assert _network_names(services[caller]) == {"default", network}, caller
    assert networks[DATABASE].get("internal") is True
    assert not networks[EGRESS].get("internal")
    # nothing else shares a network with Polis
    for network in polis_networks:
        assert len(members[network] - {"polis"}) <= 1, (network, members[network])
    assert "polis" not in members.get("default", set())


def test_the_sso_overlay_gives_each_caller_its_own_network_with_polis():
    overlay = yaml.safe_load((ROOT / SSO_OVERLAY).read_text())
    _check_deployment(overlay["services"], overlay["networks"])


def test_only_services_that_call_polis_get_its_internal_url():
    """The callers list above is the set of services configured to reach Polis."""
    deployment = yaml.safe_load((ROOT / DEPLOYMENT).read_text())["services"]
    callers = {
        name for name, service in deployment.items()
        if "SSO_POLIS_INTERNAL_URL" in (service.get("environment") or {})
    }
    assert callers == set(CALLER_NETWORKS)


def test_the_local_polis_shares_no_network_with_the_local_stack():
    local = yaml.safe_load((ROOT / SSO_LOCAL).read_text())
    services, networks = local["services"], local["networks"]
    members = _members(services)
    assert _network_names(services["polis"]) == {EGRESS, DATABASE}
    assert members[EGRESS] == {"polis"}
    assert members[DATABASE] == {"polis", "polis-postgres"}
    assert networks[DATABASE].get("internal") is True
    # not the local stack's network (Mongo, app-postgres, ...), and no external network
    assert not any((body or {}).get("external") for body in networks.values())
    assert "polis" not in members.get("default", set())
    assert not (_network_names(services["mock-saml"]) & _network_names(services["polis"]))
    # its data no longer lives in app-postgres
    assert services["polis"]["environment"]["DB_URL"].endswith("@polis-postgres:5432/polis")
    assert "app-postgres" not in (ROOT / "scripts" / "sso-dev-setup.sh").read_text()


# ------------------------------------------------------------------ rendered


def _compose_works() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0


def _hermetic(*texts: str) -> dict:
    """The shell's own variables would win over the env file."""
    names = set()
    for text in texts:
        names |= set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", text))
    return {k: v for k, v in os.environ.items() if k not in names and k != "COMPOSE_PROJECT_NAME"}


def _render(workdir: Path, files: list[str], env_lines: list[str]) -> dict:
    env = workdir / "render.env"
    env.write_text("\n".join(env_lines) + "\n")
    args = ["docker", "compose", "-p", "bcssonet", "--env-file", str(env)]
    for name in files:
        args += ["-f", str(workdir / name)]
    done = subprocess.run(
        args + ["config", "--format", "json"],
        capture_output=True, text=True, cwd=workdir,
        env=_hermetic(*((workdir / name).read_text() for name in files)),
    )
    assert done.returncode == 0, done.stderr[-800:]
    return json.loads(done.stdout)


@pytest.mark.skipif(not _compose_works(), reason="needs docker compose v2")
def test_the_rendered_sso_deployment_isolates_polis(tmp_path):
    for name in (DEPLOYMENT, SSO_OVERLAY):
        shutil.copy(ROOT / name, tmp_path / name)
    deployment_text = (ROOT / DEPLOYMENT).read_text() + (ROOT / SSO_OVERLAY).read_text()
    required = sorted(set(re.findall(r"\$\{([A-Z][A-Z0-9_]*):\?", deployment_text)))
    lines = [f"{name}=v{n}" for n, name in enumerate(required)]
    lines += ["SETTINGS_MASTER_KEY=" + "A" * 64, "UMAMI_APP_SECRET=x", "SSO_ENABLED=true"]
    rendered = _render(tmp_path, [DEPLOYMENT, SSO_OVERLAY], lines)
    services, networks = rendered["services"], rendered["networks"]
    _check_deployment(services, networks)
    # every other service of the stack stays off Polis's networks
    polis_networks = _network_names(services["polis"])
    for name, service in services.items():
        if name in ("polis", "polis-postgres", *CALLER_NETWORKS):
            continue
        assert not (_network_names(service) & polis_networks), name
    # the egress network has the pinned subnet a firewall rule can name
    assert networks[EGRESS]["ipam"]["config"][0]["subnet"] == "172.30.78.0/29"
    # the callers keep reaching Polis by name
    for caller in CALLER_NETWORKS:
        assert services[caller]["environment"]["SSO_POLIS_INTERNAL_URL"] == "http://polis:5225"


@pytest.mark.skipif(not _compose_works(), reason="needs docker compose v2")
def test_the_rendered_local_sso_file_isolates_polis(tmp_path):
    shutil.copy(ROOT / SSO_LOCAL, tmp_path / SSO_LOCAL)
    (tmp_path / ".sso-dev").mkdir()
    (tmp_path / ".sso-dev" / "polis.env").write_text(
        # an older setup's line: the compose file's own DB_URL wins
        "DB_URL=postgres://bettercollected:bettercollected@app-postgres:5432/polis\n"
    )
    (tmp_path / ".sso-dev" / "mock-saml.env").write_text("")
    rendered = _render(tmp_path, [SSO_LOCAL], [])
    services, networks = rendered["services"], rendered["networks"]
    members = _members(services)
    assert _network_names(services["polis"]) == {EGRESS, DATABASE}
    assert members[EGRESS] == {"polis"} and members[DATABASE] == {"polis", "polis-postgres"}
    assert networks[DATABASE].get("internal") is True
    assert not any(body.get("external") for body in networks.values())
    assert services["polis"]["environment"]["DB_URL"].endswith("@polis-postgres:5432/polis")
    assert services["polis"]["ports"][0]["host_ip"] == "127.0.0.1"
