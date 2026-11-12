"""Rate limits of the sign-in code mail (workspace and creator routes) and of
the respondent submit route (services/respondent_limits.py): per address, per
client, per workspace and for the instance; per client and form, and per form.
A refusal is 429 ``rate_limited`` with ``Retry-After`` and never depends on
whether the address has an account."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.services import respondent_limits as limits
from backend.app.services.respondent_limits import address_limit_key
from backend.config import settings
from common.exceptions.http import HTTPException as CommonHTTPException

SENT = {"message": "Email set to be sent"}
ALICE = {"X-Forwarded-For": "203.0.113.7"}
BOB = {"X-Forwarded-For": "198.51.100.23"}


@pytest.fixture(autouse=True)
def behind_a_proxy(monkeypatch):
    """The test client connects from 127.0.0.1: treat it as the reverse proxy
    whose X-Forwarded-For is believed (the default trusts nobody)."""
    monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "127.0.0.1")


def _set(monkeypatch, name, limit, window=3600):
    scope = getattr(limits, name)[0]
    monkeypatch.setattr(limits, name, (scope, limit, window))


def _mail(n: int, domain="example.com") -> str:
    return f"person{n}@{domain}"


async def _workspace_code(client, workspace, address, headers=None, **params):
    return await client.post(
        f"/api/v1/workspaces/{workspace.id}/auth/otp/send",
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


class TestAddressKey:
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

    def test_an_internationalised_domain_and_its_punycode_agree(self):
        assert address_limit_key("a@bücher.example") == address_limit_key(
            "a@xn--bcher-kva.example"
        )

    def test_another_mailbox_is_another_key(self):
        assert address_limit_key("a@example.com") != address_limit_key("b@example.com")
        assert address_limit_key("a@example.com") != address_limit_key("a@example.org")

    def test_a_bare_plus_local_part_is_kept(self):
        assert address_limit_key("+@example.com") == "+@example.com"


class TestCodePerAddress:
    async def test_the_fourth_request_in_the_hour_is_refused(
        self, client: AsyncClient, workspace
    ):
        sent = AsyncMock(return_value=SENT)
        with patch("common.services.http_client.HttpClient.get", sent):
            for _ in range(3):
                ok = await _workspace_code(client, workspace, "x@example.com")
                assert ok.status_code == 200, ok.text
            refused = await _workspace_code(client, workspace, "x@example.com")
        _assert_rate_limited(refused)
        # the refused request reached no mail
        assert sent.await_count == 3

    async def test_the_limit_is_three_an_hour(self):
        assert limits.CODE_PER_ADDRESS[1:] == (3, 3600)

    async def test_the_window_ends_and_the_address_may_ask_again(
        self, client: AsyncClient, workspace, rate_limit_clock
    ):
        with patch(
            "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
        ):
            for _ in range(3):
                await _workspace_code(client, workspace, "x@example.com")
            refused = await _workspace_code(client, workspace, "x@example.com")
            wait = int(refused.headers["Retry-After"])
            assert 1 <= wait <= 3600
            rate_limit_clock["now"] += wait + 1
            again = await _workspace_code(client, workspace, "x@example.com")
        assert again.status_code == 200, again.text

    async def test_another_address_is_not_affected(
        self, client: AsyncClient, workspace
    ):
        with patch(
            "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
        ):
            for _ in range(4):
                await _workspace_code(client, workspace, "x@example.com")
            other = await _workspace_code(client, workspace, "y@example.com")
        assert other.status_code == 200, other.text

    async def test_spelling_variants_are_one_address(
        self, client: AsyncClient, workspace
    ):
        with patch(
            "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
        ):
            for spelling in ("x@example.com", "X@Example.com", "x+1@example.com"):
                ok = await _workspace_code(client, workspace, spelling)
                assert ok.status_code == 200, ok.text
            refused = await _workspace_code(client, workspace, "x+2@EXAMPLE.com")
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


class TestCodePerClient:
    async def test_the_eleventh_request_of_a_client_is_refused(
        self, client: AsyncClient, workspace
    ):
        assert limits.CODE_PER_CLIENT[1:] == (10, 3600)
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

    async def test_the_creator_route_counts_the_same_client(
        self, client: AsyncClient, workspace
    ):
        with patch(
            "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
        ):
            for n in range(5):
                await _workspace_code(client, workspace, _mail(n))
            for n in range(5, 10):
                ok = await _creator_code(client, _mail(n))
                assert ok.status_code == 200, ok.text
            refused = await _creator_code(client, _mail(11))
        _assert_rate_limited(refused)

    async def test_an_ipv6_client_is_counted_by_its_64(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        _set(monkeypatch, "CODE_PER_CLIENT", 2)
        with patch(
            "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
        ):
            for n, host in enumerate(("2001:db8:1:2::1", "2001:db8:1:2::2")):
                ok = await _workspace_code(
                    client, workspace, _mail(n), headers={"X-Forwarded-For": host}
                )
                assert ok.status_code == 200, ok.text
            refused = await _workspace_code(
                client,
                workspace,
                _mail(3),
                headers={"X-Forwarded-For": "2001:db8:1:2:ffff::9"},
            )
        _assert_rate_limited(refused)

    async def test_an_unknown_client_is_not_limited_per_client(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        """No address to tell clients apart: one shared bucket would lock
        everyone out together, so only the address, workspace and instance
        limits hold."""
        monkeypatch.setattr(
            "backend.app.controllers.workspace_router.request_client_ip",
            lambda request: None,
        )
        sent = AsyncMock(return_value=SENT)
        with patch("common.services.http_client.HttpClient.get", sent):
            for n in range(15):
                ok = await _workspace_code(client, workspace, _mail(n))
                assert ok.status_code == 200, ok.text
            # the address limit still holds
            for _ in range(3):
                await _workspace_code(client, workspace, "x@example.com")
            refused = await _workspace_code(client, workspace, "x@example.com")
        _assert_rate_limited(refused)

    async def test_an_unknown_client_still_meets_the_workspace_budget(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        monkeypatch.setattr(
            "backend.app.controllers.workspace_router.request_client_ip",
            lambda request: None,
        )
        _set(monkeypatch, "CODE_PER_WORKSPACE", 4)
        with patch(
            "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
        ):
            for n in range(4):
                ok = await _workspace_code(client, workspace, _mail(n))
                assert ok.status_code == 200, ok.text
            refused = await _workspace_code(client, workspace, _mail(9))
        _assert_rate_limited(refused)


class TestCodePerWorkspaceAndInstance:
    async def test_the_numbers(self):
        assert limits.CODE_PER_WORKSPACE[1:] == (1000, 3600)
        assert limits.CODE_ALL[1:] == (5000, 3600)
        assert limits.CODE_CREATOR[1:] == (1000, 3600)

    async def test_a_workspace_budget_is_its_own(
        self, client: AsyncClient, workspace, workspace_1, monkeypatch
    ):
        _set(monkeypatch, "CODE_PER_WORKSPACE", 3)
        with patch(
            "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
        ):
            for n in range(3):
                ok = await _workspace_code(
                    client,
                    workspace,
                    _mail(n),
                    headers={"X-Forwarded-For": f"203.0.113.{n + 1}"},
                )
                assert ok.status_code == 200, ok.text
            refused = await _workspace_code(
                client, workspace, _mail(9), headers={"X-Forwarded-For": "203.0.113.50"}
            )
            elsewhere = await _workspace_code(
                client,
                workspace_1,
                _mail(10),
                headers={"X-Forwarded-For": "203.0.113.51"},
            )
        _assert_rate_limited(refused)
        assert elsewhere.status_code == 200, elsewhere.text

    async def test_the_creator_sign_in_has_a_budget_of_its_own(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        _set(monkeypatch, "CODE_CREATOR", 2)
        with patch(
            "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
        ):
            for n in range(2):
                ok = await _creator_code(
                    client, _mail(n), headers={"X-Forwarded-For": f"203.0.113.{n + 1}"}
                )
                assert ok.status_code == 200, ok.text
            refused = await _creator_code(
                client, _mail(9), headers={"X-Forwarded-For": "203.0.113.50"}
            )
            respondent = await _workspace_code(
                client, workspace, _mail(10), headers={"X-Forwarded-For": "203.0.113.51"}
            )
        _assert_rate_limited(refused)
        assert respondent.status_code == 200, respondent.text

    async def test_the_instance_budget_covers_every_route(
        self, client: AsyncClient, workspace, workspace_1, monkeypatch
    ):
        _set(monkeypatch, "CODE_ALL", 3)
        with patch(
            "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
        ):
            for n, route in enumerate(("w", "w1", "c")):
                headers = {"X-Forwarded-For": f"203.0.113.{n + 1}"}
                if route == "c":
                    ok = await _creator_code(client, _mail(n), headers=headers)
                else:
                    ok = await _workspace_code(
                        client,
                        workspace if route == "w" else workspace_1,
                        _mail(n),
                        headers=headers,
                    )
                assert ok.status_code == 200, ok.text
            refused = await _workspace_code(
                client, workspace, _mail(9), headers={"X-Forwarded-For": "203.0.113.60"}
            )
        _assert_rate_limited(refused)


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

    async def test_refusals_are_counted_on_for_the_same_address(
        self, client: AsyncClient, workspace
    ):
        """A refused request keeps the address refused (it still counts)."""
        with patch(
            "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
        ):
            for _ in range(3):
                await _workspace_code(client, workspace, "x@example.com")
            for _ in range(5):
                refused = await _workspace_code(client, workspace, "x@example.com")
                assert refused.status_code == 429


class TestRefusalWording:
    async def test_english_by_default_dutch_when_asked(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        _set(monkeypatch, "CODE_PER_ADDRESS", 0)
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
        _set(monkeypatch, "CODE_PER_ADDRESS", 0)
        refused = await _workspace_code(client, workspace, "private.person@example.com")
        assert "private" not in refused.text
        assert "example.com" not in refused.text

    async def test_the_wait_is_in_minutes_or_hours(self):
        from backend.app.services.rate_limiter import Verdict

        def message(seconds, locale=None):
            return limits.too_many(
                Verdict(False, 4, seconds), locale
            ).content["message"]

        assert "a minute" in message(30)
        assert "10 minutes" in message(600)
        assert "3 hours" in message(3 * 3600)
        assert "10 minuten" in message(600, "nl")
        assert "een minuut" in message(30, "nl")


class TestSubmit:
    """``POST /workspaces/{w}/forms/{f}/response``."""

    @staticmethod
    async def _post(client, workspace, form_id, headers=None):
        return await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/response",
            data={"response": json.dumps({"answers": {}})},
            headers=headers or ALICE,
        )

    async def test_the_numbers(self):
        assert limits.SUBMIT_PER_CLIENT_FORM[1:] == (120, 60)
        assert limits.SUBMIT_PER_FORM[1:] == (1000, 60)

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

    async def test_the_form_budget_covers_all_its_clients(
        self, client: AsyncClient, workspace, published_form, monkeypatch
    ):
        _set(monkeypatch, "SUBMIT_PER_FORM", 3, 60)
        for n in range(3):
            sent = await self._post(
                client,
                workspace,
                published_form.form_id,
                {"X-Forwarded-For": f"203.0.113.{n + 1}"},
            )
            assert sent.status_code != 429, sent.text
        refused = await self._post(
            client, workspace, published_form.form_id, {"X-Forwarded-For": "203.0.113.99"}
        )
        _assert_rate_limited(refused)

    async def test_forms_do_not_share_budgets(
        self, client: AsyncClient, workspace, published_form, monkeypatch
    ):
        """One form's flood leaves another form of the same workspace, and the
        same client on it, untouched."""
        _set(monkeypatch, "SUBMIT_PER_FORM", 2, 60)
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

    async def test_an_unknown_client_meets_only_the_form_budget(
        self, client: AsyncClient, workspace, published_form, monkeypatch
    ):
        monkeypatch.setattr(
            "backend.app.controllers.workspace_forms.request_client_ip",
            lambda request: None,
        )
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 1, 60)
        _set(monkeypatch, "SUBMIT_PER_FORM", 3, 60)
        for _ in range(3):
            sent = await self._post(client, workspace, published_form.form_id)
            assert sent.status_code != 429, sent.text
        _assert_rate_limited(
            await self._post(client, workspace, published_form.form_id)
        )

    async def test_a_busy_form_with_many_clients_is_not_throttled(
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
        for _ in range(20):
            sent = await self._post(
                client, workspace, published_form.form_id, {"X-Forwarded-For": "192.0.2.5"}
            )
            assert sent.status_code != 429, sent.text

    async def test_a_refused_submit_stores_nothing(
        self, client: AsyncClient, workspace, published_form, monkeypatch
    ):
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 0, 60)
        service = container.workspace_form_service()
        with patch.object(service, "submit_response", AsyncMock()) as submit:
            refused = await self._post(client, workspace, published_form.form_id)
        _assert_rate_limited(refused)
        submit.assert_not_awaited()


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
        respondent route's budgets used up, a key still submits, and the
        respondent counters do not move."""
        from tests.app.controllers.test_submissions_api import (
            _body,
            _form,
            _key,
            _submit,
        )
        monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        _set(monkeypatch, "SUBMIT_PER_CLIENT_FORM", 0, 60)
        _set(monkeypatch, "SUBMIT_PER_FORM", 0, 60)
        spy = AsyncMock()
        with patch.object(
            type(container.respondent_limits()), "submit", spy
        ), patch.object(type(container.respondent_limits()), "code_mail", spy):
            response = await _submit(client, token, form_id, _body({}))
        # the API's own answer (validation or created), never the 429 of the
        # respondent route, and the respondent limiter was not asked
        assert response.status_code != 429, response.text
        spy.assert_not_awaited()


class TestUnits:
    async def test_no_address_or_client_is_stored_in_a_counter(
        self, client: AsyncClient, workspace
    ):
        from sqlalchemy import select

        from backend.db.models import RateLimitCounterRow

        with patch(
            "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
        ):
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
        _set(monkeypatch, "CODE_PER_ADDRESS", 0)
        with pytest.raises(Exception) as refused:
            await container.respondent_limits().code_mail(
                "203.0.113.7", "x@example.com", workspace_id="w"
            )
        assert refused.value.status_code == 429
        assert calls == ["code-mail-client", "code-mail-address"]

    async def test_none_client_skips_the_client_limit(self, monkeypatch):
        calls = []
        real = container.rate_limiter()
        real_hit = real.hit

        async def hit(scope, client, limit, window, amount=1):
            calls.append(scope)
            return await real_hit(scope, client, limit, window, amount=amount)

        monkeypatch.setattr(real, "hit", hit)
        await container.respondent_limits().code_mail(None, "x@example.com")
        await container.respondent_limits().submit(None, "w", "f")
        assert calls == [
            "code-mail-address",
            "code-mail-creator",
            "code-mail-all",
            "submit-form",
        ]
