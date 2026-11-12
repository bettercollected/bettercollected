"""The challenge route and the enforcement on the respondent submit, switch on."""

import datetime as dt

import pytest
from sqlalchemy import select

from backend.app.container import container
from backend.app.services.captcha import challenge as ch
from backend.app.services.captcha.service import CHALLENGES_PER_MINUTE
from backend.config import settings
from backend.db.models import RateLimitCounterRow
from tests.app.captcha.conftest import (
    ALICE,
    BOB,
    ask,
    a_form,
    signed_in,
    solved,
    submit,
)

pytestmark = pytest.mark.usefixtures("on")


async def test_the_route_issues_a_bound_uncached_challenge(client, workspace):
    form = await a_form(workspace)
    answer = await ask(client, workspace, form)
    assert answer.status_code == 200, answer.text
    assert answer.headers["cache-control"] == "no-store"
    assert "set-cookie" not in answer.headers
    body = answer.json()
    assert body["algorithm"] == "sha256-lz" and body["subpuzzles"] == 8
    assert body["bits"] == 14  # the test's base
    claims = ch.unverified_claims(body["challenge"])
    assert claims["w"] == str(workspace.id) and claims["f"] == str(form.form_id)
    assert claims["p"] == "submit" and claims["t"]
    assert body["expiresAt"] == claims["e"]
    expires = dt.datetime.fromtimestamp(claims["e"] / 1000, dt.timezone.utc)
    assert (
        dt.timedelta(minutes=14) < expires - dt.datetime.now(dt.timezone.utc) <= ch.TTL
    )


async def test_the_route_answers_for_an_unknown_form_and_a_bad_purpose(
    client, workspace
):
    form = await a_form(workspace)
    missing = await client.post(
        f"/api/v1/workspaces/{workspace.id}/captcha/challenge",
        json={"purpose": "submit", "formId": "64a1b2c3d4e5f60718293a4c"},
        headers=ALICE,
    )
    assert missing.status_code == 404 and missing.json()["code"] == "form_not_found"
    for body in (
        {"purpose": "mail", "formId": str(form.form_id)},
        {"purpose": "submit"},
    ):
        refused = await client.post(
            f"/api/v1/workspaces/{workspace.id}/captcha/challenge",
            json=body,
            headers=ALICE,
        )
        assert refused.status_code == 422


async def test_a_private_form_gets_no_challenge(client, workspace):
    form = await a_form(workspace)
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form.form_id
    )
    link.settings.private = True
    await container.workspace_form_repo().update(link.id, link)
    refused = await ask(client, workspace, form)
    assert refused.status_code == 404 and refused.json()["code"] == "form_not_found"


async def test_a_solved_proof_submits_once_and_a_replay_is_refused(
    client, workspace, claims
):
    form = await a_form(workspace)
    proof = await solved(client, workspace, form)
    first = await submit(client, workspace, form, proof)
    assert first.status_code == 200, first.text
    assert claims == ["captcha-nonce"]
    again = await submit(client, workspace, form, proof)
    assert again.status_code == 422 and again.json()["code"] == "captcha_replayed"
    # the replay stored nothing
    assert (
        await container.form_response_service().get_responses_count_in_workspace(
            workspace.id, [str(form.form_id)]
        )
        == 1
    )


async def test_a_missing_proof_is_refused_without_touching_the_database(
    client, workspace, claims
):
    form = await a_form(workspace)
    refused = await submit(client, workspace, form)
    assert refused.status_code == 422 and refused.json()["code"] == "captcha_missing"
    assert claims == []


async def test_a_tampered_or_wrong_form_proof_is_refused_before_any_write(
    client, workspace, claims
):
    form, other = await a_form(workspace), await a_form(workspace)
    proof = await solved(client, workspace, form)
    payload, signature, counters = proof.split(".")
    tampered = f"{payload}.{'A' + signature[1:] if signature[0] != 'A' else 'B' + signature[1:]}.{counters}"
    for header, code in ((tampered, "captcha_invalid"), (proof, "captcha_invalid")):
        target = other if header is proof else form
        refused = await submit(client, workspace, target, header)
        assert refused.status_code == 422 and refused.json()["code"] == code
    assert claims == []
    # the proof for the right form still works: refusals spent nothing
    assert (await submit(client, workspace, form, proof)).status_code == 200


async def test_an_expired_proof_is_refused(client, workspace, monkeypatch, claims):
    form = await a_form(workspace)
    proof = await solved(client, workspace, form)
    later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=17)
    monkeypatch.setattr(ch, "_now", lambda now: later)
    refused = await submit(client, workspace, form, proof)
    assert refused.status_code == 422 and refused.json()["code"] == "captcha_expired"
    assert claims == []


async def test_a_proof_from_another_network_is_refused(client, workspace):
    form = await a_form(workspace)
    proof = await solved(client, workspace, form, headers=ALICE)
    refused = await submit(client, workspace, form, proof, headers=BOB)
    assert refused.status_code == 422 and refused.json()["code"] == "captcha_invalid"


async def test_failures_raise_the_difficulty_of_that_client_only(
    client, workspace, monkeypatch
):
    form = await a_form(workspace)
    for _ in range(3):
        await submit(client, workspace, form, "x.y.z")
    assert (await ask(client, workspace, form, ALICE)).json()["bits"] == 16
    assert (await ask(client, workspace, form, BOB)).json()["bits"] == 14


async def test_a_signed_in_respondent_gets_three_bits_less_with_a_floor(
    client, workspace, monkeypatch
):
    form = await a_form(workspace)
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_SUBMIT", 18)
    anonymous = await ask(client, workspace, form)
    member = await ask(client, workspace, form, BOB, signed_in())
    assert (anonymous.json()["bits"], member.json()["bits"]) == (18, 15)
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_SUBMIT", 14)
    low = await ask(
        client, workspace, form, {"X-Forwarded-For": "192.0.2.9"}, signed_in()
    )
    assert low.json()["bits"] == 14


async def test_the_creator_can_turn_it_off_for_a_form(
    client, workspace, test_user_cookies
):
    form = await a_form(workspace)
    url = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/settings"
    patched = await client.patch(
        url, json={"captchaEnabled": False}, cookies=test_user_cookies
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["settings"]["captchaEnabled"] is False
    assert (
        await submit(client, workspace, form)
    ).status_code == 200  # no header needed
    back = await client.patch(
        url, json={"captchaEnabled": True}, cookies=test_user_cookies
    )
    assert back.status_code == 200
    assert (await submit(client, workspace, form)).status_code == 422


async def test_respondents_are_told_whether_it_is_required_never_the_setting(
    client, workspace, test_user_cookies
):
    form = await a_form(workspace)
    read = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}?published=true"
    served = (await client.get(read)).json()["settings"]
    assert served["captchaRequired"] is True and not served.get("captchaEnabled")
    await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/settings",
        json={"captchaEnabled": False},
        cookies=test_user_cookies,
    )
    served = (await client.get(read)).json()["settings"]
    assert served["captchaRequired"] is False and not served.get("captchaEnabled")
    # what is stored is the creator's setting, no computed field
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form.form_id
    )
    assert link.settings.captcha_enabled is False


async def test_a_member_reading_the_published_form_is_told_too(
    client, workspace, test_user_cookies, monkeypatch
):
    """A member of the workspace answering their own form passes the same
    route as anyone, so the page must know to send the proof."""
    from backend.app.services.form_service import FormService

    async def nobody(self, user_ids):
        return []

    monkeypatch.setattr(FormService, "fetch_user_details", nobody)
    form = await a_form(workspace)
    read = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}?published=true"
    served = (await client.get(read, cookies=test_user_cookies)).json()["settings"]
    assert served["captchaRequired"] is True
    await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/settings",
        json={"captchaEnabled": False},
        cookies=test_user_cookies,
    )
    served = (await client.get(read, cookies=test_user_cookies)).json()["settings"]
    assert served["captchaRequired"] is False


async def test_the_permissions_answer_says_the_switch_is_on(
    client, workspace, test_user_cookies
):
    answer = await client.get(
        f"/api/v1/workspaces/{workspace.id}/permissions", cookies=test_user_cookies
    )
    assert answer.json()["captchaEnabled"] is True


async def test_the_challenge_route_is_limited_per_client(client, workspace):
    form = await a_form(workspace)
    for _ in range(CHALLENGES_PER_MINUTE):
        assert (await ask(client, workspace, form)).status_code == 200
    limited = await ask(client, workspace, form)
    assert limited.status_code == 429 and limited.json()["code"] == "rate_limited"
    assert int(limited.headers["Retry-After"]) >= 1
    assert (await ask(client, workspace, form, BOB)).status_code == 200


async def test_the_submissions_api_with_a_key_needs_no_proof(
    client, workspace, monkeypatch, claims
):
    from tests.app.controllers.test_submissions_api import _body, _form, _key, _submit

    monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)
    form_id = await _form(client, workspace)
    token = await _key(workspace)
    response = await _submit(client, token, form_id, _body({}))
    # the API's own answer, never the proof's; and nothing was claimed
    assert "captcha" not in response.text.lower(), response.text
    assert claims == []


# ------------------------------------------------------- an unknown client


class TestUntrustedProxy:
    """A proxy on a private address that is not in TRUSTED_PROXIES makes every
    user one client: like the other per-client limits, nothing is bound or
    counted for it."""

    @pytest.fixture(autouse=True)
    def no_trusted_proxy(self, monkeypatch):
        monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "")

    async def test_the_challenge_is_unbound_and_nothing_is_counted(
        self, client, workspace
    ):
        form = await a_form(workspace)
        answer = await ask(client, workspace, form, ALICE)
        assert ch.unverified_claims(answer.json()["challenge"])["t"] == ""
        for _ in range(CHALLENGES_PER_MINUTE + 5):
            assert (await ask(client, workspace, form, ALICE)).status_code == 200
        pressure = container.captcha_service().pressure
        assert not pressure._issued._keys and not pressure._asked._keys
        # many challenges, still the base difficulty
        assert (await ask(client, workspace, form, ALICE)).json()["bits"] == 14

    async def test_a_proof_works_from_another_forwarded_address(
        self, client, workspace
    ):
        form = await a_form(workspace)
        proof = await solved(client, workspace, form, ALICE)
        assert (await submit(client, workspace, form, proof, BOB)).status_code == 200

    async def test_failures_are_not_counted_for_it(self, client, workspace):
        form = await a_form(workspace)
        for _ in range(4):
            await submit(client, workspace, form, "x.y.z")
        assert not container.captcha_service().pressure._failed._keys
        assert (await ask(client, workspace, form)).json()["bits"] == 14


async def test_a_spent_nonce_is_stored_hashed(client, workspace):
    form = await a_form(workspace)
    proof = await solved(client, workspace, form)
    nonce = ch.unverified_claims(proof.rsplit(".", 1)[0])["n"]
    before = {r.id for r in (await _rows())}
    await submit(client, workspace, form, proof)
    after = await _rows()
    assert len(after) > len(before)
    assert nonce not in str([tuple(map(str, r)) for r in after])


async def _rows():
    async with container.pg_engine().connect() as conn:
        return (await conn.execute(select(RateLimitCounterRow))).all()
