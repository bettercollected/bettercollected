"""Rate limits of the sign-in code mail (workspace and creator routes) and of
the respondent submit route (services/respondent_limits.py): per address and
per client, one instance-wide circuit breaker for code mail, and per client and
form on submit; no budget that many people share (a workspace, a form), since
that would let a few networks block everyone. A refusal is 429 ``rate_limited``
with ``Retry-After`` and never depends on whether the address has an account."""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from loguru import logger
from sqlalchemy import select

from backend.app.container import container
from backend.app.services import respondent_limits as limits
from backend.app.services.respondent_limits import address_limit_key, client_key
from backend.config import settings
from backend.db.models import RateLimitCounterRow
from common.exceptions.http import HTTPException as CommonHTTPException

SENT = {"message": "Email set to be sent"}
ALICE = {"X-Forwarded-For": "203.0.113.7"}
BOB = {"X-Forwarded-For": "198.51.100.23"}


@pytest.fixture(autouse=True)
def behind_a_proxy(monkeypatch):
    """The test client connects from 127.0.0.1: treat it as the reverse proxy
    whose X-Forwarded-For is believed (the default trusts nobody)."""
    monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "127.0.0.1")


_SETTING = {
    "CODE_PER_CLIENT": "CODE_MAIL_PER_CLIENT_PER_HOUR",
    "CODE_PER_ADDRESS": "CODE_MAIL_PER_ADDRESS_PER_HOUR",
    "SUBMIT_PER_CLIENT_FORM": "SUBMIT_PER_CLIENT_FORM_PER_MINUTE",
}


def _set(monkeypatch, name, limit, window=None):
    """Set a per-person budget (a live setting; 0 turns the limit off)."""
    monkeypatch.setattr(settings.api_settings, _SETTING[name], limit)


def _mail(n: int, domain="example.com") -> str:
    return f"person{n}@{domain}"


def _from(n: int) -> dict:
    return {"X-Forwarded-For": f"203.0.113.{n}"}


async def _workspace_code(client, workspace, address, headers=None, **params):
    return await client.post(
        f"/api/v1/workspaces/{getattr(workspace, 'id', workspace)}/auth/otp/send",
        params={"receiver_email": address, **params},
        headers=headers or ALICE,
    )


async def _creator_code(client, address, headers=None, **params):
    return await client.post(
        "/api/v1/auth/creator/otp/send",
        params={"receiver_email": address, **params},
        headers=headers or ALICE,
    )


def _assert_rate_limited(response, lang="en"):
    assert response.status_code == 429, response.text
    body = response.json()
    assert body["code"] == "rate_limited"
    assert int(response.headers["Retry-After"]) > 0
    assert body["retry_after"] == int(response.headers["Retry-After"])
    if lang == "nl":
        assert body["message"].startswith("Te veel pogingen")
    else:
        assert body["message"].startswith("Too many attempts")
    return body


def _mailing():
    return patch(
        "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
    )


async def _counter_count() -> int:
    async with container.pg_engine().connect() as conn:
        return len((await conn.execute(select(RateLimitCounterRow))).all())


class TestKeys:
    @pytest.mark.parametrize(
        "spelling",
        [
            "Person@Example.COM",
            " person@example.com ",
            "person+news@example.com",
            "PERSON+a+b@EXAMPLE.com",
        ],
    )
    def test_one_mailbox_is_one_key(self, spelling):
        assert address_limit_key(spelling) == "person@example.com"

    @pytest.mark.parametrize(
        "spelling",
        [
            "first.last@gmail.com",
            "f.i.r.s.t.l.a.s.t@gmail.com",
            "First.Last+news@GMail.com",
            "firstlast@googlemail.com",
            "first.last@googlemail.com",
        ],
    )
    def test_gmail_dots_and_googlemail_are_ignored(self, spelling):
        assert address_limit_key(spelling) == "firstlast@gmail.com"

    def test_other_providers_keep_their_dots(self):
        assert address_limit_key("a.b@example.com") != address_limit_key("ab@example.com")

    def test_an_internationalised_domain_and_its_punycode_agree(self):
        assert address_limit_key("a@bücher.example") == address_limit_key(
            "a@xn--bcher-kva.example"
        )

    def test_another_mailbox_is_another_key(self):
        assert address_limit_key("a@example.com") != address_limit_key("b@example.com")
        assert address_limit_key("a@example.com") != address_limit_key("a@example.org")

    def test_a_bare_plus_local_part_is_kept(self):
        assert address_limit_key("+@example.com") == "+@example.com"

    def test_an_ipv6_client_is_keyed_by_its_64(self):
        assert client_key("2001:db8:1:2::1") == "2001:db8:1:2::/64"
        assert client_key("2001:db8:1:2:ffff:aaaa::9") == "2001:db8:1:2::/64"
        assert client_key("2001:db8:1:3::1") == "2001:db8:1:3::/64"
        assert client_key("2001:db8:2::1") == "2001:db8:2::/64"

    def test_an_ipv4_client_is_kept_and_no_client_is_unknown(self):
        assert client_key("203.0.113.7") == "203.0.113.7"
        assert client_key(None) == "unknown"
        assert client_key("not an address") == "unknown"


class TestCodePerAddress:
    async def test_the_fourth_request_in_the_hour_is_refused(
        self, client: AsyncClient, workspace
    ):
        assert settings.api_settings.CODE_MAIL_PER_ADDRESS_PER_HOUR == 3
        assert limits.CODE_PER_ADDRESS[1] == 3600
        sent = AsyncMock(return_value=SENT)
        with patch("common.services.http_client.HttpClient.get", sent):
            for _ in range(3):
                ok = await _workspace_code(client, workspace, "x@example.com")
                assert ok.status_code == 200, ok.text
            refused = await _workspace_code(client, workspace, "x@example.com")
        _assert_rate_limited(refused)
        # the refused request reached no mail
        assert sent.await_count == 3

    async def test_the_window_ends_and_the_address_may_ask_again(
        self, client: AsyncClient, workspace, rate_limit_clock
    ):
        with _mailing():
            for _ in range(3):
                await _workspace_code(client, workspace, "x@example.com")
            refused = await _workspace_code(client, workspace, "x@example.com")
            wait = int(refused.headers["Retry-After"])
            assert 1 <= wait <= 3600
            rate_limit_clock["now"] += wait + 1
            again = await _workspace_code(client, workspace, "x@example.com")
        assert again.status_code == 200, again.text

    async def test_another_address_is_not_affected(self, client: AsyncClient, workspace):
        with _mailing():
            for _ in range(4):
                await _workspace_code(client, workspace, "x@example.com")
            other = await _workspace_code(client, workspace, "y@example.com")
        assert other.status_code == 200, other.text

    async def test_spelling_variants_are_one_address(
        self, client: AsyncClient, workspace
    ):
        with _mailing():
            for spelling in ("x@example.com", "X@Example.com", "x+1@example.com"):
                ok = await _workspace_code(client, workspace, spelling)
                assert ok.status_code == 200, ok.text
            refused = await _workspace_code(client, workspace, "x+2@EXAMPLE.com")
        _assert_rate_limited(refused)

    async def test_gmail_variants_are_one_address(self, client: AsyncClient, workspace):
        with _mailing():
            for spelling in ("first.last@gmail.com", "firstlast@googlemail.com"):
                ok = await _workspace_code(client, workspace, spelling)
                assert ok.status_code == 200, ok.text
            await _workspace_code(client, workspace, "f.i.r.s.t.last@gmail.com")
            refused = await _workspace_code(client, workspace, "first.last+x@gmail.com")
        _assert_rate_limited(refused)

    async def test_the_budget_is_shared_by_the_workspace_and_creator_routes(
        self, client: AsyncClient, workspace
    ):
        sent = AsyncMock(return_value=SENT)
        with patch("common.services.http_client.HttpClient.get", sent):
            await _workspace_code(client, workspace, "x@example.com")
            await _creator_code(client, "x@example.com")
            await _workspace_code(client, workspace, "x@example.com")
            refused_creator = await _creator_code(client, "x@example.com")
            refused_workspace = await _workspace_code(client, workspace, "x@example.com")
        _assert_rate_limited(refused_creator)
        _assert_rate_limited(refused_workspace)
        assert sent.await_count == 3

    async def test_a_refused_request_keeps_the_address_refused(
        self, client: AsyncClient, workspace
    ):
        with _mailing():
            for _ in range(3):
                await _workspace_code(client, workspace, "x@example.com")
            for _ in range(5):
                refused = await _workspace_code(client, workspace, "x@example.com")
                assert refused.status_code == 429


class TestCodePerClient:
    async def test_the_default_is_sixty_an_hour(self):
        assert settings.api_settings.CODE_MAIL_PER_CLIENT_PER_HOUR == 60
        assert limits.CODE_PER_CLIENT[1] == 3600

    async def test_the_request_over_the_budget_of_a_client_is_refused(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        _set(monkeypatch, "CODE_PER_CLIENT", 10)
        sent = AsyncMock(return_value=SENT)
        with patch("common.services.http_client.HttpClient.get", sent):
            for n in range(10):
                ok = await _workspace_code(client, workspace, _mail(n))
                assert ok.status_code == 200, ok.text
            refused = await _workspace_code(client, workspace, _mail(11))
            other_client = await _workspace_code(
                client, workspace, _mail(12), headers=BOB
            )
        _assert_rate_limited(refused)
        assert sent.await_count == 11
        assert other_client.status_code == 200, other_client.text

    async def test_a_school_behind_one_address_is_not_locked_out_at_ten(
        self, client: AsyncClient, workspace
    ):
        """The default budget is 60: eleven different mailboxes behind one
        address all get their code."""
        with _mailing():
            for n in range(11):
                ok = await _workspace_code(client, workspace, _mail(n))
                assert ok.status_code == 200, ok.text

    async def test_zero_turns_the_client_limit_off(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        _set(monkeypatch, "CODE_PER_CLIENT", 0)
        with _mailing():
            for n in range(15):
                ok = await _workspace_code(client, workspace, _mail(n))
                assert ok.status_code == 200, ok.text
        # the mailbox limit still holds
        with _mailing():
            for _ in range(3):
                await _workspace_code(client, workspace, "x@example.com")
            refused = await _workspace_code(client, workspace, "x@example.com")
        _assert_rate_limited(refused)

    async def test_zero_turns_the_mailbox_limit_off(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        _set(monkeypatch, "CODE_PER_ADDRESS", 0)
        with _mailing():
            for _ in range(6):
                ok = await _workspace_code(client, workspace, "x@example.com")
                assert ok.status_code == 200, ok.text

    async def test_the_budgets_are_read_on_every_request(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        _set(monkeypatch, "CODE_PER_CLIENT", 1)
        with _mailing():
            assert (await _workspace_code(client, workspace, _mail(1))).status_code == 200
            _assert_rate_limited(await _workspace_code(client, workspace, _mail(2)))
            # an operator raises it: the next request is let through, no restart
            _set(monkeypatch, "CODE_PER_CLIENT", 5)
            ok = await _workspace_code(client, workspace, _mail(3))
        assert ok.status_code == 200, ok.text

    async def test_the_creator_route_counts_the_same_client(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        _set(monkeypatch, "CODE_PER_CLIENT", 10)
        with _mailing():
            for n in range(5):
                await _workspace_code(client, workspace, _mail(n))
            for n in range(5, 10):
                ok = await _creator_code(client, _mail(n))
                assert ok.status_code == 200, ok.text
            refused = await _creator_code(client, _mail(11))
        _assert_rate_limited(refused)

    async def test_an_ipv6_device_is_one_client_by_its_64(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        """One /64 is one client (what a subscriber or device gets): rotating
        through its addresses does not multiply the limit, while another /64
        of the same carrier pool has its own budget."""
        _set(monkeypatch, "CODE_PER_CLIENT", 2)
        with _mailing():
            for n, host in enumerate(("2001:db8:1:2::1", "2001:db8:1:2:aaaa::2")):
                ok = await _workspace_code(
                    client, workspace, _mail(n), headers={"X-Forwarded-For": host}
                )
                assert ok.status_code == 200, ok.text
            refused = await _workspace_code(
                client,
                workspace,
                _mail(3),
                headers={"X-Forwarded-For": "2001:db8:1:2:7777::9"},
            )
            same_site_other_device = await _workspace_code(
                client,
                workspace,
                _mail(4),
                headers={"X-Forwarded-For": "2001:db8:1:3::9"},
            )
        _assert_rate_limited(refused)
        assert same_site_other_device.status_code == 200, same_site_other_device.text


class TestUntrustedProxy:
    """A proxy on a private address that is not in TRUSTED_PROXIES would make
    every user one client: such a request is "unknown" and not limited per
    client, while the limits that name no client still apply."""

    @pytest.fixture(autouse=True)
    def no_trusted_proxy(self, monkeypatch):
        monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "")

    async def test_code_mail_has_no_per_client_limit_but_keeps_the_others(
        self, client: AsyncClient, workspace
    ):
        sent = AsyncMock(return_value=SENT)
        with patch("common.services.http_client.HttpClient.get", sent):
            for n in range(15):
                ok = await _workspace_code(client, workspace, _mail(n), headers=_from(n + 1))
                assert ok.status_code == 200, ok.text
            for _ in range(3):
                await _workspace_code(client, workspace, "x@example.com")
            refused = await _workspace_code(client, workspace, "x@example.com")
        _assert_rate_limited(refused)

    async def test_the_instance_breaker_still_holds(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        monkeypatch.setattr(settings.api_settings, "CODE_MAIL_PER_HOUR", 12)
        with _mailing():
            for n in range(12):
                ok = await _workspace_code(client, workspace, _mail(n), headers=_from(n + 1))
                assert ok.status_code == 200, ok.text
            refused = await _workspace_code(client, workspace, _mail(99), headers=_from(99))
        _assert_rate_limited(refused)

    async def test_the_creator_route_too(self, client: AsyncClient):
        with _mailing():
            for n in range(12):
                ok = await _creator_code(client, _mail(n), headers=_from(n + 1))
                assert ok.status_code == 200, ok.text

    async def test_a_direct_client_without_forwarding_headers_is_still_counted(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        """No forwarding header: the peer is the client (a direct connection)."""
        _set(monkeypatch, "CODE_PER_CLIENT", 10)
        with _mailing():
            for n in range(10):
                ok = await client.post(
                    f"/api/v1/workspaces/{workspace.id}/auth/otp/send",
                    params={"receiver_email": _mail(n)},
                )
                assert ok.status_code == 200, ok.text
            refused = await client.post(
                f"/api/v1/workspaces/{workspace.id}/auth/otp/send",
                params={"receiver_email": _mail(11)},
            )
        _assert_rate_limited(refused)

    async def test_submit_is_not_limited_per_client(
        self, client: AsyncClient, workspace, published_form, monkeypatch
    ):
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 1, 60)
        for n in range(4):
            sent = await TestSubmit._post(
                client, workspace, published_form.form_id, _from(n + 1)
            )
            assert sent.status_code != 429, sent.text


class TestInstanceBreaker:
    """The only budget everyone shares: far above normal use, loud when it
    trips, and the only brake on the code mail reaching random addresses."""

    async def test_the_default_is_twenty_thousand_an_hour(self):
        assert settings.api_settings.CODE_MAIL_PER_HOUR == 20000
        assert limits.CODE_ALL_SCOPE == "code-mail-all"

    async def test_it_refuses_every_code_request_once_used_up_and_logs_an_error_once(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        monkeypatch.setattr(settings.api_settings, "CODE_MAIL_PER_HOUR", 3)
        records = []
        handler = logger.add(lambda m: records.append(m.record), level="ERROR")
        try:
            with _mailing():
                for n in range(3):
                    ok = await _workspace_code(client, workspace, _mail(n), headers=_from(n + 1))
                    assert ok.status_code == 200, ok.text
                for n in range(3, 6):
                    refused = await _workspace_code(
                        client, workspace, _mail(n), headers=_from(n + 1)
                    )
                    _assert_rate_limited(refused)
                creator = await _creator_code(client, _mail(7), headers=_from(70))
        finally:
            logger.remove(handler)
        _assert_rate_limited(creator)
        tripped = [r for r in records if "circuit breaker" in r["message"]]
        assert len(tripped) == 1
        assert "example.com" not in tripped[0]["message"]

    async def test_zero_turns_it_off(self, client: AsyncClient, workspace, monkeypatch):
        monkeypatch.setattr(settings.api_settings, "CODE_MAIL_PER_HOUR", 0)
        before = await _counter_count()
        with _mailing():
            ok = await _workspace_code(client, workspace, "x@example.com")
        assert ok.status_code == 200, ok.text
        scopes = await _counter_count()
        # a client and an address counter, none for the breaker
        assert scopes - before == 2

    async def test_no_budget_is_shared_by_a_workspace_creators_or_a_form(self):
        for name in (
            "CODE_PER_WORKSPACE",
            "CODE_CREATOR",
            "SUBMIT_PER_FORM",
            "CODE_ALL",
        ):
            assert not hasattr(limits, name), name


class TestRefusalDoesNotTellAccounts:
    """The limits are counted before the auth service is asked anything, so
    what comes back cannot depend on whether the address has an account."""

    async def test_a_known_and_an_unknown_address_are_refused_alike(
        self, client: AsyncClient, workspace
    ):
        # auth answers 200 for the known address and fails for the other: the
        # first three requests of each differ (200 / 502), the refusal must not
        def reaction(url, **kwargs):
            if kwargs["params"]["receiver_email"].startswith("known"):
                return SENT
            raise CommonHTTPException(404, "no account")

        sent = AsyncMock(side_effect=reaction)
        with patch("common.services.http_client.HttpClient.get", sent):
            for _ in range(3):
                await _workspace_code(client, workspace, "known@example.com")
                await _workspace_code(client, workspace, "unknown@example.com")
            known = await _workspace_code(client, workspace, "known@example.com")
            unknown = await _workspace_code(client, workspace, "unknown@example.com")
        assert known.status_code == unknown.status_code == 429
        assert known.headers["Retry-After"] == unknown.headers["Retry-After"]
        assert known.json() == unknown.json()
        assert "example.com" not in known.text

    async def test_the_breaker_refuses_known_and_unknown_addresses_alike(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        monkeypatch.setattr(settings.api_settings, "CODE_MAIL_PER_HOUR", 1)
        with _mailing():
            await _workspace_code(client, workspace, "seed@example.com", headers=_from(1))
            one = await _workspace_code(client, workspace, "known@example.com", headers=_from(2))
            two = await _workspace_code(client, workspace, "nobody@example.org", headers=_from(3))
        assert one.status_code == two.status_code == 429
        assert one.json()["code"] == two.json()["code"]


class TestWorkspaceMustExist:
    async def test_a_workspace_that_does_not_exist_counts_nothing(
        self, client: AsyncClient
    ):
        before = await _counter_count()
        with _mailing():
            for _ in range(15):
                response = await _workspace_code(
                    client, str(uuid.uuid4()), "x@example.com"
                )
                assert response.status_code != 429
        assert await _counter_count() == before

    async def test_an_existing_one_counts(self, client: AsyncClient, workspace):
        before = await _counter_count()
        with _mailing():
            await _workspace_code(client, workspace, "x@example.com")
        assert await _counter_count() > before


class TestRefusalWording:
    async def test_english_by_default_dutch_when_asked(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        _set(monkeypatch, "CODE_PER_ADDRESS", 1)
        with _mailing():
            await _workspace_code(client, workspace, "x@example.com")  # uses it up
        english = await _workspace_code(client, workspace, "x@example.com")
        dutch = await _workspace_code(client, workspace, "x@example.com", locale="nl")
        dutch_tag = await _creator_code(client, "x@example.com", locale="nl-NL")
        _assert_rate_limited(english)
        _assert_rate_limited(dutch, "nl")
        _assert_rate_limited(dutch_tag, "nl")
        assert dutch.json()["message"].endswith("opnieuw.")

    async def test_the_message_has_no_address_in_it(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        _set(monkeypatch, "CODE_PER_ADDRESS", 1)
        with _mailing():
            await _workspace_code(client, workspace, "private.person@example.com")
        refused = await _workspace_code(client, workspace, "private.person@example.com")
        assert "private" not in refused.text
        assert "example.com" not in refused.text

    async def test_the_wait_is_in_minutes_or_hours(self):
        from backend.app.services.rate_limiter import Verdict

        def message(seconds, locale=None):
            return limits.too_many(Verdict(False, 4, seconds), locale).content["message"]

        assert "a minute" in message(30)
        assert "10 minutes" in message(600)
        assert "3 hours" in message(3 * 3600)
        assert "10 minuten" in message(600, "nl")
        assert "een minuut" in message(30, "nl")


class TestSubmit:
    """``POST /workspaces/{w}/forms/{f}/response``."""

    @staticmethod
    async def _post(client, workspace, form_id, headers=None, **kwargs):
        return await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/response",
            data={"response": json.dumps({"answers": {}})},
            headers=headers or ALICE,
            **kwargs,
        )

    async def test_the_number(self):
        assert settings.api_settings.SUBMIT_PER_CLIENT_FORM_PER_MINUTE == 30
        assert limits.SUBMIT_PER_CLIENT_FORM[1] == 60

    async def test_a_client_is_limited_per_form_with_retry_after(
        self, client: AsyncClient, workspace, published_form, monkeypatch
    ):
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 3, 60)
        for _ in range(3):
            sent = await self._post(client, workspace, published_form.form_id)
            assert sent.status_code != 429, sent.text
        refused = await self._post(client, workspace, published_form.form_id)
        body = _assert_rate_limited(refused)
        assert body["retry_after"] <= 60
        # another client is not affected
        other = await self._post(client, workspace, published_form.form_id, BOB)
        assert other.status_code != 429, other.text

    async def test_the_window_ends(
        self,
        client: AsyncClient,
        workspace,
        published_form,
        monkeypatch,
        rate_limit_clock,
    ):
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 1, 60)
        await self._post(client, workspace, published_form.form_id)
        refused = await self._post(client, workspace, published_form.form_id)
        wait = int(_assert_rate_limited(refused)["retry_after"])
        rate_limit_clock["now"] += wait + 1
        again = await self._post(client, workspace, published_form.form_id)
        assert again.status_code != 429, again.text

    async def test_there_is_no_budget_the_clients_of_a_form_share(
        self, client: AsyncClient, workspace, published_form
    ):
        """Many different clients on one form: nobody is refused, however many
        (a shared form budget would let a few networks lock everyone out)."""
        for n in range(60):
            sent = await self._post(
                client,
                workspace,
                published_form.form_id,
                {"X-Forwarded-For": f"198.51.100.{n + 1}"},
            )
            assert sent.status_code != 429, sent.text

    async def test_one_client_on_one_form_only_uses_that_forms_budget(
        self, client: AsyncClient, workspace, published_form, monkeypatch
    ):
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 2, 60)
        other_form = await container.workspace_form_service().create_form(
            workspace.id, _another_form(), _owner()
        )
        other_published = await container.workspace_form_service().publish_form(
            workspace.id, other_form.form_id, _owner()
        )
        for _ in range(2):
            await self._post(client, workspace, published_form.form_id)
        assert (
            await self._post(client, workspace, published_form.form_id)
        ).status_code == 429
        clear = await self._post(client, workspace, other_published.form_id)
        assert clear.status_code != 429, clear.text

    async def test_a_busy_form_is_not_throttled(
        self, client: AsyncClient, workspace, published_form
    ):
        """Real traffic: a hundred respondents from a hundred addresses within
        the minute, and one address submitting a few times (retries, a shared
        office address), pass with the shipped numbers."""
        for n in range(100):
            sent = await self._post(
                client,
                workspace,
                published_form.form_id,
                {"X-Forwarded-For": f"198.51.100.{n + 1}"},
            )
            assert sent.status_code != 429, sent.text
        for _ in range(10):
            sent = await self._post(
                client, workspace, published_form.form_id, {"X-Forwarded-For": "192.0.2.5"}
            )
            assert sent.status_code != 429, sent.text

    async def test_the_limit_runs_before_the_body_is_read(
        self, client: AsyncClient, workspace, published_form, monkeypatch
    ):
        """An over-budget request is refused without its body being parsed: a
        multipart body that cannot be parsed (a handler or a dependency would
        answer 400 or 422 for it) still gets the 429, and nothing is stored."""
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 1, 60)
        await container.respondent_limits().submit(
            "203.0.113.7", str(workspace.id), str(published_form.form_id)
        )  # the client's one request is used up
        service = container.workspace_form_service()
        with patch.object(service, "submit_response", AsyncMock()) as submit:
            garbage = await client.post(
                f"/api/v1/workspaces/{workspace.id}/forms/{published_form.form_id}/response",
                content=b"--nope\r\nnot a part",
                headers={**ALICE, "Content-Type": "multipart/form-data; boundary=zzz"},
            )
            missing = await self._post(client, workspace, published_form.form_id)
        _assert_rate_limited(garbage)
        _assert_rate_limited(missing)
        submit.assert_not_awaited()

    async def test_a_form_that_does_not_exist_counts_nothing(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 1, 60)
        before = await _counter_count()
        for _ in range(4):
            response = await client.post(
                f"/api/v1/workspaces/{workspace.id}/forms/{uuid.uuid4()}/response",
                data={"response": json.dumps({"answers": {}})},
                headers=ALICE,
            )
            assert response.status_code != 429, response.text
        assert await _counter_count() == before

    async def test_the_refusal_is_readable_from_another_origin(
        self, client: AsyncClient, workspace, published_form, monkeypatch
    ):
        """The middleware sits inside CORS: the 429 carries the CORS headers
        the answers of the route carry."""
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 1, 60)
        await container.respondent_limits().submit(
            "203.0.113.7", str(workspace.id), str(published_form.form_id)
        )
        origin = "http://localhost:3000"
        limited = await self._post(
            client, workspace, published_form.form_id, {**ALICE, "Origin": origin}
        )
        assert limited.status_code == 429
        routed = await client.get(
            f"/api/v1/workspaces/{workspace.id}", headers={"Origin": origin}
        )
        assert limited.headers.get("access-control-allow-origin") == routed.headers.get(
            "access-control-allow-origin"
        )


def _owner():
    from tests.app.controllers.data import testUser

    return testUser


def _another_form():
    from common.models.standard_form import StandardForm
    from tests.app.controllers.data import formData

    return StandardForm(**formData)


class TestSubmissionsApiIsUnaffected:
    async def test_a_key_does_not_pass_the_respondent_limits(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        """The Submissions API calls the submit service directly: with the
        respondent route's budget used up, a key still submits, and the
        respondent limiter is never asked."""
        from tests.app.controllers.test_submissions_api import (
            _body,
            _form,
            _key,
            _submit,
        )

        monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 1, 60)
        spy = AsyncMock()
        with patch.object(type(container.respondent_limits()), "submit", spy), patch.object(
            type(container.respondent_limits()), "code_mail", spy
        ):
            response = await _submit(client, token, form_id, _body({}))
        # the API's own answer (validation or created), never the 429 of the
        # respondent route, and the respondent limiter was not asked
        assert response.status_code != 429, response.text
        spy.assert_not_awaited()


class TestStorage:
    async def test_no_address_or_client_is_stored_in_a_counter(
        self, client: AsyncClient, workspace
    ):
        with _mailing():
            await _workspace_code(client, workspace, "secret.person@example.com")
        async with container.pg_engine().connect() as conn:
            rows = (await conn.execute(select(RateLimitCounterRow))).all()
        assert rows
        flat = json.dumps([[str(value) for value in row] for row in rows])
        assert "secret" not in flat
        assert "example.com" not in flat
        assert "203.0.113.7" not in flat

    async def test_limits_are_hit_in_order_and_a_refusal_stops_the_rest(
        self, monkeypatch
    ):
        calls = []
        real = container.rate_limiter()
        real_hit = real.hit

        async def hit(scope, client, limit, window, amount=1):
            calls.append(scope)
            return await real_hit(scope, client, limit, window, amount=amount)

        monkeypatch.setattr(real, "hit", hit)
        _set(monkeypatch, "CODE_PER_ADDRESS", 1)
        await container.respondent_limits().code_mail("203.0.113.8", "x@example.com")
        calls.clear()
        with pytest.raises(Exception) as refused:
            await container.respondent_limits().code_mail(
                "203.0.113.7", "x@example.com"
            )
        assert refused.value.status_code == 429
        assert calls == ["code-mail-client", "code-mail-address"]

    async def test_an_unknown_client_skips_the_client_limit(self, monkeypatch):
        calls = []
        real = container.rate_limiter()
        real_hit = real.hit

        async def hit(scope, client, limit, window, amount=1):
            calls.append(scope)
            return await real_hit(scope, client, limit, window, amount=amount)

        monkeypatch.setattr(real, "hit", hit)
        await container.respondent_limits().code_mail(None, "x@example.com")
        await container.respondent_limits().submit(None, "w", "f")
        assert calls == ["code-mail-address", "code-mail-all"]


class TestSubmitSetting:
    async def test_zero_turns_the_submit_limit_off(
        self, client: AsyncClient, workspace, published_form, monkeypatch
    ):
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 0)
        before = await _counter_count()
        for _ in range(4):
            sent = await TestSubmit._post(
                client, workspace, published_form.form_id
            )
            assert sent.status_code != 429, sent.text
        assert await _counter_count() == before  # nothing counted

    async def test_the_budget_is_read_on_every_request(self, monkeypatch):
        limiter = container.respondent_limits()
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 1)
        await limiter.submit("203.0.113.7", "w", "f")
        with pytest.raises(Exception) as refused:
            await limiter.submit("203.0.113.7", "w", "f")
        assert refused.value.status_code == 429
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 3)
        await limiter.submit("203.0.113.7", "w", "f")  # raised live, no restart

    async def test_an_ipv6_device_is_one_client_on_submit(self, monkeypatch):
        limiter = container.respondent_limits()
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 1)
        await limiter.submit("2001:db8:1:2::1", "w", "f")
        with pytest.raises(Exception) as refused:
            await limiter.submit("2001:db8:1:2:ffff::7", "w", "f")
        assert refused.value.status_code == 429
        await limiter.submit("2001:db8:1:3::1", "w", "f")  # another /64


class TestLimiterFailure:
    """A limiter that errors (lock timeout, pool timeout, database down): the
    submit fails open (the request goes on); the sign-in code routes fail
    closed (503, Retry-After 60, no mail), the instance breaker included. Only
    a real 429 is a 429. Nothing personal is logged."""

    @staticmethod
    def _broken(monkeypatch, only_scope=None):
        real = container.rate_limiter().hit

        async def boom(scope, *args, **kwargs):
            if only_scope is None or scope == only_scope:
                raise RuntimeError(
                    "lock timeout on rate_limit_counters for secret.person@example.com"
                )
            return await real(scope, *args, **kwargs)

        monkeypatch.setattr(container.rate_limiter(), "hit", boom)

    @staticmethod
    def _logged():
        lines = []
        sink = logger.add(lambda m: lines.append(str(m)), level="WARNING")
        return lines, sink

    @staticmethod
    def _assert_unavailable(response, lang="en"):
        assert response.status_code == 503, response.text
        assert response.headers["Retry-After"] == "60"
        body = response.json()
        assert body["code"] == "rate_limiter_unavailable" and body["retry_after"] == 60
        if lang == "nl":
            assert body["message"].startswith("Inlogcodes zijn tijdelijk")
        else:
            assert body["message"].startswith("Sign-in codes are temporarily")
        assert "secret" not in response.text and "example.com" not in response.text

    async def test_a_failing_limiter_refuses_the_workspace_code_with_503(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        self._broken(monkeypatch)
        lines, sink = self._logged()
        sent = AsyncMock(return_value=SENT)
        try:
            with patch("common.services.http_client.HttpClient.get", sent):
                refused = await _workspace_code(
                    client, workspace, "secret.person@example.com"
                )
        finally:
            logger.remove(sink)
        self._assert_unavailable(refused)
        assert sent.await_count == 0, "no mail without a counted request"
        text = "".join(lines)
        assert "code request refused" in text and "RuntimeError" in text
        assert "secret" not in text and "example.com" not in text
        assert "203.0.113.7" not in text

    async def test_a_failing_limiter_refuses_the_creator_code_with_503(
        self, client: AsyncClient, monkeypatch
    ):
        self._broken(monkeypatch)
        sent = AsyncMock(return_value=SENT)
        with patch("common.services.http_client.HttpClient.get", sent):
            refused = await _creator_code(client, "x@example.com")
            dutch = await _creator_code(client, "x@example.com", locale="nl")
        self._assert_unavailable(refused)
        self._assert_unavailable(dutch, "nl")
        assert sent.await_count == 0

    async def test_an_error_on_the_breaker_does_not_skip_it(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        """The per-client and per-mailbox counters work, the instance breaker's
        counter fails (a pool timeout on its one row under a flood): no code."""
        self._broken(monkeypatch, only_scope=limits.CODE_ALL_SCOPE)
        sent = AsyncMock(return_value=SENT)
        with patch("common.services.http_client.HttpClient.get", sent):
            workspace_refused = await _workspace_code(client, workspace, "x@example.com")
            creator_refused = await _creator_code(client, "y@example.com")
        self._assert_unavailable(workspace_refused)
        self._assert_unavailable(creator_refused)
        assert sent.await_count == 0

    async def test_a_failing_container_refuses_the_code_with_503(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        def broken():
            raise RuntimeError("no limiter")

        monkeypatch.setattr(container, "respondent_limits", broken)
        sent = AsyncMock(return_value=SENT)
        with patch("common.services.http_client.HttpClient.get", sent):
            refused = await _creator_code(client, "x@example.com")
        self._assert_unavailable(refused)
        assert sent.await_count == 0

    async def test_a_failing_limiter_lets_the_submit_through(
        self, client: AsyncClient, workspace, published_form, monkeypatch
    ):
        self._broken(monkeypatch)
        lines, sink = self._logged()
        try:
            sent = await TestSubmit._post(client, workspace, published_form.form_id)
        finally:
            logger.remove(sink)
        assert sent.status_code != 429 and sent.status_code < 500, sent.text
        assert "request let through" in "".join(lines)

    async def test_a_failing_container_lets_the_submit_through(
        self, client: AsyncClient, workspace, published_form, monkeypatch
    ):
        def broken():
            raise RuntimeError("no limiter")

        monkeypatch.setattr(container, "respondent_limits", broken)
        sent = await TestSubmit._post(client, workspace, published_form.form_id)
        assert sent.status_code != 429 and sent.status_code < 500, sent.text

    async def test_a_real_429_is_still_a_429(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        _set(monkeypatch, "CODE_PER_ADDRESS", 1)
        with _mailing():
            await _workspace_code(client, workspace, "x@example.com")
            refused = await _workspace_code(client, workspace, "x@example.com")
        _assert_rate_limited(refused)

    async def test_the_guards_pass_a_refusal_and_handle_the_rest(self):
        from backend.app.services.rate_limiter import Verdict

        async def refuse():
            raise limits.too_many(Verdict(False, 4, 30))

        async def fail():
            raise ValueError("x")

        for guard in (limits.fail_open, limits.fail_closed):
            with pytest.raises(Exception) as refused:
                await guard(refuse)
            assert refused.value.status_code == 429
        await limits.fail_open(fail)
        with pytest.raises(Exception) as unavailable:
            await limits.fail_closed(fail)
        assert unavailable.value.status_code == 503
        assert unavailable.value.headers == {"Retry-After": "60"}
