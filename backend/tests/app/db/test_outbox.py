from backend.app.container import container
from backend.app.repositories.allowed_origins_repository import AllowedOriginsRepository
from common.db import MirrorWriteFailureDocument, RoutingRepository, load_flags


class BrokenPostgres:
    async def add(self, origin):
        raise ConnectionError("postgres is down")


async def test_a_failed_mirror_write_lands_in_the_mongo_outbox_and_the_request_succeeds(
    _initialized_app,
):
    routed = RoutingRepository(
        group="refdata",
        flags=load_flags({"DB_WRITE_MODE__refdata": "dual"}),
        mongo=AllowedOriginsRepository(),
        postgres=BrokenPostgres(),
        on_mirror_failure=container.outbox_recorder(),
    )
    saved = await routed.add("https://mirror-fails.example")
    assert saved.origin == "https://mirror-fails.example"  # the primary write succeeded

    records = await MirrorWriteFailureDocument.find().to_list()
    assert len(records) == 1
    record = records[0]
    assert record.table_name == "AllowedOriginsRepository"
    assert record.op == "add"
    assert record.row_id == "https://mirror-fails.example"
    assert record.error.startswith("ConnectionError")
    assert record.attempts == 0 and record.resolved_at is None
