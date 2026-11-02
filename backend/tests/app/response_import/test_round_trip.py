"""Export -> import: what the export writes, an import reads back, for every
question type the export writes, as stored answers equal to the originals."""

import csv
import io

import pytest
from common.models.standard_form import StandardFormResponseAnswer  # noqa: F401
from httpx import AsyncClient

from backend.app.container import container

from tests.app.controllers.data import testUser
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.response_export.helpers import start as start_export
from tests.app.response_import.helpers import (
    ADA,
    ALL_FIELDS,
    import_all,
    publish_form,
    stored_answers,
    submit,
)

pytestmark = pytest.mark.asyncio


def plain(value):
    """An answer as plain data without the empty slots the model adds."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items() if v is not None and v != [] and v != {}}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


def comparable(answers):
    """Answers without what a submission stamps itself (the signing time) and
    the question reference."""
    out = {}
    for key, answer in (answers or {}).items():
        answer = plain(answer)
        answer.pop("field", None)
        if "signature" in answer:
            answer["signature"].pop("signed_at", None)
        for item in answer.get("items", []) or []:
            for child in item.values():
                child.pop("field", None)
        out[key] = answer
    return out


async def export_csv(client, workspace, form):
    response = await start_export(client, workspace, form)
    assert response.status_code == 200, response.text
    return response.content


async def test_every_exported_question_type_reads_back_equal(client: AsyncClient, workspace):
    source = await publish_form(workspace, ALL_FIELDS, hidden=["utm_source"], title="Source")
    sent = await submit(workspace, source, ADA, hidden={"utm_source": "mail"})
    # internal (staff) answers are written by the export too
    await container.form_response_service().update_internal_answers(
        workspace.id,
        source.form_id,
        sent.response_id,
        {
            "note": {"type": "text", "text": "Call back on Monday"},
            "score": {"type": "number", "number": 8},
        },
        testUser,
    )

    exported = await export_csv(client, workspace, source)
    target = await publish_form(workspace, ALL_FIELDS, hidden=["utm_source"], title="Target")

    body = await import_all(client, workspace, target, exported)
    assert body["status"] == "completed", body
    assert (body["rowsImported"], body["rowsSkipped"]) == (1, 0)
    assert body["problems"] == []

    original = (await stored_answers(workspace, source))[0]
    imported = (await stored_answers(workspace, target))[0]
    assert comparable(imported.answers) == comparable(original.answers)
    assert imported.hidden_fields == {"utm_source": "mail"}
    # the staff-only answers came along, recorded as entered by the importer
    assert comparable(imported.internal_answers) == comparable(original.internal_answers)
    assert comparable(imported.internal_answers)["note"]["text"] == "Call back on Monday"
    assert set(imported.internal_answers_meta) == {"note", "score"}
    assert all(m.updated_by == str(testUser.id) for m in imported.internal_answers_meta.values())
    assert imported.csv_import_id == body["id"]
    assert original.csv_import_id is None
    # no identity is taken from the file, the response is anonymous
    assert imported.dataOwnerIdentifier is None and imported.anonymous_identity is None
    # the submission time of the file is the response's
    assert imported.created_at == original.created_at.replace(microsecond=0)

    # and the second export of the imported form has the same cells (but its own ids)
    again = await export_csv(client, workspace, target)
    first_rows = list(csv.reader(io.StringIO(exported.decode().removeprefix("﻿"), newline="")))
    second_rows = list(csv.reader(io.StringIO(again.decode().removeprefix("﻿"), newline="")))
    anonymous = first_rows[0].index("Responder ID")
    for row in (first_rows[1], second_rows[1]):
        row[anonymous] = "-"
    head = first_rows[0]
    skip = {head.index("Response ID")}
    assert [c for i, c in enumerate(first_rows[1]) if i not in skip][:-1] == [c for i, c in enumerate(second_rows[1]) if i not in skip][:-1]
