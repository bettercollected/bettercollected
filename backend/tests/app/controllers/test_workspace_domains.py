"""Verified email domains: claim, verify (DNS mocked), remove; who may; one
verified owner per domain; re-checks; the helpers single sign-on will use."""

import datetime as dt

import dns.resolver
import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.config import settings
from tests.app.controllers.data import testUser1

RECORD = "_bettercollected-verification.acme.com"


def _url(workspace, *rest) -> str:
    return "/".join([f"/api/v1/workspaces/{workspace.id}/domains", *rest])


async def _claim(client, workspace, cookies, domain="acme.com"):
    response = await client.post(
        _url(workspace), cookies=cookies, json={"domain": domain}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _verify(client, workspace, cookies, domain_id):
    return await client.post(_url(workspace, domain_id, "verify"), cookies=cookies)


async def _make_admin(workspace, user):
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=user.id, roles=[WorkspaceRoles.ADMIN]
        )
    )


async def _age_last_check(domain_id, hours=48):
    repo = container.workspace_domain_repo()
    document = await repo.get(domain_id)
    document.last_checked_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
        hours=hours
    )
    await repo.save(document)


class TestClaim:
    async def test_owner_claims_and_sees_the_record_to_publish(
        self, client: AsyncClient, workspace, test_user_cookies
    ):
        body = await _claim(client, workspace, test_user_cookies, "  ACME.com. ")

        assert body["domain"] == "acme.com"
        assert body["status"] == "pending"
        assert body["txtRecordName"] == RECORD
        token = body["txtRecordValue"].removeprefix(
            "bettercollected-domain-verification="
        )
        assert len(token) == 32 and token != body["txtRecordValue"]
        assert body["verifiedAt"] is None

        listed = await client.get(_url(workspace), cookies=test_user_cookies)
        assert listed.status_code == 200
        assert [d["domain"] for d in listed.json()] == ["acme.com"]

    async def test_each_claim_gets_its_own_token(
        self,
        client: AsyncClient,
        workspace,
        workspace_1,
        test_user_cookies,
        test_user_cookies_1,
    ):
        mine = await _claim(client, workspace, test_user_cookies)
        theirs = await _claim(client, workspace_1, test_user_cookies_1)
        assert mine["txtRecordName"] == theirs["txtRecordName"]
        assert mine["txtRecordValue"] != theirs["txtRecordValue"]

    async def test_idn_is_stored_as_punycode(
        self, client: AsyncClient, workspace, test_user_cookies
    ):
        body = await _claim(client, workspace, test_user_cookies, "Bücher.de")
        assert body["domain"] == "xn--bcher-kva.de"
        assert body["displayDomain"] == "bücher.de"
        assert body["txtRecordName"] == "_bettercollected-verification.xn--bcher-kva.de"

    @pytest.mark.parametrize(
        "domain, code",
        [
            ("gmail.com", "free_mail_domain"),
            ("yahoo.co.uk", "free_mail_domain"),
            ("co.uk", "public_suffix"),
            ("github.io", "public_suffix"),
            ("*.acme.com", "invalid_domain"),
            ("jane@acme.com", "invalid_domain"),
            ("acme.internal", "unknown_suffix"),
        ],
    )
    async def test_unclaimable_domains_are_refused(
        self, client: AsyncClient, workspace, test_user_cookies, domain, code
    ):
        response = await client.post(
            _url(workspace), cookies=test_user_cookies, json={"domain": domain}
        )
        assert response.status_code == 422
        assert response.json()["code"] == code
        assert (
            await client.get(_url(workspace), cookies=test_user_cookies)
        ).json() == []

    async def test_reserved_domains_are_refused(
        self, client: AsyncClient, workspace, test_user_cookies, monkeypatch
    ):
        monkeypatch.setattr(
            settings.verified_domains, "PLATFORM_ADMIN_EMAILS", "root@operator.io"
        )
        response = await client.post(
            _url(workspace), cookies=test_user_cookies, json={"domain": "operator.io"}
        )
        assert response.status_code == 422
        assert response.json()["code"] == "reserved_domain"

    async def test_claiming_twice_is_a_conflict(
        self, client: AsyncClient, workspace, test_user_cookies
    ):
        await _claim(client, workspace, test_user_cookies)
        again = await client.post(
            _url(workspace), cookies=test_user_cookies, json={"domain": "ACME.COM"}
        )
        assert again.status_code == 409
        assert again.json()["code"] == "already_claimed"

    async def test_claims_per_workspace_are_limited(
        self, client: AsyncClient, workspace, test_user_cookies, monkeypatch
    ):
        monkeypatch.setattr(settings.verified_domains, "MAX_PER_WORKSPACE", 1)
        await _claim(client, workspace, test_user_cookies)
        response = await client.post(
            _url(workspace), cookies=test_user_cookies, json={"domain": "beta.com"}
        )
        assert response.status_code == 422
        assert response.json()["code"] == "too_many_domains"


class TestPermissions:
    async def test_an_admin_manages_domains(
        self,
        client: AsyncClient,
        workspace,
        test_user_cookies_1,
        fake_dns,
    ):
        await _make_admin(workspace, testUser1)
        body = await _claim(client, workspace, test_user_cookies_1)
        fake_dns.set_txt(RECORD, body["txtRecordValue"])

        verified = await _verify(client, workspace, test_user_cookies_1, body["id"])
        assert verified.status_code == 200
        assert verified.json()["status"] == "verified"
        listed = await client.get(_url(workspace), cookies=test_user_cookies_1)
        assert listed.status_code == 200 and len(listed.json()) == 1
        removed = await client.delete(
            _url(workspace, body["id"]), cookies=test_user_cookies_1
        )
        assert removed.status_code == 204

    @pytest.mark.parametrize("who", ["collaborator", "outsider", "anonymous"])
    async def test_others_cannot_see_or_change_domains(
        self,
        client: AsyncClient,
        workspace,
        test_user_cookies,
        test_invited_user_cookies,
        test_user_cookies_1,
        fake_dns,
        who,
    ):
        body = await _claim(client, workspace, test_user_cookies)
        fake_dns.set_txt(RECORD, body["txtRecordValue"])
        cookies, expected = {
            # invited_user is a COLLABORATOR of the workspace fixture
            "collaborator": (test_invited_user_cookies, 403),
            "outsider": (test_user_cookies_1, 403),
            "anonymous": ({}, 401),
        }[who]

        calls = [
            client.get(_url(workspace), cookies=cookies),
            client.post(_url(workspace), cookies=cookies, json={"domain": "beta.com"}),
            _verify(client, workspace, cookies, body["id"]),
            client.delete(_url(workspace, body["id"]), cookies=cookies),
        ]
        for call in calls:
            assert (await call).status_code == expected

        # nothing changed
        listed = (await client.get(_url(workspace), cookies=test_user_cookies)).json()
        assert [(d["domain"], d["status"]) for d in listed] == [("acme.com", "pending")]

    async def test_a_domain_of_another_workspace_is_not_found(
        self,
        client: AsyncClient,
        workspace,
        workspace_1,
        test_user_cookies,
        test_user_cookies_1,
    ):
        theirs = await _claim(client, workspace_1, test_user_cookies_1)
        for response in [
            await _verify(client, workspace, test_user_cookies, theirs["id"]),
            await client.delete(
                _url(workspace, theirs["id"]), cookies=test_user_cookies
            ),
            await _verify(client, workspace, test_user_cookies, "not-an-id"),
        ]:
            assert response.status_code == 404
        listed = (
            await client.get(_url(workspace_1), cookies=test_user_cookies_1)
        ).json()
        assert len(listed) == 1


class TestVerify:
    async def test_matching_record_verifies(
        self, client: AsyncClient, workspace, test_user_cookies, fake_dns
    ):
        body = await _claim(client, workspace, test_user_cookies)
        fake_dns.set_txt(RECORD, "v=spf1 -all", body["txtRecordValue"])

        response = await _verify(client, workspace, test_user_cookies, body["id"])

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "verified"
        assert result["verifiedAt"] and result["lastCheckedAt"]
        assert result["lastCheckError"] is None
        service = container.workspace_domain_service()
        assert await service.domain_owner("acme.com") == workspace.id

    @pytest.mark.parametrize(
        "record, error",
        [
            ("bettercollected-domain-verification=wrong", "token_mismatch"),
            (None, "no_record"),
            (dns.resolver.LifetimeTimeout(timeout=5, errors={}), "dns_timeout"),
            (dns.resolver.NoNameservers(), "dns_error"),
        ],
    )
    async def test_failed_checks_leave_it_unverified(
        self,
        client: AsyncClient,
        workspace,
        test_user_cookies,
        fake_dns,
        record,
        error,
    ):
        body = await _claim(client, workspace, test_user_cookies)
        if isinstance(record, str):
            fake_dns.set_txt(RECORD, record)
        elif record is not None:
            fake_dns.fail(RECORD, record)

        response = await _verify(client, workspace, test_user_cookies, body["id"])

        assert response.status_code == 200
        assert response.json()["status"] == "failed"
        assert response.json()["lastCheckError"] == error
        assert response.json()["verifiedAt"] is None
        assert (
            await container.workspace_domain_service().domain_owner("acme.com") is None
        )

        # fixing the record and checking again verifies it
        fake_dns.set_txt(RECORD, body["txtRecordValue"])
        again = await _verify(client, workspace, test_user_cookies, body["id"])
        assert again.json()["status"] == "verified"
        assert again.json()["lastCheckError"] is None


class TestOneOwnerPerDomain:
    async def test_first_to_verify_wins(
        self,
        client: AsyncClient,
        workspace,
        workspace_1,
        workspace_pro,
        test_user_cookies,
        test_user_cookies_1,
        test_pro_user_cookies,
        fake_dns,
    ):
        mine = await _claim(client, workspace, test_user_cookies)
        theirs = await _claim(client, workspace_1, test_user_cookies_1)
        # both workspaces publish their own record on the same name
        fake_dns.set_txt(RECORD, mine["txtRecordValue"], theirs["txtRecordValue"])

        assert (
            await _verify(client, workspace_1, test_user_cookies_1, theirs["id"])
        ).json()["status"] == "verified"

        blocked = await _verify(client, workspace, test_user_cookies, mine["id"])
        assert blocked.status_code == 200
        assert blocked.json()["status"] == "conflict"
        assert blocked.json()["lastCheckError"] == "verified_by_another_workspace"
        listed = (await client.get(_url(workspace), cookies=test_user_cookies)).json()
        assert listed[0]["status"] == "conflict"

        # a new claim of a verified domain is refused outright
        refused = await client.post(
            _url(workspace_pro),
            cookies=test_pro_user_cookies,
            json={"domain": "acme.com"},
        )
        assert refused.status_code == 409
        assert refused.json()["code"] == "domain_verified_elsewhere"

        service = container.workspace_domain_service()
        assert await service.domain_owner("acme.com") == workspace_1.id
        assert await service.is_domain_verified_for(workspace_1.id, "jane@acme.com")
        assert not await service.is_domain_verified_for(workspace.id, "jane@acme.com")

        # once the owner removes it, the domain is free again
        removed = await client.delete(
            _url(workspace_1, theirs["id"]), cookies=test_user_cookies_1
        )
        assert removed.status_code == 204
        assert (await client.get(_url(workspace), cookies=test_user_cookies)).json()[0][
            "status"
        ] == "failed"
        won = await _verify(client, workspace, test_user_cookies, mine["id"])
        assert won.json()["status"] == "verified"
        assert await service.domain_owner("acme.com") == workspace.id

    async def test_concurrent_verification_has_one_winner(
        self,
        client: AsyncClient,
        workspace,
        workspace_1,
        test_user_cookies,
        test_user_cookies_1,
        fake_dns,
    ):
        import asyncio

        mine = await _claim(client, workspace, test_user_cookies)
        theirs = await _claim(client, workspace_1, test_user_cookies_1)
        fake_dns.set_txt(RECORD, mine["txtRecordValue"], theirs["txtRecordValue"])

        results = await asyncio.gather(
            _verify(client, workspace, test_user_cookies, mine["id"]),
            _verify(client, workspace_1, test_user_cookies_1, theirs["id"]),
        )

        statuses = sorted(r.json()["status"] for r in results)
        assert statuses == ["conflict", "verified"]


class TestHelpersAndRechecks:
    async def _verified(self, client, workspace, cookies, fake_dns):
        body = await _claim(client, workspace, cookies)
        fake_dns.set_txt(RECORD, body["txtRecordValue"])
        assert (await _verify(client, workspace, cookies, body["id"])).json()[
            "status"
        ] == "verified"
        return body

    async def test_helpers(
        self,
        client: AsyncClient,
        workspace,
        workspace_1,
        test_user_cookies,
        fake_dns,
    ):
        await self._verified(client, workspace, test_user_cookies, fake_dns)
        service = container.workspace_domain_service()

        assert await service.domain_owner("ACME.com") == workspace.id
        assert await service.domain_owner("Jane.Doe@Acme.COM") == workspace.id
        assert await service.domain_owner("eng.acme.com") is None
        assert await service.domain_owner("not a domain") is None
        assert await service.is_domain_verified_for(workspace.id, "jane@acme.com")
        assert await service.is_domain_verified_for(str(workspace.id), "acme.com")
        assert not await service.is_domain_verified_for(
            workspace.id, "jane@eng.acme.com"
        )
        assert not await service.is_domain_verified_for(workspace_1.id, "jane@acme.com")

    async def test_pending_claims_do_not_count(
        self, client: AsyncClient, workspace, test_user_cookies
    ):
        await _claim(client, workspace, test_user_cookies)
        service = container.workspace_domain_service()
        assert await service.domain_owner("acme.com") is None
        assert not await service.is_domain_verified_for(workspace.id, "jane@acme.com")

    async def test_recheck_marks_loss_after_repeated_failures_and_keeps_owner(
        self,
        client: AsyncClient,
        workspace,
        test_user_cookies,
        fake_dns,
    ):
        body = await self._verified(client, workspace, test_user_cookies, fake_dns)
        service = container.workspace_domain_service()
        assert settings.verified_domains.LOSS_AFTER_FAILED_CHECKS == 3

        # just checked: not due
        assert (await service.recheck_verified_domains())["checked"] == 0

        fake_dns.clear(RECORD)
        for expected_failures in (1, 2):
            await _age_last_check(body["id"])
            counts = await service.recheck_verified_domains()
            assert counts == {"checked": 1, "passed": 0, "failed": 1, "lost": 0}
            listed = (
                await client.get(_url(workspace), cookies=test_user_cookies)
            ).json()
            assert listed[0]["failedChecks"] == expected_failures
            assert listed[0]["verificationLostAt"] is None

        # a resolver outage does not count towards the loss
        fake_dns.fail(RECORD, dns.resolver.LifetimeTimeout(timeout=5, errors={}))
        await _age_last_check(body["id"])
        await service.recheck_verified_domains()
        listed = (await client.get(_url(workspace), cookies=test_user_cookies)).json()
        assert listed[0]["failedChecks"] == 2
        assert listed[0]["lastCheckError"] == "dns_timeout"

        fake_dns.clear(RECORD)
        await _age_last_check(body["id"])
        assert (await service.recheck_verified_domains())["lost"] == 1
        listed = (await client.get(_url(workspace), cookies=test_user_cookies)).json()
        assert listed[0]["status"] == "verified"
        assert listed[0]["verificationLostAt"] is not None
        assert listed[0]["lastCheckError"] == "no_record"
        # it is not transferred or released automatically
        assert await service.domain_owner("acme.com") == workspace.id

        # the record comes back: the next check clears the loss
        fake_dns.set_txt(RECORD, body["txtRecordValue"])
        await _age_last_check(body["id"])
        counts = await service.recheck_verified_domains()
        assert counts == {"checked": 1, "passed": 1, "failed": 0, "lost": 0}
        listed = (await client.get(_url(workspace), cookies=test_user_cookies)).json()
        assert listed[0]["verificationLostAt"] is None
        assert listed[0]["failedChecks"] == 0

    async def test_verify_now_on_a_verified_domain_rechecks_it(
        self,
        client: AsyncClient,
        workspace,
        test_user_cookies,
        fake_dns,
    ):
        body = await self._verified(client, workspace, test_user_cookies, fake_dns)
        fake_dns.set_txt(RECORD, "bettercollected-domain-verification=other")
        result = (
            await _verify(client, workspace, test_user_cookies, body["id"])
        ).json()
        assert result["status"] == "verified"
        assert result["lastCheckError"] == "token_mismatch"
        assert result["failedChecks"] == 1

    async def test_deleted_workspaces_release_their_domains(
        self,
        client: AsyncClient,
        workspace,
        test_user_cookies,
        fake_dns,
    ):
        await self._verified(client, workspace, test_user_cookies, fake_dns)
        service = container.workspace_domain_service()
        assert await service.release_workspace_domains([workspace.id]) == 1
        assert await service.domain_owner("acme.com") is None
