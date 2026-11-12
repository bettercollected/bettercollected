"""The export reads a form in batches on a keyset of ``(created_at, id)``: each
batch seeks to where the last one ended on the index of ``(workspace, form,
created_at)``, so a batch costs its own rows and a pass over N responses reads N.
The output (rows and order) is what ``ORDER BY id`` gave.

Set ``EXPORT_BENCH_ROWS`` (a comma list, e.g. ``5000,20000``) to print the
before/after timings of the pull request::

    EXPORT_BENCH_ROWS=5000,20000 uv run pytest tests/app/response_export/test_export_keyset.py -s -k bench
"""

import os
import statistics
import time

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from backend.app.container import container
from backend.app.repositories.postgres.responses import ExportCursor
from backend.app.models.filter_queries.response_export import ResponseExportFilters
from backend.app.services.response_export import limits
from tests.app.repositories.test_responses_list_performance import (
    BASE,
    Captured,
    explain,
    nodes,
    ORDERED_INDEXES,
)
from backend.app.repositories.response_scope import ResponseScope
from tests.app.response_export.helpers import publish, start, submit_many
from tests.app.response_helpers import form_scope, unlinked_scope

pytestmark = pytest.mark.asyncio

async def sql(statement: str, **params):
    async with container.pg_engine().begin() as connection:
        result = await connection.execute(text(statement), params)
        return result.all() if result.returns_rows else []


async def walk(scope, filters=None, size=5):
    """Every id of the pass, in batches of ``size``, and the batch lengths."""
    repo = container.form_response_repo()
    ids, lengths, after = [], [], None
    while True:
        batch, after = await repo.export_batch(scope, filters, after=after, limit=size)
        if not batch:
            return ids, lengths
        lengths.append(len(batch))
        ids.extend(str(response.id) for response in batch)


async def stored_ids(form_id: str, where: str = "true") -> list:
    """What the previous query returned: the form's responses with answers, by id."""
    rows = await sql(
        "SELECT id FROM app.form_responses WHERE form_id = :form AND doc ? 'answers'"
        f" AND {where} ORDER BY id",
        form=form_id,
    )
    return [r[0] for r in rows]


async def form_of(workspace, count: int):
    form = await publish(workspace)
    await submit_many(workspace, form, count)
    return form


@pytest.mark.parametrize("size", [1, 5, 13, 500])
async def test_the_pass_returns_every_response_in_the_stored_order(workspace, size):
    form = await form_of(workspace, 13)
    scope = await form_scope(form.form_id, workspace.id)
    ids, lengths = await walk(scope, size=size)
    assert ids == await stored_ids(form.form_id)
    assert len(ids) == 13 and sum(lengths) == 13
    # every batch but the last is full: a short one ends the pass
    assert all(n == size for n in lengths[:-1])
    assert await container.form_response_repo().count_for_export(scope) == 13


async def test_the_file_is_the_same_whatever_the_batch_size(client: AsyncClient, workspace, monkeypatch):
    form = await form_of(workspace, 12)
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 100)
    whole = (await start(client, workspace, form)).content
    monkeypatch.setattr(limits, "BATCH_SIZE", 5)
    in_batches = (await start(client, workspace, form)).content
    assert whole == in_batches
    # a header and the twelve people, oldest first
    lines = whole.decode().removeprefix("﻿").splitlines()
    assert len(lines) == 13 and "Person 0" in lines[1] and "Person 11" in lines[-1]


async def test_a_filter_narrows_the_pass_without_changing_its_order(workspace):
    form = await form_of(workspace, 10)
    scope = await form_scope(form.form_id, workspace.id)
    rows = await sql("SELECT id, created_at FROM app.form_responses WHERE form_id = :f ORDER BY id", f=form.form_id)
    cut = rows[4][1]
    filters = ResponseExportFilters(submitted_from=cut)
    ids, _ = await walk(scope, filters, size=3)
    assert ids == await stored_ids(form.form_id, f"created_at >= '{cut.isoformat()}'")
    assert 0 < len(ids) < 10


async def test_responses_with_the_same_time_are_not_skipped_or_repeated(workspace):
    form = await form_of(workspace, 12)
    scope = await form_scope(form.form_id, workspace.id)
    # four to a time: a batch ends in the middle of each
    await sql(
        "UPDATE app.form_responses SET created_at = cast(:base as timestamptz) + (g.n / 4) * interval '1 minute'"
        " FROM (SELECT id, row_number() OVER (ORDER BY id) - 1 AS n FROM app.form_responses WHERE form_id = :f) g"
        " WHERE app.form_responses.id = g.id",
        base=BASE,
        f=form.form_id,
    )
    for size in (1, 3, 5):
        ids, _ = await walk(scope, size=size)
        assert ids == await stored_ids(form.form_id) and len(set(ids)) == 12


async def test_a_response_stored_before_workspaces_is_merged_by_the_same_key(workspace):
    form = await form_of(workspace, 12)
    # every third response is one stored before it carried a workspace
    await sql(
        "UPDATE app.form_responses SET doc = doc - 'workspace_id'"
        " WHERE form_id = :f AND id IN (SELECT id FROM (SELECT id, row_number() OVER (ORDER BY id) n"
        " FROM app.form_responses WHERE form_id = :f) x WHERE n % 3 = 0)",
        f=form.form_id,
    )
    scope = await form_scope(form.form_id, workspace.id)
    stamped = ResponseScope(workspace_id=scope.workspace_id, form_ids=scope.form_ids)
    assert len((await walk(stamped, size=4))[0]) == 8
    both = unlinked_scope(workspace.id, form.form_id)
    for size in (1, 4, 50):
        ids, _ = await walk(both, size=size)
        assert ids == await stored_ids(form.form_id) and len(ids) == 12


async def test_a_response_without_a_time_comes_last_and_is_not_dropped(workspace):
    form = await form_of(workspace, 9)
    scope = await form_scope(form.form_id, workspace.id)
    await sql(
        "UPDATE app.form_responses SET created_at = NULL WHERE id IN"
        " (SELECT id FROM app.form_responses WHERE form_id = :f ORDER BY id LIMIT 1 OFFSET 2)"
        " OR id IN (SELECT id FROM app.form_responses WHERE form_id = :f ORDER BY id LIMIT 1 OFFSET 6)",
        f=form.form_id,
    )
    expected = await stored_ids(form.form_id, "created_at IS NOT NULL") + await stored_ids(
        form.form_id, "created_at IS NULL"
    )
    for size in (1, 2, 7, 9, 50):
        ids, _ = await walk(scope, size=size)
        assert ids == expected and len(ids) == 9
    assert await container.form_response_repo().count_for_export(scope) == 9


async def test_a_stub_kept_for_a_deletion_request_is_not_a_response(workspace):
    form = await form_of(workspace, 6)
    scope = await form_scope(form.form_id, workspace.id)
    await sql(
        "UPDATE app.form_responses SET doc = doc - 'answers' WHERE id ="
        " (SELECT id FROM app.form_responses WHERE form_id = :f ORDER BY id LIMIT 1 OFFSET 1)",
        f=form.form_id,
    )
    ids, _ = await walk(scope, size=4)
    assert ids == await stored_ids(form.form_id) and len(ids) == 5
    assert await container.form_response_repo().count_for_export(scope) == 5


async def test_an_export_scope_is_one_form(workspace):
    form = await form_of(workspace, 1)
    scope = await form_scope(form.form_id, workspace.id)
    two = type(scope)(workspace_id=scope.workspace_id, form_ids=(form.form_id, "other"))
    with pytest.raises(ValueError):
        await container.form_response_repo().export_batch(two, None, limit=5)


# ------------------------------------------------------------------ the plan


SEED_FORM = text("""
    INSERT INTO app.form_responses (id, created_at, updated_at, doc, _bc_checksum)
    SELECT
      lpad(to_hex(g + :first), 24, '0'),
      cast(:base as timestamptz) + (g / 3) * interval '7 seconds',   -- three rows share each time
      cast(:base as timestamptz) + (g / 3) * interval '7 seconds',
      jsonb_strip_nulls(jsonb_build_object(
        '_id', jsonb_build_object('$oid', lpad(to_hex(g + :first), 24, '0')),
        'form_id', cast(:form_id as text),
        'workspace_id', cast(:workspace_id as text),
        'response_id', 'r' || (g + :first),
        'provider', 'self',
        'form_version', 1 + (g % 3),
        'dataOwnerIdentifier', CASE WHEN g % 2 = 0 THEN 'user' || g || '@example.com' END,
        -- about what a form of thirty answers weighs once encrypted: stored out of line
        'answers', md5(g::text) || repeat(md5((g + 1)::text), cast(:weight as int))
      )),
      'x'
    FROM generate_series(1, cast(:rows as int)) AS g
    """)


async def seeded(workspace, form_id: str, rows: int, first: int = 0, weight: int = 1) -> None:
    """``rows`` responses of one form; ``weight`` 80 makes each about 2.6 KB."""
    async with container.pg_engine().begin() as connection:
        await connection.execute(
            SEED_FORM,
            {
                "base": BASE,
                "form_id": form_id,
                "workspace_id": str(workspace.id),
                "rows": rows,
                "first": first,
                "weight": weight,
            },
        )
    async with container.pg_engine().connect() as connection:
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        await connection.execute(text("VACUUM ANALYZE app.form_responses"))


async def test_a_batch_deep_in_a_form_is_an_ordered_index_scan_of_its_own_rows(workspace, published_form):
    rows = int(os.getenv("EXPORT_PLAN_ROWS", "30000"))
    await seeded(workspace, published_form.form_id, rows)
    scope = await form_scope(published_form.form_id, workspace.id)
    repo = container.form_response_repo()
    # the cursor of a pass that has read the first 1,000: nearly the whole form is still ahead
    (at,) = await sql(
        "SELECT created_at, id FROM app.form_responses WHERE form_id = :f ORDER BY created_at, id OFFSET :n LIMIT 1",
        f=published_form.form_id,
        n=1000,
    )
    cursor = ExportCursor(created_at=at[0], id=at[1])
    with Captured(container.pg_engine()) as captured:
        batch, _ = await repo.export_batch(scope, None, after=cursor, limit=500)
    assert len(batch) == 500
    keyset = [(s, p) for s, p in captured.statements if "ORDER BY" in s and "created_at >=" in s]
    plan, _ = await explain(*keyset[0])
    kinds = [n["Node Type"] for n in nodes(plan)]
    scans = [n for n in nodes(plan) if n.get("Index Name") in ORDERED_INDEXES]
    assert scans, kinds
    # read in index order (ties finished by id), not sorted after reading the rest of the form
    assert not {"Sort", "Bitmap Heap Scan"} & set(kinds), kinds
    read = sum(n.get("Actual Rows", 0) + n.get("Rows Removed by Filter", 0) for n in scans)
    assert read <= 520, read


# ---------------------------------------------------------------- the benchmark

SIZES = [int(n) for n in os.environ.get("EXPORT_BENCH_ROWS", "").split(",") if n.strip()]

COUNT_OLD = (
    "SELECT count(*) FROM app.form_responses WHERE form_id = :f"
    " AND coalesce(jsonb_typeof(doc -> 'answers'), 'null') != 'null'"
)


async def old_batch(repo, scope, after_id):
    """The removed ``export_batch``: ``ORDER BY id`` under the scope's filter and
    the ``jsonb_typeof`` test, decoded like the new one."""
    from sqlalchemy import func

    from backend.app.repositories.postgres.responses import _in_scope
    from backend.db.models import FormResponseRow as row

    where = [_in_scope(row, scope), func.coalesce(func.jsonb_typeof(row.doc["answers"]), "null") != "null"]
    if after_id is not None:
        where.append(row.id > after_id)
    return await repo.many(*where, order_by=(row.id,), limit=500)


@pytest.mark.skipif(not SIZES, reason="set EXPORT_BENCH_ROWS to run the benchmark")
@pytest.mark.parametrize("size", SIZES)
async def test_bench(size, workspace, published_form):
    # a table that holds other forms too, as a real one does: ``EXPORT_BENCH_NOISE``
    # responses (default 200,000) of 2,000-response forms
    for other in range(int(os.getenv("EXPORT_BENCH_NOISE", "200000")) // 2000):
        await seeded(workspace, f"other{other:019d}", 2000, first=(other + 1) * 10_000_000, weight=8)
    await seeded(workspace, published_form.form_id, size, weight=80)
    form = published_form.form_id
    scope = await form_scope(form, workspace.id)
    repo = container.form_response_repo()

    old, after, total = [], None, 0
    while True:
        started = time.perf_counter()
        batch = await old_batch(repo, scope, after)
        old.append((time.perf_counter() - started) * 1000)
        total += len(batch)
        if len(batch) < 500:
            break
        after = str(batch[-1].id)
    new, cursor, seen = [], None, 0
    while True:
        started = time.perf_counter()
        batch, cursor = await repo.export_batch(scope, None, after=cursor, limit=500)
        new.append((time.perf_counter() - started) * 1000)
        seen += len(batch)
        if len(batch) < 500:
            break
    started = time.perf_counter()
    counted = await sql(COUNT_OLD, f=form)
    count_old_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    await repo.count_for_export(scope)
    count_new_ms = (time.perf_counter() - started) * 1000
    assert total == seen == size and counted[0][0] == size
    print(
        f"\nEXPORT_BENCH rows={size} batches={len(new)} | by id: batch median={statistics.median(old):.0f}ms "
        f"worst={max(old):.0f}ms pass={sum(old):.0f}ms | keyset: batch median={statistics.median(new):.0f}ms "
        f"worst={max(new):.0f}ms pass={sum(new):.0f}ms | count old={count_old_ms:.0f}ms new={count_new_ms:.0f}ms"
    )
