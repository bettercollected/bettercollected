"""The public receipt routes (GET and DELETE .../submissions/by-uuid/{number})
are rate limited per client address, unknown numbers more strictly, with a
limit on all clients' unknown numbers together; the number never reaches the
limiter's keys, its stored counters or the logs."""

import logging
import uuid

import pytest
from common.models.standard_form import StandardFormResponse
from httpx import AsyncClient
from loguru import logger
from sqlalchemy import select

from backend.app.container import container
from backend.app.services import receipt_limits
from backend.config import settings
from tests.app.controllers.data import testUser2
from tests.app.controllers.test_privacy_officer import requested  # noqa: F401

WINDOW = 600
T0 = 600 * 3_166_667 + 100.0  # 100 s into a 600 s window
ALICE = {"X-Forwarded-For": "203.0.113.7"}
BOB = {"X-Forwarded-For": "198.51.100.23"}


@pytest.fixture(autouse=True)
def behind_a_proxy(monkeypatch):
    """The test client connects from 127.0.0.1: treat it as the reverse proxy
    whose X-Forwarded-For is believed (the default trusts nobody)."""
    monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "127.0.0.1")


@pytest.fixture()
def clock(monkeypatch):
    now = {"t": T0}
    monkeypatch.setattr(container.rate_limiter(), "_clock", lambda: now["t"])
    return now


@pytest.fixture()
def limits(monkeypatch, clock):
    values = {
        "RECEIPT_REQUESTS_PER_WINDOW": 5,
        "RECEIPT_MISSES_PER_WINDOW": 2,
        "RECEIPT_GLOBAL_MISSES_PER_WINDOW": 1000,
        "RECEIPT_WINDOW_SECONDS": WINDOW,
    }
    for name, value in values.items():
        monkeypatch.setattr(settings.api_settings, name, value)
    return values


@pytest.fixture()
async def receipt(requested):  # noqa: F811
    """The receipt route of a stored response (its deletion is already
    requested) and its number."""
    stored = await container.form_response_repo().get_response(requested["response"])
    base = "/api/v1/workspaces/{ws}/submissions/by-uuid/".format(**requested)
    return {"base": base, "number": stored.submission_uuid, **requested}


def _unknown() -> str:
    return str(uuid.uuid4())


def _assert_rate_limited(response):
    assert response.status_code == 429, response.text
    assert response.json()["code"] == "rate_limited"
    assert int(response.headers["Retry-After"]) > 0


async def test_a_respondent_under_the_limit_reads_their_receipt(
    client: AsyncClient, receipt, limits
):
    url = receipt["base"] + receipt["number"]
    for _ in range(limits["RECEIPT_REQUESTS_PER_WINDOW"]):
        sent = await client.get(url, headers=ALICE)
        assert sent.status_code == 200, sent.text
        assert "form" in sent.json() and "response" in sent.json()


async def test_over_the_limit_answers_429_until_the_window_ends(
    client: AsyncClient, receipt, limits, clock
):
    url = receipt["base"] + receipt["number"]
    for _ in range(limits["RECEIPT_REQUESTS_PER_WINDOW"]):
        assert (await client.get(url, headers=ALICE)).status_code == 200

    refused = await client.get(url, headers=ALICE)
    _assert_rate_limited(refused)
    assert refused.headers["Retry-After"] == "500"
    assert refused.json()["message"] == (
        "Too many receipt lookups. Retry after 500 seconds."
    )
    # nothing of the receipt in the refusal
    assert receipt["number"] not in refused.text

    # another client is counted on its own
    assert (await client.get(url, headers=BOB)).status_code == 200

    # the next window starts afresh
    clock["t"] = T0 + 500
    assert (await client.get(url, headers=ALICE)).status_code == 200


async def test_unknown_numbers_are_limited_much_sooner(
    client: AsyncClient, receipt, limits, clock
):
    url = receipt["base"] + receipt["number"]
    for _ in range(limits["RECEIPT_MISSES_PER_WINDOW"]):
        missed = await client.get(receipt["base"] + _unknown(), headers=ALICE)
        assert missed.status_code == 404, missed.text

    # well under the request limit, but the misses are used up: no lookup at
    # all, not even of a real number, until the window ends
    _assert_rate_limited(await client.get(receipt["base"] + _unknown(), headers=ALICE))
    _assert_rate_limited(await client.get(url, headers=ALICE))
    # ...on the deletion request route too (one budget for both)
    _assert_rate_limited(
        await client.delete(receipt["base"] + _unknown(), headers=ALICE)
    )

    # someone else is not affected
    assert (await client.get(url, headers=BOB)).status_code == 200

    clock["t"] = T0 + 500
    assert (await client.get(url, headers=ALICE)).status_code == 200


async def test_the_deletion_request_route_is_limited_alike(
    client: AsyncClient, receipt, limits
):
    url = receipt["base"] + receipt["number"]
    # already requested: 400, a known number, so never counted as a miss
    for _ in range(limits["RECEIPT_REQUESTS_PER_WINDOW"]):
        assert (await client.delete(url, headers=ALICE)).status_code == 400
    _assert_rate_limited(await client.delete(url, headers=ALICE))

    # each route has its own request limit
    assert (await client.get(url, headers=ALICE)).status_code == 200


async def test_a_deletion_request_by_number_still_works(
    client: AsyncClient, receipt, limits
):
    response = await container.workspace_form_service().submit_response(
        receipt["ws"],
        receipt["form"],
        StandardFormResponse(answers={"q-feedback": {"type": "text", "text": "x"}}),
        testUser2,
    )
    stored = await container.form_response_repo().get_response(response.response_id)
    sent = await client.delete(
        receipt["base"] + stored.submission_uuid, headers=ALICE
    )
    assert sent.status_code == 200, sent.text
    assert sent.json() == {"message": "Request for deletion created successfully."}


async def test_unknown_numbers_of_all_clients_together_are_capped(
    client: AsyncClient, receipt, limits, monkeypatch
):
    monkeypatch.setattr(settings.api_settings, "RECEIPT_GLOBAL_MISSES_PER_WINDOW", 3)
    for n in range(3):  # one miss each from three addresses
        sent = await client.get(
            receipt["base"] + _unknown(), headers={"X-Forwarded-For": f"192.0.2.{n}"}
        )
        assert sent.status_code == 404, sent.text
    fresh = {"X-Forwarded-For": "192.0.2.99"}
    _assert_rate_limited(await client.get(receipt["base"] + _unknown(), headers=fresh))
    _assert_rate_limited(
        await client.get(receipt["base"] + receipt["number"], headers=fresh)
    )


async def test_forwarded_headers_from_an_untrusted_peer_are_ignored(
    client: AsyncClient, receipt, limits, monkeypatch
):
    monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "")
    # every request claims another address: all of them are the peer's
    for n in range(limits["RECEIPT_MISSES_PER_WINDOW"]):
        sent = await client.get(
            receipt["base"] + _unknown(),
            headers={"X-Forwarded-For": f"198.51.100.{n}"},
        )
        assert sent.status_code == 404, sent.text
    forged = {"X-Forwarded-For": "198.51.100.200", "CF-Connecting-IP": "203.0.113.9"}
    _assert_rate_limited(await client.get(receipt["base"] + _unknown(), headers=forged))


async def test_a_spoofed_hop_in_front_of_the_proxy_changes_nothing(
    client: AsyncClient, receipt, limits
):
    for _ in range(limits["RECEIPT_MISSES_PER_WINDOW"]):
        assert (
            await client.get(receipt["base"] + _unknown(), headers=ALICE)
        ).status_code == 404
    spoofed = {"X-Forwarded-For": "192.0.2.1, 203.0.113.7"}
    _assert_rate_limited(await client.get(receipt["base"] + _unknown(), headers=spoofed))


async def test_a_limit_of_zero_is_off(client: AsyncClient, receipt, limits, monkeypatch):
    monkeypatch.setattr(settings.api_settings, "RECEIPT_REQUESTS_PER_WINDOW", 0)
    monkeypatch.setattr(settings.api_settings, "RECEIPT_MISSES_PER_WINDOW", 0)
    monkeypatch.setattr(settings.api_settings, "RECEIPT_GLOBAL_MISSES_PER_WINDOW", 0)
    for _ in range(8):
        assert (
            await client.get(receipt["base"] + _unknown(), headers=ALICE)
        ).status_code == 404
    url = receipt["base"] + receipt["number"]
    assert (await client.get(url, headers=ALICE)).status_code == 200


@pytest.fixture()
def logged(caplog):
    """Every log line of the backend: loguru's and the standard library's."""
    lines = []
    sink = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
    caplog.set_level(logging.DEBUG)
    yield lambda: "\n".join(
        lines
        + [r.getMessage() for r in caplog.records if not r.name.startswith("http")]
    )
    logger.remove(sink)


async def _stored_counter_text() -> str:
    from backend.db.models import RateLimitCounterRow

    async with container.pg_sessionmaker()() as session:
        rows = (await session.execute(select(RateLimitCounterRow))).scalars()
        return "\n".join(repr((r.id, r.doc)) for r in rows)


async def test_no_receipt_number_or_address_in_logs_or_counters(
    client: AsyncClient, receipt, limits, logged
):
    numbers = [receipt["number"]] + [_unknown() for _ in range(3)]
    for number in numbers:
        await client.get(receipt["base"] + number, headers=ALICE)
        await client.delete(receipt["base"] + number, headers=ALICE)
    # the last ones were refused (429): still nothing of them anywhere
    _assert_rate_limited(await client.get(receipt["base"] + numbers[-1], headers=ALICE))

    text = logged()
    assert "Receipt lookup refused" in text  # the refusals are logged...
    for number in numbers:  # ...without the number
        assert number not in text
    assert "203.0.113.7" not in text

    stored = await _stored_counter_text()
    assert stored
    for number in numbers:
        assert number not in stored
    assert "203.0.113" not in stored


async def test_a_lookup_counts_scopes_and_addresses_only():
    from backend.app.services.rate_limiter import Verdict

    class Recording:
        def __init__(self):
            self.calls = []

        async def hit(self, scope, client, limit, window_seconds, amount=1):
            self.calls.append((scope, client, amount))
            return Verdict(True, 0, 1)

    from backend.app.exceptions import HTTPException

    limiter = Recording()
    limits_ = receipt_limits.ReceiptLimits(limiter)
    number = _unknown()
    with pytest.raises(HTTPException):
        async with limits_.lookup(receipt_limits.READ, "2001:db8:1:2::5"):
            raise HTTPException(404, f"no receipt {number}")
    assert limiter.calls == [
        ("receipt-read", "2001:db8:1:2::/64", 1),
        ("receipt-miss", "2001:db8:1:2::/64", 0),
        ("receipt-miss-all", "*", 0),
        ("receipt-miss", "2001:db8:1:2::/64", 1),
        ("receipt-miss-all", "*", 1),
    ]
    assert all(number not in repr(call) for call in limiter.calls)
