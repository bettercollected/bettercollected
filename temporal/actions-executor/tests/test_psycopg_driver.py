"""The Postgres queue needs psycopg 3 with a libpq of its own.

The image is python:3.11-slim and ships no libpq, so the executor started with
JOBS_BACKEND=postgres died with "ImportError: no pq wrapper available". A CI
runner has a system libpq, so importing psycopg is not enough to catch this:
the test asks for the bundled one (the ``psycopg[binary]`` extra).
"""

import psycopg


def test_psycopg_uses_its_bundled_libpq():
    assert psycopg.pq.__impl__ == "binary"


def test_the_queue_connector_can_be_built():
    from procrastinate import PsycopgConnector

    PsycopgConnector(conninfo="postgresql://u:p@127.0.0.1:1/db")
