"""The security primitives need no application, database or mirror metrics:
the suite-wide autouse fixtures are replaced with no-ops here."""

import pytest


@pytest.fixture(autouse=True)
def _clean_db():
    yield


@pytest.fixture(autouse=True)
def rate_limit_clock():
    yield {}


@pytest.fixture(autouse=True)
def no_silent_mirror_failures():
    yield
