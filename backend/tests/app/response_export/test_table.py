"""The export's columns and cells, pinned with what the browser's builder
(``webapp/src/utils/response-export.ts``, since removed) wrote for the same
form and responses: ``fixtures/response_export/golden_expected.json`` is its
output for ``golden_input.json``."""

import datetime as dt
import io
import json
import zipfile
from pathlib import Path
from typing import List

import pytest

from backend.app.services.response_export.table import (
    UnknownColumn,
    build_plan,
    column_catalogue,
    csv_line,
    export_file_name,
    formula_safe_cell,
    number_text,
    submitted_at_cell,
)
from backend.app.services.response_export.writer import (
    BOM,
    RowCount,
    table_file_names,
    write_export,
)
from backend.app.services.response_export.service import to_export_response  # noqa: F401
from backend.app.services.response_export.table import ExportResponse

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "response_export"
GIVEN = json.loads((FIXTURES / "golden_input.json").read_text(encoding="utf-8"))
EXPECTED = json.loads((FIXTURES / "golden_expected.json").read_text(encoding="utf-8"))


def parse_time(value):
    if not value:
        return None
    moment = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return moment


def responses() -> List[ExportResponse]:
    return [
        ExportResponse(
            response_id=r.get("response_id"),
            responder=r.get("dataOwnerIdentifier"),
            created_at=parse_time(r.get("created_at")),
            answers=r.get("answers", {}),
            internal_answers=r.get("internal_answers", {}),
            hidden_fields=r.get("hidden_fields", {}),
        )
        for r in GIVEN["responses"]
    ]


def source_of(items):
    async def source():
        for item in items:
            yield item

    return source


async def collect(plan, items=None, title="Survey") -> bytes:
    counter = RowCount()
    out = b""
    async for piece in write_export(plan, title, source_of(items or responses()), counter):
        out += piece
    return out


@pytest.mark.asyncio
async def test_the_main_table_is_what_the_browser_wrote():
    plan = build_plan(GIVEN["form"])
    zipped = await collect(plan, title=GIVEN["form"]["title"])
    archive = zipfile.ZipFile(io.BytesIO(zipped))
    names = archive.namelist()
    assert names == [EXPECTED["fileName"], *EXPECTED["groupFileName"]]
    main = archive.read(names[0]).decode("utf-8")
    assert main.startswith(BOM)
    assert main.removeprefix(BOM) == EXPECTED["main"]


@pytest.mark.asyncio
async def test_each_group_table_is_what_the_browser_wrote():
    plan = build_plan(GIVEN["form"])
    zipped = await collect(plan, title=GIVEN["form"]["title"])
    archive = zipfile.ZipFile(io.BytesIO(zipped))
    for name, table in zip(archive.namelist()[1:], EXPECTED["groups"]):
        assert archive.read(name).decode("utf-8").removeprefix(BOM) == EXPECTED["groups"][table]


@pytest.mark.asyncio
async def test_without_a_group_table_the_export_is_one_csv():
    form = json.loads(json.dumps(GIVEN["form"]))
    for slide in form["fields"]:
        fields = (slide.get("properties") or {}).get("fields")
        if fields:
            fields[:] = [f for f in fields if f["id"] != "jobs"]
    plan = build_plan(form)
    assert plan.group_tables == []
    data = await collect(plan)
    assert data.decode("utf-8").startswith(BOM + "Responder ID,")
    assert not data.startswith(b"PK")


def test_the_file_name_follows_the_form_title():
    assert export_file_name(GIVEN["form"]["title"]) == EXPECTED["fileName"]
    assert export_file_name("", extension="zip") == "export.zip"
    assert export_file_name("a/b\\c", "d:e") == "a b c - d e.csv"
    assert export_file_name("x\x00y\ny") == "x y y.csv"


@pytest.mark.asyncio
async def test_two_tables_with_one_name_get_two_file_names():
    plan = build_plan(GIVEN["form"])
    plan.group_tables.append(plan.group_tables[0])
    names = table_file_names("T", plan)
    assert len(set(names)) == len(names) == 3


# ------------------------------------------------------------- chosen columns


def test_every_column_has_a_stable_key():
    catalogue = column_catalogue(GIVEN["form"])
    keys = [c["key"] for c in catalogue]
    assert keys[0] == "responder"
    assert keys[-5:] == [
        "response_id",
        "submitted_at",
        "hidden:utm_source",
        "hidden:ref",
        "hidden:constructor",
    ]
    assert "q:name" in keys and "internal:ref" in keys and "q:kids" in keys
    assert len(set(keys)) == len(keys)
    assert {c["kind"] for c in catalogue} == {"responder", "question", "internal", "meta", "hidden"}


@pytest.mark.asyncio
async def test_chosen_columns_keep_the_usual_order():
    plan = build_plan(GIVEN["form"], ["submitted_at", "q:phone", "q:name"])
    assert plan.headers == ["Name Page 1", "Phone", "Submitted at (UTC, ISO 8601)"]
    data = (await collect(plan)).decode("utf-8").removeprefix(BOM)
    first = data.split("\r\n")[1]
    assert first.startswith("\"Sita, \"\"the\"\" first")


def test_a_group_table_brings_the_response_id_it_joins_on():
    plan = build_plan(GIVEN["form"], ["q:jobs"])
    assert plan.headers == ["Jobs (Job count)", "Response ID (2)"]
    assert [t.name for t in plan.group_tables] == ["Jobs"]
    # chosen without it, the table is not part of the export
    assert build_plan(GIVEN["form"], ["q:name"]).group_tables == []


def test_an_unknown_column_is_refused():
    with pytest.raises(UnknownColumn):
        build_plan(GIVEN["form"], ["q:name", "q:nope"])
    with pytest.raises(UnknownColumn):
        build_plan(GIVEN["form"], ["hidden:undeclared"])


# ----------------------------------------------------------------- the guard


KEPT = ["-12.5", "-3", "-0", "-10.25", "plain", "", "a=b", "1+1", "2026-10-01T10:00:00Z", "(020) 123-4567", "020 123 4567", "31612345678"]
PREFIXED = [
    "-2+3+cmd|' /C calc'!A0", '+HYPERLINK("http://x","y")', "=SUM(1)", "=1+1", "@x", "@SUM(A1)", "\tx",
    "\r=1", "\t", "\r", "-", "+", "-abc", "+1+cmd", "-1;=1", "-1-1", "-1.", "-.5", "-1.2.3", "-1e5", "-1\n",
    "-1 ", "- 1", "+1\n=1", "+31 6 1234 5678", "+31612345678", "+31-6-1234-5678", "+1 (555) 123-4567", "+12.5",
    "-1|2", "-١٢", " =1", "  +1", "\n=1", " \n-cmd", " @x", " =1", "﻿+1", " -x",
]


@pytest.mark.parametrize("value", KEPT)
def test_a_plain_value_is_left_alone(value):
    assert formula_safe_cell(value) == value


@pytest.mark.parametrize("value", PREFIXED)
def test_a_formula_like_value_gets_a_leading_apostrophe(value):
    assert formula_safe_cell(value) == "'" + value


def test_numbers_are_left_alone():
    assert formula_safe_cell(-5) == -5 and formula_safe_cell(0) == 0 and formula_safe_cell(-2.5) == -2.5


def test_headers_and_every_cell_of_a_line_are_guarded():
    assert csv_line(["=cmd", "+31", "Hidden: =cmd"]) == "'=cmd,'+31,Hidden: =cmd"
    assert csv_line(["a,b", 'q"q', "x\ny", 5, 2.5, None]) == '"a,b","q""q","x\ny",5,2.5,'


def test_numbers_print_like_javascript():
    assert [number_text(v) for v in (5, 5.0, 2.5, -3.0, 1e21, 0.1)] == ["5", "5", "2.5", "-3", "1e+21", "0.1"]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-10-01T10:00:00Z", "2026-10-01T10:00:00Z"),
        ("2026-10-01T10:00:00.123456", "2026-10-01T10:00:00Z"),
        ("2026-10-01T12:00:00+02:00", "2026-10-01T10:00:00Z"),
        (None, ""),
    ],
)
def test_the_submission_time_is_utc_iso(value, expected):
    moment = None if value is None else dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert submitted_at_cell(moment) == expected
    assert submitted_at_cell("not a date") == ""  # type: ignore[arg-type]
