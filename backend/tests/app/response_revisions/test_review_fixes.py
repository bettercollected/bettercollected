"""Review fixes of the revision log: which version staff are judged against,
the sealing context, the limit counting staff only, and erased shared answers
leaving the history too."""

import json

import pytest

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.repositories.postgres import responses as responses_module
from backend.app.schemas.response_revision import RevisionEditor, seal_context
from backend.config import settings
from common.services.crypto_service import UnreadableCiphertext, crypto_service
from tests.app.controllers.data import testUser
from tests.app.response_revisions.helpers import (
    NAME,
    RESPONDENT,
    answers_url,
    cookies,
    published_form,
    question,
    respondent_edit,
    revision_rows,
    revisions_url,
    stored_answers,
    submit,
    text,
)

pytestmark = pytest.mark.asyncio


async def staff_patch(client, workspace, form, response, answers):
    return await client.patch(
        answers_url(workspace, form, response),
        json={"answers": answers},
        cookies=cookies(testUser),
    )


async def set_form_version(response, version):
    """Store what an older response (or a forged page) carried."""
    repo = container.form_response_repo()
    stored = await repo.get_response(response.response_id)
    stored.form_version = version
    await repo.upsert(stored)


class TestVersionStaffAreJudgedAgainst:
    async def test_a_question_that_became_a_signature_stays_locked(
        self, client, workspace, monkeypatch
    ):
        monkeypatch.setattr(settings, "SIGNATURE_QUESTION_ENABLED", True)
        form = await published_form(workspace, [NAME, question("mark", title="Mark")])
        response = await submit(workspace, form, {"name": text("Ada"), "mark": text("x")})
        # version 2: the same id is now a signature
        service = container.workspace_form_service()
        from common.models.standard_form import StandardForm

        draft = await container.form_service().get_form_document_by_id(str(form.form_id))
        newer = StandardForm(**draft.model_dump())
        sig = [f for f in newer.fields[0].properties.fields if f.id == "mark"][0]
        sig.type = "signature"
        await service.update_form(workspace.id, form.form_id, newer, testUser)
        await service.publish_form(workspace.id, form.form_id, testUser)
        assert (await container.form_repo().get_latest_version_of_form(form.form_id)).version == 2
        # the response says it was given in version 1, where "mark" was text
        await set_form_version(response, 1)
        refused = await staff_patch(client, workspace, form, response, {"mark": text("over")})
        assert refused.status_code == 422, refused.text
        assert refused.json()["code"] == "question_not_editable"
        assert refused.json()["questionIds"] == ["mark"]
        assert (await stored_answers(workspace, response))["mark"]["text"] == "x"

    async def test_a_question_that_was_a_signature_in_the_responses_version_stays_locked(
        self, client, workspace, monkeypatch
    ):
        monkeypatch.setattr(settings, "SIGNATURE_QUESTION_ENABLED", True)
        form = await published_form(
            workspace, [NAME, question("mark", "signature", title="Sign")]
        )
        response = await submit(
            workspace,
            form,
            {
                "name": text("Ada"),
                "mark": {"type": "signature", "signature": {"method": "typed", "name": "Ada Lovelace"}},
            },
        )
        service = container.workspace_form_service()
        from common.models.standard_form import StandardForm

        draft = await container.form_service().get_form_document_by_id(str(form.form_id))
        newer = StandardForm(**draft.model_dump())
        newer.fields[0].properties.fields = [
            f if f.id != "mark" else question_as_text(f) for f in newer.fields[0].properties.fields
        ]
        await service.update_form(workspace.id, form.form_id, newer, testUser)
        await service.publish_form(workspace.id, form.form_id, testUser)
        refused = await staff_patch(client, workspace, form, response, {"mark": text("over")})
        assert refused.status_code == 422
        assert refused.json()["questionIds"] == ["mark"]

    async def test_a_version_beyond_the_latest_is_not_believed(self, client, workspace):
        form = await published_form(workspace, [NAME, question("city", title="City")])
        response = await submit(workspace, form, {"name": text("Ada"), "city": text("Leiden")})
        await set_form_version(response, 99)
        # judged against the latest: the edit is checked, and works
        ok = await staff_patch(client, workspace, form, response, {"city": text("Delft")})
        assert ok.status_code == 200 and ok.json()["changed"] == ["city"]
        bad = await staff_patch(client, workspace, form, response, {"name": text("")})
        assert bad.status_code == 422

    async def test_a_submission_cannot_choose_its_version(self, client, workspace):
        form = await published_form(workspace)
        service = container.workspace_form_service()
        sent = await service.submit_response(
            workspace.id,
            form.form_id,
            StandardFormResponseCamelModel(answers={"name": text("Ada")}, form_version=77),
            RESPONDENT,
        )
        stored = await container.form_response_repo().get_response(sent.response_id)
        assert stored.form_version == 1


def question_as_text(field):
    field.type = "short_text"
    return field


class TestSealingContext:
    async def test_an_entry_copied_onto_another_response_does_not_open(
        self, client, workspace
    ):
        form = await published_form(workspace)
        one = await submit(workspace, form, {"name": text("Ada")})
        two = await submit(workspace, form, {"name": text("Bo")})
        for response in (one, two):
            await respondent_edit(workspace, form, response, {"name": text("Changed")})
        [first] = await revision_rows(one)
        [second] = await revision_rows(two)
        # the previous values of the second response, put on the first (a bad fix, a script)
        repo = container.response_revision_repo()
        first.previous_values = second.previous_values
        await repo.upsert(first)
        got = await client.get(revisions_url(workspace, form, one, 1), cookies=cookies(testUser))
        assert got.status_code == 409, got.text
        assert "Bo" not in got.text
        # the second still opens, and shows its own
        own = await client.get(revisions_url(workspace, form, two, 1), cookies=cookies(testUser))
        assert own.json()["values"]["name"]["text"] == "Bo"

    async def test_the_number_is_part_of_the_binding(self, workspace):
        form = await published_form(workspace)
        response = await submit(workspace, form, {"name": text("Ada")})
        await respondent_edit(workspace, form, response, {"name": text("B")})
        await respondent_edit(workspace, form, response, {"name": text("C")})
        first, second = await revision_rows(response)
        for entry, wrong in ((first, second.seq), (second, first.seq)):
            with pytest.raises(UnreadableCiphertext):
                crypto_service.decrypt(
                    workspace_id=workspace.id,
                    form_id=str(form.form_id),
                    data=bytes(entry.previous_values),
                    context=seal_context(entry.response_pk, wrong),
                )
        crypto_service.decrypt(
            workspace_id=workspace.id,
            form_id=str(form.form_id),
            data=bytes(first.previous_values),
            context=seal_context(first.response_pk, first.seq),
        )


class TestLimitCountsStaffOnly:
    async def test_a_respondents_own_edit_is_never_refused_for_the_limit(
        self, client, workspace, monkeypatch
    ):
        monkeypatch.setattr(responses_module, "MAX_REVISIONS", 2)
        form = await published_form(workspace)
        response = await submit(workspace, form, {"name": text("Ada")})
        for value in ("a", "b"):
            assert (await staff_patch(client, workspace, form, response, {"name": text(value)})).status_code == 200
        refused = await staff_patch(client, workspace, form, response, {"name": text("c")})
        assert refused.status_code == 409 and refused.json()["code"] == "revision_limit"
        # the data subject can still correct their answer, and it is recorded
        await respondent_edit(workspace, form, response, {"name": text("mine")})
        await respondent_edit(workspace, form, response, {"name": text("mine again")})
        assert (await stored_answers(workspace, response))["name"]["text"] == "mine again"
        entries = await revision_rows(response)
        assert [(e.seq, e.actor_kind.value) for e in entries] == [
            (1, "staff"),
            (2, "staff"),
            (3, "respondent"),
            (4, "respondent"),
        ]
        # staff stay refused
        assert (await staff_patch(client, workspace, form, response, {"name": text("d")})).status_code == 409

    async def test_respondent_entries_do_not_use_up_the_staff_limit(
        self, client, workspace, monkeypatch
    ):
        monkeypatch.setattr(responses_module, "MAX_REVISIONS", 2)
        form = await published_form(workspace)
        response = await submit(workspace, form, {"name": text("Ada")})
        for value in ("a", "b", "c"):
            await respondent_edit(workspace, form, response, {"name": text(value)})
        assert (await staff_patch(client, workspace, form, response, {"name": text("s")})).status_code == 200


class TestErasedSharedAnswersLeaveTheHistoryToo:
    async def test_the_label_snapshot_in_previous_values_is_redacted(
        self, workspace, monkeypatch
    ):
        from backend.app.services.option_sources import erasure
        from tests.app.option_sources.helpers import choice, publish, question as sq, submit as osubmit, text as otext

        monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", True)
        sources = container.option_source_service()
        sources._auto_redact = False
        people = await publish(
            workspace, [sq("name", "short_text", "Name", share_as_choices=True)], title="People"
        )
        for name in ("Alice", "Bob"):
            await osubmit(workspace, people, {"name": otext(name)})
        built = await sources.options(
            workspace.id,
            {"kind": "form_answers", "form_id": people.form_id, "question_id": "name"},
        )
        ids = {o.label: o.id for o in built.options}
        consumers = await publish(
            workspace,
            [
                sq(
                    "who",
                    "dropdown",
                    "Who",
                    source={"kind": "form_answers", "form_id": people.form_id, "question_id": "name"},
                )
            ],
            title="Who comes",
        )
        sent = await osubmit(workspace, consumers, {"who": choice(ids["Alice"])})
        # the consumer's answer is changed to Bob: the history holds the Alice snapshot
        repo = container.form_response_repo()
        stored = await repo.get_response(sent.response_id)
        await repo.patch_form_response(
            form_id=consumers.form_id,
            document_id=stored.id,
            response=StandardFormResponseCamelModel(answers={"who": choice(ids["Bob"])}),
            workspace_id=workspace.id,
            editor=RevisionEditor(user_id=str(testUser.id), role="OWNER"),
            record=True,
        )
        [entry] = await container.response_revision_repo().list_for_response(stored.id)

        def open_previous(item):
            return json.loads(
                crypto_service.decrypt(
                    workspace_id=workspace.id,
                    form_id=str(consumers.form_id),
                    data=bytes(item.previous_values),
                    context=seal_context(item.response_pk, item.seq),
                )
            )

        assert open_previous(entry)["who"]["choice"]["label"] == "Alice"
        # Alice's own response is erased: the choices made from it are redacted
        scope = await container.form_response_service().scope(workspace.id, [people.form_id])
        alice = None
        for row in await repo.list_by_form_id(scope):
            decrypted = container.form_response_service().decrypt_form_response(
                workspace_id=workspace.id, response=row.model_copy(deep=True)
            )
            if decrypted.answers["name"]["text"] == "Alice":
                alice = row
        await container.form_response_service().delete_form_response(
            people.form_id, alice.response_id, workspace.id
        )
        counts = await sources.redact_erased()
        assert counts["failed"] == 0
        [after] = await container.response_revision_repo().list_for_response(stored.id)
        label = open_previous(after)["who"]["choice"]["label"]
        assert label == erasure.REMOVED_LABEL
        assert "Alice" not in json.dumps(open_previous(after))
