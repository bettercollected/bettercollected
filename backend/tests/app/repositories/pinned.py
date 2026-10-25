"""Pinned results of repository steps (ids and timestamps aside).

A group whose Mongo repositories are gone keeps what its parity tests proved:
each step of a test runs on the Postgres repository and its result is compared
with the one pinned in a JSON fixture, written (``pin_env=1``, one process)
from a run of the 4.0-era repositories whose Mongo/Postgres parity tests
passed, never regenerated to make a change pass.
"""

import datetime as dt
import json
import os
from enum import Enum
from pathlib import Path

from bson import ObjectId
from fastapi_pagination import Page, Params
from fastapi_pagination.api import set_page, set_params

from tests.app.repositories.parity import strip


def plain(value):
    """``strip``ped results as JSON data (ids and dates left by the raw
    aggregation shapes as strings)."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


class Pinned:
    """The results of one test's steps, compared with (or, with the pin
    variable set to ``1``, written to) the fixture."""

    def __init__(self, fixture: Path, pin_env: str, case: str):
        self.fixture = fixture
        self.pin = os.getenv(pin_env) == "1"
        self.case = case
        self.results = {}

    async def step(self, label: str, call, key=None):
        result = await call()
        if isinstance(result, Page):
            value = plain(
                {
                    "total": result.total,
                    "page": result.page,
                    "pages": result.pages,
                    "items": strip(result.items),
                }
            )
        else:
            value = plain(strip(result))
        if key is not None:
            value = sorted(value, key=key)
        self.results[f"{len(self.results):02d} {label}"] = value
        return result

    async def page(self, label: str, call, size: int = 10):
        """A listing step: ``call`` runs with the pagination of page 1."""
        with set_page(Page), set_params(Params(page=1, size=size)):
            return await self.step(label, call)

    async def steps(self, repo, steps):
        for name, args in steps:
            await self.step(name, lambda: getattr(repo, name)(*args()))

    def check(self):
        pinned = json.loads(self.fixture.read_text()) if self.fixture.exists() else {}
        if self.pin:
            pinned[self.case] = self.results
            self.fixture.write_text(json.dumps(pinned, indent=1, sort_keys=True) + "\n")
            return
        expected = pinned[self.case]
        assert list(self.results) == list(expected)
        for label, value in self.results.items():
            assert value == expected[label], label
