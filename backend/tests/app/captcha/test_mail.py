"""Purpose ``mail`` of the proof of work, switch on: the sign-in code sends
(respondent and creator) and the draft link. The proof is bound to its purpose,
workspace and form, so a proof for a submit is no good for a mail and the other
way round; it is checked before any limit counts."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from backend.app.container import container
from backend.app.services.captcha import challenge as ch
from backend.config import settings
from backend.db.models import RateLimitCounterRow
from tests.app.captcha.conftest import ALICE, BOB, a_form, ask, solved, submit
from tests.app.form_drafts.helpers import body, drafting_form, url

pytestmark = pytest.mark.usefixtures("on")

SENT = {"message": "Email set to be sent"}
ADDRESS = "ada.respondent@example.org"


@pytest.fixture(autouse=True)
def easy_mail(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_MAIL", 14)
    monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", True)


def _mailing():
    return patch(
        "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
    )


@pytest.fixture()
def drafts_mail(monkeypatch):
    sent = []

    async def post(self, url, **kwargs):
        sent.append(url)
        return {"message": "Notice queued."}

    monkeypatch.setattr(type(container.http_client()), "post", post)
    return sent


def workspace_challenge(workspace) -> str:
    return f"/api/v1/workspaces/{workspace.id}/captcha/challenge"


CREATOR_CHALLENGE = "/api/v1/auth/captcha/challenge"


async def workspace_proof(client, workspace, form=None, headers=ALICE) -> str:
    payload = {"purpose": "mail"}
    if form is not None:
        payload["formId"] = str(form.form_id)
    answer = await client.post(
        workspace_challenge(workspace), json=payload, headers=headers
    )
    assert answer.status_code == 200, answer.text
    text = answer.json()["challenge"]
    return ch.proof(text, ch.solve(text))


async def creator_proof(client, headers=ALICE) -> str:
    answer = await client.post(
        CREATOR_CHALLENGE, json={"purpose": "mail"}, headers=headers
    )
    assert answer.status_code == 200, answer.text
    text = answer.json()["challenge"]
    return ch.proof(text, ch.solve(text))


async def workspace_code(client, workspace, address=ADDRESS, proof=None, headers=ALICE):
    sent = dict(headers)
    if proof is not None:
        sent[ch.HEADER] = proof
    return await client.post(
        f"/api/v1/workspaces/{workspace.id}/auth/otp/send",
        params={"receiver_email": address},
        headers=sent,
    )


async def creator_code(client, address=ADDRESS, proof=None, headers=ALICE):
    sent = dict(headers)
    if proof is not None:
        sent[ch.HEADER] = proof
    return await client.post(
        "/api/v1/auth/creator/otp/send",
        params={"receiver_email": address},
        headers=sent,
    )


async def counters() -> int:
    async with container.pg_engine().connect() as conn:
        return len((await conn.execute(select(RateLimitCounterRow))).all())


# -- the challenge


async def test_a_mail_challenge_is_bound_to_its_purpose_workspace_and_no_form(
    client, workspace
):
    answer = await client.post(
        workspace_challenge(workspace), json={"purpose": "mail"}, headers=ALICE
    )
    assert answer.status_code == 200, answer.text
    assert answer.headers["cache-control"] == "no-store"
    body_ = answer.json()
    assert body_["bits"] == 14  # the test's mail base
    claims = ch.unverified_claims(body_["challenge"])
    assert claims["p"] == "mail" and claims["w"] == str(workspace.id)
    assert claims["f"] == "" and claims["t"]
    assert "s" not in claims  # no signed-in discount on a mail


async def test_the_default_mail_base_is_a_bit_above_the_submit_base():
    from backend.config.api_settings import ApiSettings

    assert ApiSettings.model_fields["CAPTCHA_BASE_BITS_MAIL"].default == 18
    service = container.captcha_service()
    from common.settings.inventory import INVENTORY

    spec = {s.key: s for s in INVENTORY}["API_CAPTCHA_BASE_BITS_MAIL"]
    assert (spec.min_value, spec.max_value) == (ch.MIN_BITS, ch.MAX_BITS)
    assert service.difficulty("", "", False, purpose="mail") == 14  # the test's base


async def test_a_mail_challenge_is_harder_than_a_submit_one_by_the_base_only(
    client, workspace, monkeypatch
):
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_MAIL", 16)
    service = container.captcha_service()
    # no signed-in discount on a mail, and the form's submit rate is no part of it
    assert service.difficulty("", "f", True, purpose="mail") == 16
    for _ in range(40):
        service.pressure.submitted("f")
    assert service.difficulty("", "f", False, purpose="mail") == 16
    assert service.difficulty("", "f", False, purpose="submit") == 15


async def test_the_challenge_of_a_missing_workspace_or_a_form_of_another(
    client, workspace
):
    missing = await client.post(
        "/api/v1/workspaces/64a1b2c3d4e5f60718293a4c/captcha/challenge",
        json={"purpose": "mail"},
        headers=ALICE,
    )
    assert missing.status_code == 404
    unknown = await client.post(
        workspace_challenge(workspace),
        json={"purpose": "mail", "formId": "64a1b2c3d4e5f60718293a4c"},
        headers=ALICE,
    )
    assert unknown.status_code == 404 and unknown.json()["code"] == "form_not_found"
    # a submit challenge still names its form
    assert (
        await client.post(
            workspace_challenge(workspace), json={"purpose": "submit"}, headers=ALICE
        )
    ).status_code == 422


async def test_the_creator_challenge_is_for_mail_only_and_bound_to_no_workspace(
    client,
):
    answer = await client.post(CREATOR_CHALLENGE, json={"purpose": "mail"}, headers=ALICE)
    assert answer.status_code == 200, answer.text
    claims = ch.unverified_claims(answer.json()["challenge"])
    assert claims["p"] == "mail" and claims["w"] == "" and claims["f"] == ""
    refused = await client.post(
        CREATOR_CHALLENGE, json={"purpose": "submit"}, headers=ALICE
    )
    assert refused.status_code == 422


# -- the sign-in code sends


async def test_the_workspace_code_needs_a_proof_and_a_missing_one_counts_nothing(
    client, workspace, claims
):
    with _mailing() as mailed:
        refused = await workspace_code(client, workspace)
        assert refused.status_code == 422
        assert refused.json()["code"] == "captcha_missing"
        mailed.assert_not_called()
    # no budget was used up, nothing was claimed
    assert claims == [] and await counters() == 0


async def test_the_workspace_code_with_a_proof_is_sent_once(client, workspace):
    proof = await workspace_proof(client, workspace)
    with _mailing() as mailed:
        sent = await workspace_code(client, workspace, proof=proof)
        assert sent.status_code == 200, sent.text
        assert mailed.await_count == 1
        again = await workspace_code(client, workspace, proof=proof)
        assert again.status_code == 422 and again.json()["code"] == "captcha_replayed"
        assert mailed.await_count == 1


async def test_a_proof_for_another_workspace_a_submit_or_the_creator_is_refused(
    client, workspace, workspace_1
):
    form = await a_form(workspace)
    submit_proof = await solved(client, workspace, form)
    other = await workspace_proof(client, workspace_1)
    creator = await creator_proof(client)
    with _mailing() as mailed:
        for proof in (submit_proof, other, creator):
            refused = await workspace_code(client, workspace, proof=proof)
            assert refused.status_code == 422, refused.text
            assert refused.json()["code"] == "captcha_invalid"
        mailed.assert_not_called()


async def test_a_mail_proof_is_no_good_for_a_submit(client, workspace):
    form = await a_form(workspace)
    proof = await workspace_proof(client, workspace)
    refused = await submit(client, workspace, form, proof)
    assert refused.status_code == 422 and refused.json()["code"] == "captcha_invalid"
    # and a challenge for the form's mail is no proof of a submit either
    draft = await workspace_proof(client, workspace, form)
    refused = await submit(client, workspace, form, draft)
    assert refused.status_code == 422 and refused.json()["code"] == "captcha_invalid"


async def test_the_creator_code_needs_a_proof_and_only_the_creators(
    client, workspace
):
    with _mailing() as mailed:
        missing = await creator_code(client)
        assert missing.status_code == 422
        assert missing.json()["code"] == "captcha_missing"
        # a workspace's mail proof is not the creator's
        wrong = await creator_code(client, proof=await workspace_proof(client, workspace))
        assert wrong.status_code == 422 and wrong.json()["code"] == "captcha_invalid"
        assert mailed.await_count == 0
        sent = await creator_code(client, proof=await creator_proof(client))
        assert sent.status_code == 200, sent.text
        assert mailed.await_count == 1


async def test_a_workspace_that_does_not_exist_answers_as_before(client):
    # no mail, so no proof is asked: the route's own 404, nothing claimed
    class Missing:
        id = "64a1b2c3d4e5f60718293a4c"

    with _mailing() as mailed:
        answer = await workspace_code(client, Missing())
    assert answer.status_code == 404
    mailed.assert_not_called()


async def test_a_proof_for_another_network_is_refused(client, workspace):
    proof = await workspace_proof(client, workspace, headers=ALICE)
    with _mailing():
        refused = await workspace_code(client, workspace, proof=proof, headers=BOB)
    assert refused.status_code == 422 and refused.json()["code"] == "captcha_invalid"


# -- the draft link


async def test_the_draft_link_needs_a_proof_bound_to_the_form(
    client, workspace, drafts_mail
):
    form, other = await drafting_form(workspace), await drafting_form(workspace)
    link = url(workspace, form, "/link")

    async def ask_link(proof=None):
        headers = dict(ALICE)
        if proof:
            headers[ch.HEADER] = proof
        return await client.post(link, json=body(email=ADDRESS), headers=headers)

    missing = await ask_link()
    assert missing.status_code == 422 and missing.json()["code"] == "captcha_missing"
    assert drafts_mail == [] and await counters() == 0
    # a proof of another form's link, or of the workspace's sign-in code
    for wrong in (
        await workspace_proof(client, workspace, other),
        await workspace_proof(client, workspace),
        await solved(client, workspace, form),
    ):
        refused = await ask_link(wrong)
        assert refused.status_code == 422 and refused.json()["code"] == "captcha_invalid"
    assert drafts_mail == []
    proof = await workspace_proof(client, workspace, form)
    sent = await ask_link(proof)
    assert sent.status_code == 200, sent.text
    assert len(drafts_mail) == 1
    replay = await ask_link(proof)
    assert replay.status_code == 422 and replay.json()["code"] == "captcha_replayed"
    assert len(drafts_mail) == 1


async def test_saving_a_draft_needs_no_proof(client, workspace, drafts_mail):
    form = await drafting_form(workspace)
    saved = await client.put(
        url(workspace, form), json=body(editKey=None), headers=ALICE
    )
    assert saved.status_code != 422 or saved.json().get("code") not in (
        "captcha_missing",
    )


# -- the counts


async def test_the_counts_are_by_day_form_purpose_and_outcome_and_name_nobody(
    client, workspace, test_user_cookies
):
    form = await a_form(workspace)
    await submit(client, workspace, form)  # missing
    proof = await solved(client, workspace, form)
    await submit(client, workspace, form, proof)  # verified
    await submit(client, workspace, form, proof)  # replayed
    mail = await workspace_proof(client, workspace)
    with _mailing():
        await workspace_code(client, workspace, proof=mail)
    stats = container.captcha_stats()
    await stats.flush()
    rows = await container.captcha_count_repo().many()
    assert rows and all(set(r.model_dump()) >= {"day", "outcome", "count"} for r in rows)
    dump = json.dumps([r.model_dump(mode="json") for r in rows])
    for secret in ("203.0.113", ADDRESS, "example.org", ch.HEADER, proof[:20]):
        assert secret not in dump
    keys = {(r.purpose, r.outcome, r.form_id or "-") for r in rows}
    assert ("submit", "missing", str(form.form_id)) in keys
    assert ("submit", "verified", str(form.form_id)) in keys
    assert ("submit", "replayed", str(form.form_id)) in keys
    assert ("mail", "verified", "-") in keys
    form_counts = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/captcha/stats",
        cookies=test_user_cookies,
    )
    assert form_counts.status_code == 200, form_counts.text
    assert form_counts.json()["submit"] == {"passed": 1, "blocked": 2}
    assert form_counts.json()["mail"] == {"passed": 0, "blocked": 0}
    totals = await client.get(
        f"/api/v1/workspaces/{workspace.id}/captcha/stats", cookies=test_user_cookies
    )
    assert totals.json()["submit"] == {"passed": 1, "blocked": 2}
    assert totals.json()["mail"]["passed"] == 1
    assert totals.json()["days"] == 30


async def test_the_counts_are_buffered_not_written_per_request(client, workspace):
    form = await a_form(workspace)
    stats = container.captcha_stats()
    await stats.flush()
    before = await container.captcha_count_repo().many()
    for _ in range(5):
        await submit(client, workspace, form)  # missing, five times
    # written later, in one batch: nothing yet
    assert await container.captcha_count_repo().many() == before
    assert sum(stats._waiting.values()) >= 5
    await stats.flush()
    rows = await container.captcha_count_repo().many()
    missing = [r for r in rows if r.outcome == "missing" and r.form_id == str(form.form_id)]
    assert len(missing) == 1 and missing[0].count == 5


async def test_the_counts_of_a_form_need_a_member_of_its_workspace(
    client, workspace, workspace_1
):
    form = await a_form(workspace)
    for cookies in (None,):
        denied = await client.get(
            f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/captcha/stats",
            cookies=cookies,
        )
        assert denied.status_code in (401, 403)
    denied = await client.get(
        f"/api/v1/workspaces/{workspace.id}/captcha/stats"
    )
    assert denied.status_code in (401, 403)


async def test_a_failing_claim_store_answers_503_and_sends_no_code(
    client, workspace, monkeypatch
):
    proof = await workspace_proof(client, workspace)

    async def broken(*args, **kwargs):
        raise RuntimeError("down")

    monkeypatch.setattr(container.rate_limiter(), "claim", broken)
    with _mailing() as mailed:
        refused = await workspace_code(client, workspace, proof=proof)
    assert refused.status_code == 503, refused.text
    assert refused.json()["code"] == "rate_limiter_unavailable"
    assert refused.headers["Retry-After"] == "60"
    mailed.assert_not_called()
