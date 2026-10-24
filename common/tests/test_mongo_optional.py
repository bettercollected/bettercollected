"""Mongo only while a repository group uses it (common/db/mongo.py).

The decision (``DbFlags.uses_mongo``) and the start-up it drives: without
Mongo, Beanie is set up with no request to the server and the client never
connects; with Mongo, an unreachable server still fails the start."""

import time

import pytest
from beanie import Document, View
from pymongo import AsyncMongoClient
from pymongo.errors import ServerSelectionTimeoutError

from common.db import load_flags
from common.db.groups import BACKEND_GROUPS, SERVICE_GROUPS
from common.db.mongo import (
    NOT_USED_URI,
    init_documents,
    mongo_client,
    mongo_required,
    mongo_status,
)

ALL_POSTGRES = {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"}
# nothing listens on port 1: a connection is refused at once
UNREACHABLE = "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=300"


# ----------------------------------------------------------------- the decision
@pytest.mark.parametrize(
    "env, expected",
    [
        ({}, True),  # today's default: Mongo for everything
        ({"DB_WRITE_MODE": "dual"}, True),
        ({"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "dual"}, True),
        (
            {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres_primary_dual"},
            True,  # Mongo is the mirror in the rollback window
        ),
        (ALL_POSTGRES, False),
        ({**ALL_POSTGRES, "JOBS_BACKEND": "postgres"}, False),
        ({**ALL_POSTGRES, "JOBS_BACKEND": "temporal"}, False),  # jobs never use Mongo
        (
            {**ALL_POSTGRES, "DB_SHADOW_READ_SAMPLE": "0.1"},
            True,
        ),  # shadow reads go to Mongo
    ],
)
def test_mongo_is_used_unless_every_group_is_on_postgres(env, expected):
    flags = load_flags(env)
    for service, groups in SERVICE_GROUPS.items():
        assert mongo_required(flags, groups) is expected, service


@pytest.mark.parametrize("group", BACKEND_GROUPS)
@pytest.mark.parametrize(
    "read, write",
    [
        ("mongo", "mongo"),
        ("mongo", "dual"),
        ("postgres", "dual"),
        ("postgres", "postgres_primary_dual"),
    ],
)
def test_one_group_still_on_mongo_keeps_the_service_on_it(group, read, write):
    flags = load_flags(
        {
            **ALL_POSTGRES,
            f"DB_READ_SOURCE__{group}": read,
            f"DB_WRITE_MODE__{group}": write,
        }
    )
    assert mongo_required(flags, BACKEND_GROUPS) is True
    # the other services' groups are not affected by a backend group's override
    assert mongo_required(flags, SERVICE_GROUPS["auth"]) is False
    assert mongo_required(flags, SERVICE_GROUPS["google"]) is False


def test_groups_moved_one_by_one_free_mongo_with_the_last():
    env = {}
    for group in BACKEND_GROUPS:
        assert mongo_required(load_flags(env), BACKEND_GROUPS) is True
        env[f"DB_READ_SOURCE__{group}"] = "postgres"
        env[f"DB_WRITE_MODE__{group}"] = "postgres"
    assert mongo_required(load_flags(env), BACKEND_GROUPS) is False


def test_without_groups_the_defaults_and_overrides_decide():
    assert load_flags(ALL_POSTGRES).uses_mongo() is False
    mixed = load_flags(
        {**ALL_POSTGRES, "DB_WRITE_MODE__forms": "postgres_primary_dual"}
    )
    assert mixed.uses_mongo() is True


def test_status_says_not_used():
    assert mongo_status(False) == {"used": False, "status": "not used"}
    assert mongo_status(True) == {"used": True, "status": "used"}


# ------------------------------------------------------------- the start-up
class Thing(Document):
    name: str

    class Settings:
        name = "things"


async def test_the_client_of_an_unused_mongo_points_nowhere():
    client = mongo_client("mongodb://mongo.example:27017/", required=False)
    try:
        assert client.topology_description.server_descriptions().keys() == {
            ("mongo-not-used.invalid", 27017)
        }
        assert NOT_USED_URI.startswith("mongodb://mongo-not-used.invalid")
    finally:
        await client.close()
    # unset MONGO_URI is fine when Mongo is not used
    await mongo_client(None, required=False).close()


async def test_documents_are_set_up_without_a_server():
    client = AsyncMongoClient(UNREACHABLE)
    try:
        started = time.monotonic()
        await init_documents(client["db"], [Thing], required=False)
        assert time.monotonic() - started < 0.25  # no server selection was attempted
        thing = Thing(name="x")  # a Document needs an initialised class
        assert type(thing).get_collection_name() == "things"
        # and touching Mongo anyway fails instead of hanging
        with pytest.raises(ServerSelectionTimeoutError):
            await Thing.find_one(Thing.name == "x")
    finally:
        await client.close()


async def test_a_required_mongo_that_is_unreachable_fails_the_start():
    client = AsyncMongoClient(UNREACHABLE)
    try:
        with pytest.raises(ServerSelectionTimeoutError):
            await init_documents(client["db"], [Thing], required=True)
    finally:
        await client.close()


class ThingView(View):
    name: str

    class Settings:
        source = Thing
        pipeline = []


async def test_views_need_a_server():
    client = mongo_client(None, required=False)
    try:
        with pytest.raises(TypeError, match="ThingView"):
            await init_documents(client["db"], [Thing, ThingView], required=False)
    finally:
        await client.close()
