"""Deep pages of the staff responses list stay cheap: the page query seeks on
the sort index and skips a few rows, whatever its depth.

Seeds ``RESPONSES_PERF_ROWS`` responses (30,000 by default, to keep the suite
quick; run with ``RESPONSES_PERF_ROWS=300000 pytest -s`` for the measurement in
the pull request) for one form, then checks, for each way of reaching a page,
that EXPLAIN shows an index scan on the list index with no sort, and prints
the timings. The time assertions are generous (they catch a walk of the whole
table, not noise); the plan assertions are exact.
"""

import datetime as dt
import json
import os
import statistics
import time

import pytest
from sqlalchemy import event, text

from backend.app.container import container
from backend.app.models.filter_queries.response_list import (
    ResponseListFilters,
    ResponseListQuery,
)
from backend.app.services import response_cursor
from backend.app.services.response_cursor import Anchor

ROWS = int(os.getenv("RESPONSES_PERF_ROWS", "30000"))
ORDERED_INDEXES = {
    "ix_form_responses_list_submitted",
    "ix_form_responses_form_created",
    "ix_form_responses_workspace_form_created",
}
BASE = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)

SEED = text("""
    INSERT INTO app.form_responses (id, created_at, updated_at, doc, _bc_checksum)
    SELECT
      lpad(to_hex(g), 24, '0'),
      cast(:base as timestamptz) + (g / 3) * interval '7 seconds',   -- three rows share each time
      cast(:base as timestamptz) + (g / 3) * interval '7 seconds',
      jsonb_strip_nulls(jsonb_build_object(
        '_id', jsonb_build_object('$oid', lpad(to_hex(g), 24, '0')),
        'form_id', cast(:form_id as text),
        'workspace_id', cast(:workspace_id as text),
        'response_id', 'r' || g,
        'provider', 'self',
        'form_version', 1 + (g % 3),
        'dataOwnerIdentifier',
          CASE WHEN g % 2 = 0 THEN 'user' || g || '@example.com' END,
        'answers', 'ciphertext'
      )),
      'x'
    FROM generate_series(1, cast(:rows as int)) AS g
    """)


@pytest.fixture()
async def big_form(workspace, published_form):
    engine = container.pg_engine()
    async with engine.begin() as connection:
        await connection.execute(
            SEED,
            {
                "base": BASE,
                "form_id": published_form.form_id,
                "workspace_id": str(workspace.id),
                "rows": ROWS,
            },
        )
    async with engine.connect() as connection:
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        for name in filter(None, os.getenv("RESPONSES_PERF_DROP", "").split(",")):
            await connection.execute(text(f"DROP INDEX IF EXISTS app.{name}"))
        await connection.execute(text("ANALYZE app.form_responses"))
    return workspace, published_form.form_id


class Captured:
    def __init__(self, engine):
        self.statements = []
        self._engine = engine.sync_engine

        def before(conn, cursor, statement, parameters, context, executemany):
            self.statements.append((statement, parameters))

        self._hook = before

    def __enter__(self):
        event.listen(self._engine, "before_cursor_execute", self._hook)
        return self

    def __exit__(self, *exc):
        event.remove(self._engine, "before_cursor_execute", self._hook)


def nodes(plan):
    """The plan's nodes without the SubPlans (the per-row status lookup of the
    page's own rows, which sorts its one-row answer)."""
    yield plan
    for child in plan.get("Plans", []):
        if child.get("Parent Relationship") != "SubPlan":
            yield from nodes(child)


async def explain(statement, parameters):
    async with container.pg_engine().connect() as connection:
        raw = await connection.exec_driver_sql(
            "EXPLAIN (ANALYZE, FORMAT JSON) " + statement, parameters
        )
        data = raw.scalar_one()
    if isinstance(data, str):
        data = json.loads(data)
    return data[0]["Plan"], data[0]["Execution Time"]


async def page_and_plan(scope, query, anchor=None):
    repo = container.form_response_repo()
    with Captured(container.pg_engine()) as captured:
        started = time.perf_counter()
        listed = await repo.list_form_page(scope, query, anchor)
        elapsed = (time.perf_counter() - started) * 1000
    page_sql = [
        (s, p)
        for s, p in captured.statements
        if "ORDER BY" in s and "count(*)" not in s.lower()
    ]
    count_sql = [(s, p) for s, p in captured.statements if "count(*)" in s.lower()]
    return listed, elapsed, page_sql, count_sql


def assert_uses_index(plan, label, max_rows_read=2000):
    kinds = [n["Node Type"] for n in nodes(plan)]
    scans = [
        n
        for n in nodes(plan)
        if n["Node Type"] in ("Index Scan", "Index Only Scan", "Bitmap Index Scan")
        and n.get("Index Name") in ORDERED_INDEXES
    ]
    assert scans, f"{label}: no index scan on a created_at index: {kinds}"
    assert (
        "Sort" not in kinds
    ), f"{label}: the page is sorted, not read in order: {kinds}"
    read = sum(
        n.get("Actual Rows", 0) * max(n.get("Actual Loops", 1), 1) for n in scans
    )
    assert read <= max_rows_read, f"{label}: read {read} index rows"


async def scope_of(workspace, form_id):
    from tests.app.response_helpers import form_scope

    return await form_scope(form_id, workspace.id)


async def test_every_way_of_reaching_a_page_is_an_ordered_index_scan(big_form, capsys):
    workspace, form_id = big_form
    scope = await scope_of(workspace, form_id)
    size = 25
    report = []

    async def measure(label, query, anchor=None, expect_total=None, max_rows=2000):
        listed, _, sql, counted = await page_and_plan(scope, query, anchor)
        times = []
        for _ in range(5):
            _, ms, _, _ = await page_and_plan(scope, query, anchor)
            times.append(ms)
        plan, db_ms = await explain(*sql[-1])
        assert_uses_index(plan, label, max_rows)
        count_plan, count_ms = await explain(*counted[-1])
        report.append(
            (
                label,
                statistics.median(times),
                db_ms,
                count_ms,
                listed.total,
                len(listed.items),
            )
        )
        if expect_total is not None:
            assert listed.total == expect_total, label
        return listed

    def query(page, **kw):
        filters = kw.pop("filters", ResponseListFilters())
        return ResponseListQuery(filters=filters, page=page, size=size, **kw)

    first = await measure("page 1, newest first", query(1))
    assert len(first.items) == size and first.has_next
    # stand on a deep page: its first row is the cursor's anchor (read the way
    # a client would have got it, by walking there; here by one skip)
    deep_page = 1000 if ROWS >= 25_000 else 100
    async with container.pg_engine().connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT created_at, id FROM app.form_responses "
                    "WHERE workspace_id = :w AND form_id = :f "
                    "ORDER BY created_at DESC, id DESC OFFSET :o LIMIT 1"
                ),
                {"w": str(workspace.id), "f": form_id, "o": (deep_page - 1) * size},
            )
        ).one()
    anchor = Anchor(page=deep_page, version=None, created_at=row[0], row_id=row[1])
    for label, page in (
        ("next page by cursor", deep_page + 1),
        ("previous page by cursor", deep_page - 1),
        ("page +5 by cursor", deep_page + 5),
        ("page -5 by cursor", deep_page - 5),
    ):
        listed = await measure(f"{label} (depth {deep_page})", query(page), anchor)
        assert listed.items, label
    if ROWS >= 100_000:  # on a small table the planner may rightly prefer a scan
        await measure(
            "page 400 from the start (skips 9,975 rows)", query(400), max_rows=10_100
        )
    # the last page and one near it: an ordered scan from the end
    pages = -(-min(ROWS, 10_000) // size)
    if ROWS <= 10_000:
        await measure("last page (from the end)", query(pages))
    # filters on the range, the version, anonymous, status
    middle = BASE + dt.timedelta(seconds=7 * (ROWS // 6))
    await measure(
        "date range, page 1",
        query(
            1,
            filters=ResponseListFilters(
                submitted_from=middle, submitted_to=middle + dt.timedelta(days=2)
            ),
        ),
    )
    await measure(
        "date range, ascending",
        query(
            1,
            descending=False,
            filters=ResponseListFilters(submitted_from=middle),
        ),
    )
    await measure(
        "anonymous, page 1",
        query(1, filters=ResponseListFilters(respondent="anonymous")),
    )
    await measure(
        "form version 2, page 1",
        query(1, filters=ResponseListFilters(form_version=(2,))),
    )

    # the worst case of a filter: one that matches (almost) nothing makes the
    # database read the form once, for the page and for the count; no index
    # order helps, so this is reported, not required to use one
    repo = container.form_response_repo()
    started = time.perf_counter()
    nothing = await repo.list_form_page(
        scope, query(1, filters=ResponseListFilters(form_version=(99,)))
    )
    worst = (time.perf_counter() - started) * 1000
    assert nothing.items == [] and nothing.total == 0

    with capsys.disabled():
        print(f"\nresponses list, {ROWS:,} rows, page size {size} (ms)")
        print(
            f"{'case':46} {'e2e':>7} {'page sql':>9} {'count sql':>10} {'total':>8} {'rows':>5}"
        )
        for label, e2e, db_ms, count_ms, total, rows in report:
            print(
                f"{label:46} {e2e:7.1f} {db_ms:9.2f} {count_ms:10.2f} {total:8d} {rows:5d}"
            )
        print(f"{'filter that matches nothing (reads the form)':46} {worst:7.1f}")
    for label, e2e, *_ in report:
        assert e2e < 1500, f"{label}: {e2e:.0f} ms"
    assert worst < 5000


async def test_the_version_sort_uses_its_own_index(big_form, capsys):
    workspace, form_id = big_form
    scope = await scope_of(workspace, form_id)
    for descending in (True, False):
        query = ResponseListQuery(
            page=1, size=25, sort_by="form_version", descending=descending
        )
        _, ms, sql, _ = await page_and_plan(scope, query)
        plan, db_ms = await explain(*sql[-1])
        names = {n.get("Index Name") for n in nodes(plan)}
        kinds = [n["Node Type"] for n in nodes(plan)]
        with capsys.disabled():
            print(
                f"\nsort by version, descending={descending}: {ms:.1f} ms, page sql {db_ms:.2f} ms, {names}"
            )
        assert "ix_form_responses_list_version" in names, names
        assert "Sort" not in kinds, kinds


async def test_a_deep_offset_without_a_cursor_for_contrast(big_form, capsys):
    """What the old list does at depth, for the pull request's numbers."""
    workspace, form_id = big_form
    scope = await scope_of(workspace, form_id)
    repo = container.form_response_repo()
    from backend.app.models.filter_queries.sort import SortRequest
    from fastapi_pagination import Params, set_page, set_params
    from fastapi_pagination.default import Page

    page = max(1, (ROWS // 2) // 25)
    set_page(Page)
    set_params(Params(page=page, size=25))
    started = time.perf_counter()
    await repo.get_form_responses(scope, sort=SortRequest())
    old_ms = (time.perf_counter() - started) * 1000
    with capsys.disabled():
        print(f"\nold offset list, page {page} of {ROWS // 25}: {old_ms:.0f} ms")
