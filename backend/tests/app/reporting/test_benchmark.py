"""The scale benchmark of the report engine (docs/reporting.md): real Tink, a real
Postgres, forms of 30 answers (about 2.5 KB once encrypted), a report of twelve
cards over them.

Not part of a normal run: it needs ``REPORT_BENCH_ROWS`` (a comma list, e.g.
``1000,10000,20000``) and prints one line per size. It is what the cap
(``limits.REPORT_MAX_ROWS``) was set against::

    REPORT_BENCH_ROWS=1000,10000,20000 uv run pytest tests/app/reporting/test_benchmark.py -s

Run it on a Postgres that has a RAM disk or ``fsync=off`` (the generation of
the responses is most of its time) and on a quiet machine: the figures are one
machine's, a guide to the order of magnitude, not a promise.
"""

import json
import os
import random
import re
import statistics
import time

import pytest
from sqlalchemy import text

from backend.app.container import container
from tests.app.controllers.data import testUser
from tests.app.reporting.helpers import (
    add_many,
    answer_bool,
    answer_choice,
    answer_choices,
    answer_number,
    answer_text,
    card,
    choice_question,
    definition,
    make_form,
    simple_question,
)

SIZES = [int(n) for n in os.environ.get("REPORT_BENCH_ROWS", "").split(",") if n.strip()]

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not SIZES, reason="set REPORT_BENCH_ROWS to run the benchmark"),
]

DEPTS = {f"d{i}": f"Department {i}" for i in range(8)}
TOOLS = {f"t{i}": f"Tool {i}" for i in range(6)}


def questions():
    fields = []
    for n in range(8):
        fields.append(choice_question(f"c{n}", DEPTS, f"Choice {n}"))
    for n in range(4):
        fields.append(choice_question(f"m{n}", TOOLS, f"Multi {n}", multiple=True))
    for n in range(8):
        fields.append(simple_question(f"r{n}", "rating", f"Rating {n}"))
    for n in range(4):
        fields.append(simple_question(f"n{n}", "number", f"Number {n}"))
    for n in range(4):
        fields.append(simple_question(f"y{n}", "yes_no", f"Yes/no {n}"))
    for n in range(2):
        fields.append(simple_question(f"t{n}", "long_text", f"Text {n}"))
    return fields


def response(rng: random.Random):
    answers = {}
    for n in range(8):
        answers[f"c{n}"] = answer_choice(rng.choice(list(DEPTS)))
    for n in range(4):
        answers[f"m{n}"] = answer_choices(*rng.sample(list(TOOLS), rng.randint(1, 3)))
    for n in range(8):
        answers[f"r{n}"] = answer_number(rng.randint(1, 5))
    for n in range(4):
        answers[f"n{n}"] = answer_number(rng.randint(0, 5000))
    for n in range(2):
        answers[f"t{n}"] = answer_text("lorem ipsum dolor sit amet " * rng.randint(4, 12))
    for n in range(4):
        answers[f"y{n}"] = answer_bool(rng.random() < 0.5)
    return {"answers": answers, "version": 1}


def report():
    """Twelve cards, ten of which read answers, two counted in SQL."""
    cards = [
        card("c0", "bar", dimension="q:c0"),
        card("c1", "bar", dimension="q:c1", measures=[{"agg": "count"}, {"agg": "avg", "field": "q:r0"}]),
        card("m0", "bar", dimension="q:m0"),
        card("m1", "bar", dimension="q:m1"),
        card("r0", "bar", dimension="q:r0"),
        card("r1", "bar", dimension="q:r1"),
        card("y0", "donut", dimension="q:y0"),
        card("n0", "tile", measures=[{"agg": "avg", "field": "q:n0"}, {"agg": "sum", "field": "q:n0"}]),
        card("n1", "tile", measures=[{"agg": "min", "field": "q:n1"}, {"agg": "max", "field": "q:n1"}]),
        card("a0", "table", dimension="q:c2", measures=[{"agg": "avg", "field": "q:r2"}, {"agg": "avg", "field": "q:r3"}]),
        card("time", "line", dimension={"field": "submitted_at", "bucket": "day"}),
        card("ver", "bar", dimension="form_version"),
    ]
    return definition(*cards)


def peak_rss_mb() -> float:
    with open("/proc/self/status") as status:
        found = re.search(r"VmHWM:\s+(\d+) kB", status.read())
    return int(found.group(1)) / 1024 if found else float("nan")


def reset_peak() -> None:
    try:
        with open("/proc/self/clear_refs", "w") as handle:
            handle.write("5")
    except OSError:
        pass


async def timed(coro):
    started = time.perf_counter()
    result = await coro
    return result, time.perf_counter() - started


@pytest.mark.parametrize("size", SIZES)
async def test_the_pass_at(size, workspace, monkeypatch, reporting_on):
    from backend.app.services.reporting import limits

    # the benchmark asks for more than the cap on purpose to see where it falls
    monkeypatch.setattr(limits, "REPORT_MAX_ROWS", max(limits.REPORT_MAX_ROWS, size))
    rng = random.Random(7)
    form = await make_form(workspace, questions(), title="Benchmark")
    started = time.perf_counter()
    items = [response(rng) for _ in range(size)]
    await add_many(workspace, form, items, concurrency=50)
    generated = time.perf_counter() - started
    # what autovacuum does on a live table: fresh statistics and a visibility map
    async with container.pg_sessionmaker()() as session:
        connection = await session.connection(execution_options={"isolation_level": "AUTOCOMMIT"})
        await connection.execute(text("VACUUM ANALYZE app.form_responses"))
    service = container.report_service()
    body = json.dumps(report()).encode()

    async def run():
        return await service.query(testUser, workspace.id, form.form_id, body)

    # cold: nothing cached; the passes of a few runs, median and best
    cold = []
    for _ in range(3):
        service._cache.clear()
        reset_peak()
        baseline = peak_rss_mb()
        result, seconds = await timed(run())
        cold.append((seconds, peak_rss_mb() - baseline))
    assert result["n"] == size and result["scanned"] == size
    warm, warm_seconds = await timed(run())
    assert warm["generatedAt"] == result["generatedAt"] or warm["generatedAt"]
    sql_body = json.dumps(
        definition(card("t", "tile"), card("time", "line", dimension={"field": "submitted_at", "bucket": "day"}),
                   card("ver", "bar", dimension="form_version"), card("s", "bar", dimension="status"))
    ).encode()
    _, sql_seconds = await timed(service.query(testUser, workspace.id, form.form_id, sql_body))
    scope = await service._responses.scope(workspace.id, [form.form_id])
    repo = container.report_repo()
    plan_filters = None
    _, token_seconds = await timed(repo.token(scope, plan_filters))
    _, count_seconds = await timed(repo.count(*repo.report_where(scope, plan_filters)))

    seconds = sorted(s for s, _ in cold)
    print(
        "\nREPORT_BENCH rows={rows} generated_in={gen:.1f}s | cold_pass best={best:.2f}s median={med:.2f}s "
        "({rps:.0f} rows/s at median) peak_rss_over_baseline={mem:.0f}MB | "
        "cache_hit={hit:.3f}s | sql_only_cards={sql:.3f}s | token_query={tok:.3f}s count_query={cnt:.3f}s".format(
            rows=size,
            gen=generated,
            best=seconds[0],
            med=statistics.median(seconds),
            rps=size / statistics.median(seconds),
            mem=max(m for _, m in cold),
            hit=warm_seconds,
            sql=sql_seconds,
            tok=token_seconds,
            cnt=count_seconds,
        )
    )
