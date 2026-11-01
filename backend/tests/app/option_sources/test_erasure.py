"""When a response that offered an answer as an option is erased, the choices
other people made from it show ``[removed]`` (once no eligible response still
offers it), whichever way the response goes."""

import datetime as dt

import pytest
from common.clock import utcnow

from backend.app.container import container
from backend.app.services.option_sources import erasure
from tests.app.controllers.data import testUser, testUser1
from tests.app.option_sources.helpers import (
    choice,
    choices,
    publish,
    question,
    stored_answers,
    submit,
)
from tests.app.option_sources.helpers import text as text_answer

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def switched_on(sources_on):
    pass


def sources():
    return container.option_source_service()


async def people_form(workspace):
    return await publish(
        workspace,
        [question("name", "short_text", "Name", share_as_choices=True)],
        title="People",
    )


async def consumer_form(workspace, people, kind="dropdown", title="Who comes", **extra):
    return await publish(
        workspace,
        [
            question(
                "who",
                kind,
                "Who",
                source={
                    "kind": "form_answers",
                    "form_id": people.form_id,
                    "question_id": "name",
                },
                **extra,
            )
        ],
        title=title,
    )


async def option_ids(workspace, people):
    built = await sources().options(
        workspace.id,
        {"kind": "form_answers", "form_id": people.form_id, "question_id": "name"},
    )
    return {o.label: o.id for o in built.options}


async def response_of(workspace, form, name):
    scope = await container.form_response_service().scope(workspace.id, [form.form_id])
    for row in await container.form_response_repo().list_by_form_id(scope):
        decrypted = container.form_response_service().decrypt_form_response(
            workspace_id=workspace.id, response=row.model_copy(deep=True)
        )
        if decrypted.answers["name"]["text"] == name:
            return row
    raise AssertionError("no such response")


def snapshots(answers):
    out = []
    for a in answers:
        if "choice" in a["who"]:
            out.append(a["who"]["choice"]["label"])
        else:
            out.append(tuple(sorted(a["who"]["choices"]["labels"].values())))
    return sorted(out, key=str)


def after_grace():
    return utcnow() + erasure.NOTE_GRACE + dt.timedelta(minutes=1)


async def pending():
    return await container.option_erasure_repo().pending_count()


async def test_erasing_the_only_response_offering_an_option_redacts_what_others_chose(
    workspace,
):
    people = await people_form(workspace)
    for name in ("Alice", "Bob"):
        await submit(workspace, people, {"name": text_answer(name)})
    ids = await option_ids(workspace, people)
    consumers = await consumer_form(workspace, people)
    await submit(workspace, consumers, {"who": choice(ids["Alice"])})
    await submit(workspace, consumers, {"who": choice(ids["Bob"])})
    alice = await response_of(workspace, people, "Alice")
    await container.form_response_service().delete_form_response(
        people.form_id, alice.response_id, workspace.id
    )
    assert await pending() == 1
    counts = await sources().redact_erased()
    assert counts == {"notes": 1, "redacted": 1, "failed": 0, "expired": 0}
    assert snapshots(await stored_answers(workspace, consumers)) == [
        "Bob",
        erasure.REMOVED_LABEL,
    ]
    # the note stays for the grace period (a submit may still be committing)
    assert await pending() == 1
    # the stored id stays (the answer still says which option it was), the text is gone
    [answers] = [
        a
        for a in await stored_answers(workspace, consumers)
        if a["who"]["choice"]["label"] == erasure.REMOVED_LABEL
    ]
    assert answers["who"]["choice"]["value"] == ids["Alice"]
    # idempotent: another pass changes nothing; after the grace the note goes
    assert await sources().redact_erased() == {
        "notes": 1,
        "redacted": 0,
        "failed": 0,
        "expired": 0,
    }
    assert await sources().redact_erased(now=after_grace()) == {
        "notes": 1,
        "redacted": 0,
        "failed": 0,
        "expired": 1,
    }
    assert await pending() == 0
    assert await sources().redact_erased() == {
        "notes": 0,
        "redacted": 0,
        "failed": 0,
        "expired": 0,
    }


async def test_erasing_one_of_two_responses_offering_the_same_option_changes_nothing(
    workspace,
):
    people = await people_form(workspace)
    await submit(workspace, people, {"name": text_answer("Alice")}, user=testUser)
    await submit(workspace, people, {"name": text_answer("alice ")}, user=testUser1)
    ids = await option_ids(workspace, people)
    assert list(ids) == ["Alice"]
    consumers = await consumer_form(workspace, people)
    await submit(workspace, consumers, {"who": choice(ids["Alice"])})
    first = await response_of(workspace, people, "Alice")
    await container.form_response_service().delete_form_response(
        people.form_id, first.response_id, workspace.id
    )
    counts = await sources().redact_erased()
    assert counts["redacted"] == 0 and counts["notes"] == 1
    assert snapshots(await stored_answers(workspace, consumers)) == ["Alice"]
    # erasing the second one too: now nothing offers it
    second = await response_of(workspace, people, "alice ")
    await container.form_response_service().delete_form_response(
        people.form_id, second.response_id, workspace.id
    )
    await sources().redact_erased()
    assert snapshots(await stored_answers(workspace, consumers)) == [
        erasure.REMOVED_LABEL
    ]


async def test_a_multiple_choice_consumer_and_a_second_consuming_form_are_redacted(
    workspace,
):
    people = await people_form(workspace)
    for name in ("Alice", "Bob", "Carol"):
        await submit(workspace, people, {"name": text_answer(name)})
    ids = await option_ids(workspace, people)
    many = await consumer_form(
        workspace, people, "multiple_choice", "Many", allow_multiple_selection=True
    )
    other = await consumer_form(workspace, people, title="Other")
    await submit(workspace, many, {"who": choices(ids["Alice"], ids["Bob"])})
    await submit(workspace, other, {"who": choice(ids["Alice"])})
    alice = await response_of(workspace, people, "Alice")
    await container.form_response_service().delete_form_response(
        people.form_id, alice.response_id, workspace.id
    )
    await sources().redact_erased()
    assert snapshots(await stored_answers(workspace, many)) == [
        ("Bob", erasure.REMOVED_LABEL)
    ]
    assert snapshots(await stored_answers(workspace, other)) == [erasure.REMOVED_LABEL]


async def test_every_way_a_response_goes_is_covered(workspace):
    people = await people_form(workspace)
    for name in ("Alice", "Bob", "Carol"):
        await submit(workspace, people, {"name": text_answer(name)})
    ids = await option_ids(workspace, people)
    consumers = await consumer_form(workspace, people)
    for name in ("Alice", "Bob", "Carol"):
        await submit(workspace, consumers, {"who": choice(ids[name])})
    # retention (the scheduled delete of one response)
    alice = await response_of(workspace, people, "Alice")
    await container.form_response_service().delete_response(alice.response_id)
    # a deletion request completed by staff
    bob = await response_of(workspace, people, "Bob")
    repo = container.form_response_repo()
    await repo.add_deletion_request(bob, bob.response_id)
    await container.form_response_service().delete_form_response(
        people.form_id, bob.response_id, workspace.id
    )
    counts = await sources().redact_erased()
    assert counts["notes"] == 2 and counts["redacted"] == 2
    assert snapshots(await stored_answers(workspace, consumers)) == [
        "Carol",
        erasure.REMOVED_LABEL,
        erasure.REMOVED_LABEL,
    ]
    # the whole form going (every response at once)
    await container.form_response_service().delete_form_responses(people.form_id)
    await sources().redact_erased()
    assert snapshots(await stored_answers(workspace, consumers)) == [
        erasure.REMOVED_LABEL
    ] * 3


async def test_a_failed_run_leaves_the_note_and_the_next_run_finishes(
    workspace, monkeypatch
):
    people = await people_form(workspace)
    await submit(workspace, people, {"name": text_answer("Alice")})
    ids = await option_ids(workspace, people)
    consumers = await consumer_form(workspace, people)
    await submit(workspace, consumers, {"who": choice(ids["Alice"])})
    alice = await response_of(workspace, people, "Alice")
    await container.form_response_service().delete_form_response(
        people.form_id, alice.response_id, workspace.id
    )

    async def broken(*args, **kwargs):
        raise RuntimeError("database away")

    monkeypatch.setattr(sources(), "_answer_options", broken)
    counts = await sources().redact_erased()
    assert counts == {"notes": 0, "redacted": 0, "failed": 1, "expired": 0}
    assert await pending() == 1
    assert snapshots(await stored_answers(workspace, consumers)) == ["Alice"]
    monkeypatch.undo()
    assert (await sources().redact_erased())["redacted"] == 1
    assert snapshots(await stored_answers(workspace, consumers)) == [
        erasure.REMOVED_LABEL
    ]


async def test_it_works_with_the_switch_off_and_a_note_holds_no_text(
    workspace, monkeypatch
):
    from backend.config import settings

    people = await people_form(workspace)
    await submit(workspace, people, {"name": text_answer("Alice")})
    ids = await option_ids(workspace, people)
    consumers = await consumer_form(workspace, people)
    await submit(workspace, consumers, {"who": choice(ids["Alice"])})
    alice = await response_of(workspace, people, "Alice")
    await container.form_response_service().delete_form_response(
        people.form_id, alice.response_id, workspace.id
    )
    [note] = await container.option_erasure_repo().pending(10)
    assert note.option_ids == [ids["Alice"]] and "Alice" not in note.model_dump_json()
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", False)
    assert (await sources().redact_erased())["redacted"] == 1


async def test_the_redaction_starts_by_itself_after_the_erasure(workspace):
    sources()._auto_redact = True
    people = await people_form(workspace)
    await submit(workspace, people, {"name": text_answer("Alice")})
    ids = await option_ids(workspace, people)
    consumers = await consumer_form(workspace, people)
    await submit(workspace, consumers, {"who": choice(ids["Alice"])})
    alice = await response_of(workspace, people, "Alice")
    await container.form_response_service().delete_form_response(
        people.form_id, alice.response_id, workspace.id
    )
    await sources()._redaction_task
    assert snapshots(await stored_answers(workspace, consumers)) == [
        erasure.REMOVED_LABEL
    ]
    assert await pending() == 1  # kept for the grace period


async def test_a_response_that_shared_nothing_leaves_no_note(workspace):
    people = await publish(
        workspace, [question("name", "short_text", "Name")], title="Plain"
    )
    await submit(workspace, people, {"name": text_answer("Alice")})
    row = await response_of(workspace, people, "Alice")
    await container.form_response_service().delete_form_response(
        people.form_id, row.response_id, workspace.id
    )
    assert await pending() == 0


async def test_redacting_answers_is_idempotent_and_only_touches_the_named_options():
    answers = {
        "who": {
            "type": "choices",
            "choices": {
                "values": ["fa1", "fa2"],
                "labels": {"fa1": "A", "fa2": "B"},
            },
        },
        "one": {"type": "choice", "choice": {"value": "fa1", "label": "A"}},
        "plain": {"type": "choice", "choice": {"value": "fa1"}},
    }
    assert erasure.redact_answers(answers, ["who", "one"], {"fa1"}) == 2
    assert answers["who"]["choices"]["labels"] == {
        "fa1": erasure.REMOVED_LABEL,
        "fa2": "B",
    }
    assert answers["one"]["choice"]["label"] == erasure.REMOVED_LABEL
    assert "label" not in answers["plain"]["choice"]
    assert erasure.redact_answers(answers, ["who", "one"], {"fa1"}) == 0


async def test_a_consumer_committed_after_the_first_pass_is_redacted_by_the_next(
    workspace, monkeypatch
):
    people = await people_form(workspace)
    await submit(workspace, people, {"name": text_answer("Alice")})
    ids = await option_ids(workspace, people)
    consumers = await consumer_form(workspace, people)
    alice = await response_of(workspace, people, "Alice")
    await container.form_response_service().delete_form_response(
        people.form_id, alice.response_id, workspace.id
    )
    first = await sources().redact_erased()
    assert first["redacted"] == 0 and first["notes"] == 1

    # a submission whose option check ran while the erased response still
    # offered "Alice" commits only now, with the label it was given then
    async def checked_earlier(self_, workspace_id, form, answers, *args, **kwargs):
        done = dict(answers)
        done["who"] = choice(ids["Alice"], label="Alice")
        return done

    monkeypatch.setattr(type(sources()), "apply", checked_earlier)
    await submit(workspace, consumers, {"who": choice(ids["Alice"])})
    monkeypatch.undo()
    assert snapshots(await stored_answers(workspace, consumers)) == ["Alice"]

    second = await sources().redact_erased()
    assert second["redacted"] == 1
    assert snapshots(await stored_answers(workspace, consumers)) == [
        erasure.REMOVED_LABEL
    ]
    # past the grace the note is removed and a later pass does nothing more
    assert (await sources().redact_erased(now=after_grace()))["expired"] == 1
    assert await pending() == 0


async def test_a_note_that_could_not_be_worked_is_not_removed_when_it_expires(
    workspace, monkeypatch
):
    people = await people_form(workspace)
    await submit(workspace, people, {"name": text_answer("Alice")})
    ids = await option_ids(workspace, people)
    consumers = await consumer_form(workspace, people)
    await submit(workspace, consumers, {"who": choice(ids["Alice"])})
    alice = await response_of(workspace, people, "Alice")
    await container.form_response_service().delete_form_response(
        people.form_id, alice.response_id, workspace.id
    )

    async def broken(*args, **kwargs):
        raise RuntimeError("database away")

    monkeypatch.setattr(sources(), "_answer_options", broken)
    counts = await sources().redact_erased(now=after_grace())
    assert counts["failed"] == 1 and counts["expired"] == 0
    assert await pending() == 1


async def test_notes_are_worked_through_page_by_page(workspace):
    people = await people_form(workspace)
    for name in ("Alice", "Bob", "Carol"):
        await submit(workspace, people, {"name": text_answer(name)})
    ids = await option_ids(workspace, people)
    consumers = await consumer_form(workspace, people)
    for name in ("Alice", "Bob", "Carol"):
        await submit(workspace, consumers, {"who": choice(ids[name])})
        row = await response_of(workspace, people, name)
        await container.form_response_service().delete_form_response(
            people.form_id, row.response_id, workspace.id
        )
    counts = await sources().redact_erased(limit=1)
    assert counts["notes"] == 3 and counts["redacted"] == 3
    assert snapshots(await stored_answers(workspace, consumers)) == [
        erasure.REMOVED_LABEL
    ] * 3


# ------------------------------------------------------------- key rotation

RING_A = "a" * 40
RING_B = "b" * 40


def ring(monkeypatch, *members):
    from backend.config import settings

    monkeypatch.setattr(settings.auth_settings, "JWT_SECRET", ",".join(members))


async def test_choices_made_before_a_promote_are_still_redacted(workspace, monkeypatch):
    ring(monkeypatch, RING_A)
    people = await people_form(workspace)
    for name in ("Alice", "Bob"):
        await submit(workspace, people, {"name": text_answer(name)})
    ids_a = await option_ids(workspace, people)
    consumers = await consumer_form(workspace, people)
    await submit(workspace, consumers, {"who": choice(ids_a["Alice"])})
    await submit(workspace, consumers, {"who": choice(ids_a["Bob"])})
    # add_key, then promote: the new key is now the primary
    ring(monkeypatch, RING_B, RING_A)
    sources()._cache.clear()
    ids_b = await option_ids(workspace, people)
    assert ids_b["Alice"] != ids_a["Alice"]
    alice = await response_of(workspace, people, "Alice")
    await container.form_response_service().delete_form_response(
        people.form_id, alice.response_id, workspace.id
    )
    [note] = await container.option_erasure_repo().pending(10)
    assert set(note.option_ids) == {ids_a["Alice"], ids_b["Alice"]}
    counts = await sources().redact_erased()
    assert counts["redacted"] == 1
    assert snapshots(await stored_answers(workspace, consumers)) == [
        "Bob",
        erasure.REMOVED_LABEL,
    ]


async def test_an_option_another_response_still_offers_is_not_redacted_after_a_promote(
    workspace, monkeypatch
):
    ring(monkeypatch, RING_A)
    people = await people_form(workspace)
    await submit(workspace, people, {"name": text_answer("Alice")}, user=testUser)
    await submit(workspace, people, {"name": text_answer("alice ")}, user=testUser1)
    ids_a = await option_ids(workspace, people)
    consumers = await consumer_form(workspace, people)
    await submit(workspace, consumers, {"who": choice(ids_a["Alice"])})
    ring(monkeypatch, RING_B, RING_A)
    sources()._cache.clear()
    first = await response_of(workspace, people, "Alice")
    await container.form_response_service().delete_form_response(
        people.form_id, first.response_id, workspace.id
    )
    counts = await sources().redact_erased()
    assert counts["redacted"] == 0
    assert snapshots(await stored_answers(workspace, consumers)) == ["Alice"]


async def test_consuming_forms_are_found_past_one_page_and_only_in_the_workspace(
    workspace, workspace_1
):
    people = await people_form(workspace)
    mine = [
        await consumer_form(workspace, people, title=f"Mine {n}") for n in range(3)
    ]
    other_people = await people_form(workspace_1)
    elsewhere = await consumer_form(workspace_1, people, title="Elsewhere")
    repo = container.form_repo()
    drafts, versions = await repo.documents_naming_source(
        people.form_id, workspace.id, page_size=2
    )
    found = {str(d.form_id) for d in drafts}
    assert found == {str(f.form_id) for f in mine}
    assert {str(v.form_id) for v in versions} == found
    # without a workspace every match is returned (also across the page size)
    drafts, _ = await repo.documents_naming_source(people.form_id, None, page_size=2)
    assert {str(f.form_id) for f in mine} | {str(elsewhere.form_id)} <= {
        str(d.form_id) for d in drafts
    }
    assert other_people is not None
