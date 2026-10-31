"""Time, day and currency answers in the export: HH:MM, YYYY-MM-DD and
"EUR 12.50" (the code, a space, a dot decimal), the same in every language and
in a repeating group's items. The expected text is what the browser's export
wrote for the same data before the export moved to the server."""

import io
import json
import zipfile

import pytest

from backend.app.services.response_export.table import (
    ExportResponse,
    answer_value,
    build_plan,
)
from backend.app.services.response_export.writer import BOM, RowCount, write_export

FORM = {
    "form_id": "typed",
    "builder_version": "v2",
    "title": "Typed",
    "fields": [
        {
            "id": "p1",
            "index": 0,
            "type": "slide",
            "properties": {
                "fields": [
                    {"id": "arrival", "index": 0, "type": "time", "title": "Arrival"},
                    {"id": "born", "index": 1, "type": "day", "title": "Born"},
                    {
                        "id": "budget",
                        "index": 2,
                        "type": "currency",
                        "title": "Budget",
                        "properties": {"currencies": ["EUR", "GBP"]},
                    },
                ]
            },
        }
    ],
}


def _response(response_id, answers):
    return ExportResponse(
        response_id=response_id,
        responder="a@example.org",
        created_at=None,
        answers=answers,
        internal_answers={},
        hidden_fields={},
    )


async def _csv(*responses):
    async def source():
        for item in responses:
            yield item

    out = b""
    async for piece in write_export(build_plan(FORM), "Typed", source, RowCount()):
        out += piece
    return out.decode("utf-8").removeprefix(BOM).split("\r\n")


@pytest.mark.asyncio
async def test_a_time_a_day_and_an_amount_are_written_the_same_in_every_language():
    lines = await _csv(
        _response(
            "r1",
            {
                "arrival": {"type": "time", "time": "09:05"},
                "born": {"type": "date", "date": "1990-11-05"},
                "budget": {
                    "type": "currency",
                    "currency": {"code": "GBP", "amount": "1250.50"},
                },
            },
        )
    )
    assert lines[0].startswith("Responder ID,Arrival,Born,Budget,")
    assert lines[1].startswith("a@example.org,09:05,1990-11-05,GBP 1250.50,")


@pytest.mark.asyncio
async def test_unanswered_questions_leave_their_cells_empty():
    lines = await _csv(_response("r2", {}))
    assert lines[1].startswith("a@example.org,,,,")


@pytest.mark.asyncio
async def test_a_half_typed_or_impossible_day_is_written_as_typed():
    lines = await _csv(
        _response("r3", {"born": {"type": "date", "date": "2026-02-31"}})
    )
    assert lines[1].startswith("a@example.org,,2026-02-31,,")


def test_an_amount_without_a_code_or_without_an_amount():
    budget = FORM["fields"][0]["properties"]["fields"][2]
    assert answer_value({"budget": {"currency": {"code": "EUR", "amount": ""}}}, budget) == ""
    assert answer_value({"budget": {"currency": {"amount": "3"}}}, budget) == "3"
    assert answer_value({"budget": {}}, budget) == ""
    assert answer_value({"budget": {"currency": {"code": "EUR", "amount": "3"}}}, budget) == "EUR 3"
