"""Health: the jobs worker apart from the API, which instances write MongoDB, and
the address gate on the configuration page (count and the viewer's own entry only)."""

from __future__ import annotations

import ipaddress
import re

import pytest
from sqlalchemy import text

from backend.admin.asgi import get_admin_application
from backend.admin.gate.settings import GateSettings
from backend.admin.services import pages as pg
from tests.admin.conftest import needs_postgres
from tests.admin.test_portal_pages import signed_in, superuser  # noqa: F401 - fixture


# -- no database -------------------------------------------------------------------------
@pytest.mark.parametrize(
    "service, instance, expected",
    [
        ("backend", "backend.jobs:3f9c1d2ab7e4", "jobs worker"),
        ("backend", "backend:3f9c1d2ab7e4", ""),
        ("auth", "backend.jobs:abc", ""),  # another service's name never labels
        ("auth", "auth.jobs:abc", "jobs worker"),
        ("backend", "backend.<script>:abc", ""),  # only the known roles are named
        ("backend", "backend.evil:abc", ""),
    ],
)
def test_the_component_comes_from_the_known_roles_only(service, instance, expected):
    assert pg.component_of(service, instance) == expected


def test_write_stores_only_count_when_they_name_mongo():
    beat = lambda stores: pg.Heartbeat("backend", "i", 0, None, False, 0, 1, True, "", stores)
    assert beat("mongo").writes_mongo and beat("mongo,postgres").writes_mongo
    assert not beat("postgres").writes_mongo and not beat("").writes_mongo
    assert pg._write_stores("mongo; drop table") == ""
    assert pg._write_stores(None) == ""


def _gate(ips: str, gateway: str = ""):
    return GateSettings.from_env({"ADMIN_ALLOWED_IPS": ips, "ADMIN_EDGE_GATEWAY": gateway})


def test_the_viewer_sees_the_count_and_the_entry_that_lets_them_in_only():
    access = pg.admin_access(_gate("127.0.0.1/32,10.20.30.0/24,2001:db8::/32"), "10.20.30.7")
    assert access.entries == 3 and access.address == "10.20.30.7"
    assert access.matched_entry == "10.20.30.0/24" and not access.via_gateway


def test_the_gateway_entry_is_not_counted_and_is_named_as_such():
    gate = _gate("127.0.0.1/32", "172.30.0.1")
    access = pg.admin_access(gate, "172.30.0.1")
    assert access.entries == 1 and access.matched_entry is None and access.via_gateway
    assert pg.admin_access(gate, "127.0.0.1").matched_entry == "127.0.0.1/32"


def test_nothing_is_shown_without_a_gate_and_a_bad_address_matches_nothing():
    assert pg.admin_access(None, "127.0.0.1") is None
    access = pg.admin_access(_gate("127.0.0.1/32"), "not an address")
    assert access.address is None and access.matched_entry is None
    # an IPv6 client never matches an IPv4 entry
    v6 = pg.admin_access(_gate("0.0.0.0/1"), "::1")
    assert v6.matched_entry is None
    assert ipaddress.ip_address("::1").version == 6


# -- the pages ---------------------------------------------------------------------------
@needs_postgres
async def test_health_names_the_jobs_worker_and_its_state(portal, app, superuser):
    b = await signed_in(portal, app)
    none = (await b.get("/health")).text
    section = none.split("<h2>Jobs worker</h2>", 1)[1].split("<h2>", 1)[0]
    assert "No report" in section and "Reporting" not in section
    async with superuser.begin() as conn:
        await conn.execute(text(
            "INSERT INTO settings.service_state (service, instance, reported_at, revision_applied) "
            "VALUES ('backend', 'backend.jobs:jw1', now() - interval '1 hour', 0), "
            "('backend', 'backend:api1', now(), 0)"))
    try:
        stopped = (await b.get("/health")).text
        assert "Stopped" in stopped.split("<h2>Jobs worker</h2>", 1)[1].split("<h2>", 1)[0]
        async with superuser.begin() as conn:
            await conn.execute(text(
                "UPDATE settings.service_state SET reported_at = now() WHERE instance = 'backend.jobs:jw1'"))
        html = (await b.get("/health")).text
        section = html.split("<h2>Jobs worker</h2>", 1)[1].split("<h2>", 1)[0]
        assert "Reporting" in section and "1 instance(s)" in section
        jobs = re.search(r'<th scope="row">backend <span class="tag">jobs worker</span></th>.*?</tr>', html, re.S)
        assert jobs and "backend.jobs:jw1" in jobs.group(0)
        api = re.search(r'<th scope="row">backend</th>\s*<td>backend:api1</td>.*?</tr>', html, re.S)
        assert api and "jobs worker" not in api.group(0)
        assert "What is waiting in the queue is not shown" in section
    finally:
        async with superuser.begin() as conn:
            await conn.execute(text("DELETE FROM settings.service_state WHERE instance IN ('backend.jobs:jw1', 'backend:api1')"))
    await b.aclose()


@needs_postgres
async def test_health_says_which_running_instances_still_write_mongodb(portal, app, superuser):
    b = await signed_in(portal, app)
    html = (await b.get("/health")).text
    assert "No service has reported yet." in html.split("<h2>MongoDB</h2>", 1)[1].split("<h2>", 1)[0]
    async with superuser.begin() as conn:
        await conn.execute(text(
            "INSERT INTO settings.service_state (service, instance, reported_at, revision_applied, write_stores) "
            "VALUES ('backend', 'w-pg', now(), 0, 'postgres'), "
            "('auth', 'w-mongo-old', now() - interval '1 hour', 0, 'mongo')"))
    try:
        section = (await b.get("/health")).text.split("<h2>MongoDB</h2>", 1)[1].split("<h2>", 1)[0]
        assert "No running service reports writing MongoDB." in section  # the stopped one does not count
        async with superuser.begin() as conn:
            await conn.execute(text(
                "UPDATE settings.service_state SET reported_at = now() WHERE instance = 'w-mongo-old'"))
        html = (await b.get("/health")).text
        section = html.split("<h2>MongoDB</h2>", 1)[1].split("<h2>", 1)[0]
        assert "1 running instance(s) still write MongoDB" in section
        assert "cannot reach MongoDB" in section
        row = re.search(r"<td>w-mongo-old</td>.*?</tr>", html, re.S).group(0)
        assert '<span class="warn">mongo</span>' in row
        row = re.search(r"<td>w-pg</td>.*?</tr>", html, re.S).group(0)
        assert "<td>postgres</td>" in row
    finally:
        async with superuser.begin() as conn:
            await conn.execute(text("DELETE FROM settings.service_state WHERE instance IN ('w-pg', 'w-mongo-old')"))
    await b.aclose()


@needs_postgres
async def test_config_shows_the_gate_count_and_the_viewers_entry_never_the_list(portal):
    app = get_admin_application(_gate("127.0.0.1/32,10.20.30.0/24,192.0.2.0/24"), portal=portal)
    b = await signed_in(portal, app)
    html = (await b.get("/config")).text
    section = html.split("<h2>Address gate</h2>", 1)[1]
    assert re.search(r"Allowed networks</dt><dd>3</dd>", section)
    assert "<code>127.0.0.1</code>" in section and "<code>127.0.0.1/32</code>" in section
    assert "10.20.30" not in html and "192.0.2" not in html
    # the super admins stay listed, as before
    assert "<h2>Super admins</h2>" in html and "admin@example.org" in html
    await b.aclose()
