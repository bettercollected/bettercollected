"""Another form's answers are only ever the answers a question's creator opted in
(``shareAsChoices``) and that were given while the version the respondent filled
said so: before the setting, on a version without it, and after it is turned off,
nothing is offered. Also what keeps a source cheap and safe to rebuild."""

import asyncio
import json

import pytest
from common.services.crypto_service import crypto_service
from sqlalchemy import update

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.option_sources import service as module
from backend.app.services.option_sources import share_token
from backend.app.services.option_sources import text
from backend.app.services.option_sources.checks import INVALID_CODE
from backend.app.services.option_sources.service import NOT_SHARED_CODE
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.option_sources.helpers import (
    choice,
    page_token,
    publish,
    question,
    submit,
)
from tests.app.option_sources.helpers import text as text_answer

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def switched_on(sources_on):
    pass


def sources():
    return container.option_source_service()


def listed(built):
    return [o.label for o in built.options]


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


def code_of(error: HTTPException) -> str:
    return (
        error.content["code"] if isinstance(error.content, dict) else str(error.content)
    )


async def options_of(workspace, form, question_id="name"):
    return await sources().options(
        workspace.id,
        {"kind": "form_answers", "form_id": form.form_id, "question_id": question_id},
    )


async def set_share(form, value, question_id="name", publish_again=None):
    """The question's setting in the draft (and a new published version when
    ``publish_again`` is the workspace)."""
    repo = container.form_repo()
    stored = await repo.get_form_document_by_id(form.form_id)
    for slide in stored.fields:
        for field in slide.properties.fields:
            if field.id == question_id:
                field.properties.share_as_choices = value
    await repo.save_form(stored)
    if publish_again is not None:
        await container.workspace_form_service().publish_form(
            publish_again.id, form.form_id, testUser
        )


async def register(workspace, form, name, role=None):
    answers = {"name": text_answer(name)}
    if role:
        answers["role"] = choice(role)
    return await submit(workspace, form, answers)


@pytest.fixture()
async def plain(workspace):
    """A participants form whose name question does not share its answers."""
    return await publish(
        workspace,
        [
            question("name", "short_text", "Name"),
            question(
                "role",
                "dropdown",
                "Role",
                choices=[{"id": "r1", "value": "Guest"}],
                share_as_choices=True,
            ),
        ],
        title="Participants",
    )


async def test_nothing_is_offered_from_a_question_that_does_not_share(workspace, plain):
    await register(workspace, plain, "Alice", "r1")
    built = await options_of(workspace, plain)
    assert built.available is False and built.options == ()
    # another question of the same form that does share is offered
    assert listed(await options_of(workspace, plain, "role")) == ["Guest"]


async def test_the_response_records_what_it_shared_and_a_client_cannot_claim_more(
    workspace, plain
):
    from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel

    await container.workspace_form_service().submit_response(
        workspace.id,
        plain.form_id,
        StandardFormResponseCamelModel(
            answers={"name": text_answer("Alice")}, shared_as_choices=["name", "role"]
        ),
        testUser,
        share_notice_token=await page_token(workspace, plain),
    )
    [row] = await container.form_response_repo().list_by_form_id(
        await container.form_response_service().scope(workspace.id, [plain.form_id])
    )
    assert row.shared_as_choices == ["role"]
    assert (await options_of(workspace, plain)).options == ()


async def _stamped(workspace, form):
    rows = await container.form_response_repo().list_by_form_id(
        await container.form_response_service().scope(workspace.id, [form.form_id])
    )
    return [r.shared_as_choices for r in rows]


async def test_only_what_the_page_showed_is_stamped_a_publish_after_the_fetch_adds_nothing(
    workspace, plain
):
    # the respondent loaded the form while "name" did not share
    token = await page_token(workspace, plain)
    # the creator turns sharing on and publishes before they submit
    await set_share(plain, True, publish_again=workspace)
    await submit(
        workspace, plain, {"name": text_answer("Late")}, share_notice_token=token
    )
    # ("role" shared on both: stamped; "name" was not on the page: not stamped)
    assert await _stamped(workspace, plain) == [["role"]]
    assert (await options_of(workspace, plain)).options == ()


async def test_turning_sharing_off_after_the_fetch_stamps_nothing_for_it(
    workspace, plain
):
    await set_share(plain, True, publish_again=workspace)
    token = await page_token(workspace, plain)
    await set_share(plain, False, publish_again=workspace)
    await submit(
        workspace, plain, {"name": text_answer("Early")}, share_notice_token=token
    )
    assert await _stamped(workspace, plain) == [["role"]]
    assert (await options_of(workspace, plain)).options == ()


async def test_no_token_a_bad_token_or_another_forms_token_stamps_nothing(
    workspace, plain
):
    await set_share(plain, True, publish_again=workspace)
    other = await publish(
        workspace,
        [question("name", "short_text", "Name", share_as_choices=True)],
        title="Other",
    )
    good = await page_token(workspace, plain)
    for token in (None, "", "garbage", good[:-3] + "AAA", await page_token(workspace, other)):
        await submit(
            workspace, plain, {"name": text_answer("X")}, share_notice_token=token
        )
    assert await _stamped(workspace, plain) == [[]] * 5
    assert (await options_of(workspace, plain)).options == ()


async def test_an_expired_token_stamps_nothing(workspace, plain, monkeypatch):
    import datetime as dt

    await set_share(plain, True, publish_again=workspace)
    old = share_token.issue_token(
        workspace_id=workspace.id,
        form_id=plain.form_id,
        question_ids=["name"],
        now=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=25),
    )
    await submit(workspace, plain, {"name": text_answer("Stale")}, share_notice_token=old)
    assert await _stamped(workspace, plain) == [[]]
    assert (await options_of(workspace, plain)).options == ()


async def test_answers_from_before_the_setting_and_from_a_version_without_it_are_never_offered(
    workspace, plain
):
    await register(workspace, plain, "Before")
    # turned on in the draft only: the published version still says no
    await set_share(plain, True)
    await register(workspace, plain, "On the old version")
    assert (await options_of(workspace, plain)).options == ()
    # published: only what is answered from now on counts
    await set_share(plain, True, publish_again=workspace)
    await register(workspace, plain, "After")
    assert listed(await options_of(workspace, plain)) == ["After"]


async def test_turning_the_setting_off_stops_every_use_at_once(workspace, plain):
    await set_share(plain, True, publish_again=workspace)
    await register(workspace, plain, "Alice")
    assert listed(await options_of(workspace, plain)) == ["Alice"]
    await set_share(plain, False)
    built = await options_of(workspace, plain)
    assert built.available is False and built.options == ()
    # on again: the answers given while it was on are back (their consent was given then)
    await set_share(plain, True)
    assert listed(await options_of(workspace, plain)) == ["Alice"]


async def test_a_question_that_does_not_share_cannot_be_chosen_when_saving(
    workspace, plain
):
    source = {"kind": "form_answers", "form_id": plain.form_id, "question_id": "name"}
    error = await refused(sources().authorize_source(workspace.id, source, testUser))
    assert error.status_code == 422 and code_of(error) == NOT_SHARED_CODE
    await set_share(plain, True)
    await sources().authorize_source(workspace.id, source, testUser)


async def test_the_setting_belongs_to_questions_that_can_share_and_to_the_switch(
    workspace, monkeypatch
):
    service = container.workspace_form_service()
    from common.models.standard_form import StandardForm

    def form(*questions):
        return StandardForm(
            builder_version="v2",
            title="F",
            fields=[
                {
                    "id": "s",
                    "type": "slide",
                    "index": 0,
                    "properties": {"fields": list(questions)},
                }
            ],
        )

    for bad in (
        question("e", "email", "Email", why_we_ask="To reply", share_as_choices=True),
        question("i", "short_text", "Staff", share_as_choices=True, **{}),
    ):
        if bad["id"] == "i":
            bad["internal"] = True
        error = await refused(service.create_form(workspace.id, form(bad), testUser))
        assert code_of(error) == INVALID_CODE
    # off, turning it on is refused like the rest of the feature; stored stays
    created = await service.create_form(
        workspace.id,
        form(question("n", "short_text", "Name", share_as_choices=True)),
        testUser,
    )
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", False)
    error = await refused(
        service.create_form(
            workspace.id,
            form(question("n", "short_text", "Name", share_as_choices=True)),
            testUser,
        )
    )
    assert code_of(error) == "option_sources_disabled"
    await service.create_form(
        workspace.id, form(question("n", "short_text", "Name")), testUser
    )
    assert created.form_id


# ----------------------------------------------------------------------- building


@pytest.fixture()
async def shared(workspace):
    return await publish(
        workspace,
        [
            question("name", "short_text", "Name", share_as_choices=True),
            question(
                "gate",
                "dropdown",
                "Gate",
                choices=[{"id": "y", "value": "Yes"}, {"id": "n", "value": "No"}],
            ),
            question(
                "note",
                "short_text",
                "Note",
                share_as_choices=True,
                logic={
                    "action": "SHOW",
                    "operator": "AND",
                    "conditions": [
                        {
                            "field_id": "gate",
                            "field_type": "dropdown",
                            "comparison": "IS_EQUAL",
                            "value": "Yes",
                        }
                    ],
                },
            ),
        ],
        title="Shared",
    )


async def test_an_answer_a_logic_rule_hid_is_not_offered(workspace, shared):
    await submit(
        workspace,
        shared,
        {
            "name": text_answer("Alice"),
            "gate": choice("n"),
            "note": text_answer("Hidden note"),
        },
    )
    await submit(
        workspace,
        shared,
        {
            "name": text_answer("Bob"),
            "gate": choice("y"),
            "note": text_answer("Shown note"),
        },
    )
    assert listed(await options_of(workspace, shared, "note")) == ["Shown note"]


async def test_a_response_that_cannot_be_read_is_skipped_not_a_failure(
    workspace, shared
):
    good = await submit(workspace, shared, {"name": text_answer("Alice")})
    bad = await submit(workspace, shared, {"name": text_answer("Broken")})
    repo = container.form_response_repo()
    table = repo.row.__table__
    async with repo._session() as session, session.begin():
        await session.execute(
            update(table)
            .where(table.c.response_id == bad.response_id)
            .values(doc=table.c.doc.op("||")({"answers": "not-a-ciphertext"}))
        )
    built = await options_of(workspace, shared)
    assert listed(built) == ["Alice"] and good.response_id


async def test_an_edit_of_any_response_changes_the_options_even_the_oldest(
    workspace, shared
):
    first = await submit(workspace, shared, {"name": text_answer("Old")})
    await submit(workspace, shared, {"name": text_answer("Newer")})
    await submit(workspace, shared, {"name": text_answer("Newest")})
    assert listed(await options_of(workspace, shared)) == ["Newer", "Newest", "Old"]
    repo = container.form_response_repo()
    stored = await repo.get_response(first.response_id)
    stored.answers = crypto_service.encrypt(
        workspace_id=workspace.id,
        form_id=shared.form_id,
        data=json.dumps({"name": {"type": "text", "text": "Edited"}}),
    )
    await repo.save(stored)
    assert listed(await options_of(workspace, shared)) == ["Edited", "Newer", "Newest"]


async def test_a_retyped_or_unshared_question_rebuilds_at_once(workspace, shared):
    await submit(workspace, shared, {"name": text_answer("Alice")})
    assert listed(await options_of(workspace, shared)) == ["Alice"]
    repo = container.form_repo()
    stored = await repo.get_form_document_by_id(shared.form_id)
    for slide in stored.fields:
        for field in slide.properties.fields:
            if field.id == "name":
                field.type = "email"
    await repo.save_form(stored)
    assert (await options_of(workspace, shared)).options == ()


async def test_the_options_are_sorted_before_they_are_cut(
    workspace, shared, monkeypatch
):
    monkeypatch.setattr(text, "ANSWER_OPTIONS_MAX", 2)
    for name in ("delta", "alpha", "echo", "bravo", "charlie"):
        await submit(workspace, shared, {"name": text_answer(name)})
    built = await options_of(workspace, shared)
    assert listed(built) == ["alpha", "bravo"] and built.truncated


async def test_a_source_that_only_grew_is_served_as_it_was_briefly_but_a_submission_checks_afresh(
    workspace, shared
):
    clock = {"t": 1000.0}
    monkeypatch_clock = sources()
    original = monkeypatch_clock._monotonic
    monkeypatch_clock._monotonic = lambda: clock["t"]
    try:
        await submit(workspace, shared, {"name": text_answer("Alice")})
        source = {
            "kind": "form_answers",
            "form_id": shared.form_id,
            "question_id": "name",
        }
        assert listed(
            await sources().options(workspace.id, source, tolerate_growth=True)
        ) == ["Alice"]
        await submit(workspace, shared, {"name": text_answer("Bob")})
        # grew a moment ago: the public endpoint may still serve the earlier copy
        assert listed(
            await sources().options(workspace.id, source, tolerate_growth=True)
        ) == ["Alice"]
        # a submission never does
        assert listed(await sources().options(workspace.id, source)) == ["Alice", "Bob"]
        # and it shrinks at once
        await submit(workspace, shared, {"name": text_answer("Carol")})
        clock["t"] += module.GROWTH_DEBOUNCE_SECONDS + 1
        assert (
            len(
                listed(
                    await sources().options(workspace.id, source, tolerate_growth=True)
                )
            )
            == 3
        )
        repo = container.form_response_repo()
        rows = await repo.list_by_form_id(
            await container.form_response_service().scope(
                workspace.id, [shared.form_id]
            )
        )
        await repo.add_deletion_request(rows[0], rows[0].response_id)
        assert (
            len(
                listed(
                    await sources().options(workspace.id, source, tolerate_growth=True)
                )
            )
            == 2
        )
    finally:
        monkeypatch_clock._monotonic = original


async def test_the_cache_is_bounded_by_the_options_it_holds(
    workspace, shared, monkeypatch
):
    monkeypatch.setattr(module, "SOURCE_CACHE_ITEMS", 3)
    for name in ("a", "b", "c"):
        await submit(workspace, shared, {"name": text_answer(name)})
    await options_of(workspace, shared)
    assert sources()._items == 3
    await submit(workspace, shared, {"name": text_answer("d")})
    await options_of(workspace, shared)
    # four options do not fit three: the entry is dropped, never kept over the bound
    assert sources()._items <= 3
    assert sources()._items == sum(
        len(c.value.options) for c in sources()._cache.values()
    )


async def test_rebuilds_run_at_most_a_few_at_once(workspace, shared, monkeypatch):
    running = {"now": 0, "most": 0}
    original = sources()._rebuild

    async def slow(*args, **kwargs):
        running["now"] += 1
        running["most"] = max(running["most"], running["now"])
        await asyncio.sleep(0.05)
        try:
            return await original(*args, **kwargs)
        finally:
            running["now"] -= 1

    monkeypatch.setattr(sources(), "_rebuild", slow)
    sources()._rebuilds = asyncio.Semaphore(module.REBUILDS_AT_ONCE)
    await submit(workspace, shared, {"name": text_answer("Alice")})
    forms = [
        {"kind": "form_answers", "form_id": shared.form_id, "question_id": q}
        for q in ("name", "note", "gate", "x1", "x2", "x3")
    ]
    await asyncio.gather(*(sources().options(workspace.id, s) for s in forms))
    assert 1 <= running["most"] <= module.REBUILDS_AT_ONCE


async def test_without_a_secret_to_key_ids_another_forms_answers_are_not_used(
    workspace, shared, monkeypatch
):
    await submit(workspace, shared, {"name": text_answer("Alice")})
    monkeypatch.setattr(settings.auth_settings, "JWT_SECRET", "")
    built = await options_of(workspace, shared)
    assert built.available is False and built.options == ()
    source = {"kind": "form_answers", "form_id": shared.form_id, "question_id": "name"}
    error = await refused(sources().authorize_source(workspace.id, source, testUser))
    assert error.status_code == 422 and code_of(error) == INVALID_CODE


def _ring(monkeypatch, *members):
    from backend.config import settings

    monkeypatch.setattr(settings.auth_settings, "JWT_SECRET", ",".join(members))


def test_the_notice_token_survives_a_key_rotation(monkeypatch):
    a, b = "a" * 40, "b" * 40
    kw = {"workspace_id": "w1", "form_id": "f1"}
    _ring(monkeypatch, a)
    token = share_token.issue_token(question_ids=["q1", "q2"], **kw)
    assert share_token.shown_question_ids(token, **kw) == ["q1", "q2"]
    # add_key: [a, b]; promote: [b, a]: a token in flight still verifies
    for members in ((a, b), (b, a)):
        _ring(monkeypatch, *members)
        assert share_token.shown_question_ids(token, **kw) == ["q1", "q2"]
    # a token signed under the new primary verifies while the old one is in the ring ...
    newer = share_token.issue_token(question_ids=["q3"], **kw)
    _ring(monkeypatch, a, b)
    assert share_token.shown_question_ids(newer, **kw) == ["q3"]
    # ... and neither after both keys changed
    _ring(monkeypatch, "c" * 40)
    assert share_token.shown_question_ids(token, **kw) == []
    assert share_token.shown_question_ids(newer, **kw) == []
    # drop_old: the old token is gone with its key, the new one stays
    _ring(monkeypatch, b)
    assert share_token.shown_question_ids(token, **kw) == []
    assert share_token.shown_question_ids(newer, **kw) == ["q3"]


def test_a_token_naming_the_most_questions_fits_the_routes_cap():
    import uuid

    ids = [str(uuid.uuid4()) for _ in range(share_token.MAX_QUESTIONS)]
    kw = {"workspace_id": str(uuid.uuid4()), "form_id": str(uuid.uuid4())}
    token = share_token.issue_token(question_ids=ids, **kw)
    # (the cap used to be 4096, which this exceeds)
    assert 4096 < len(token) <= share_token.MAX_TOKEN_LENGTH
    assert sorted(share_token.shown_question_ids(token, **kw)) == sorted(ids)
    # an id too long to fit is never named, so a token never exceeds the cap
    long_id = "x" * (share_token.MAX_ID_LENGTH + 1)
    assert share_token.issue_token(question_ids=[long_id], **kw) is None
