from pymongo import IndexModel

from backend.config import settings
from common.configs.mongo_document import MongoDocument


def _retention_indexes():
    """TTL index on ``created_at``: MongoDB deletes an event this long after it
    was recorded (API_FLOW_EVENTS_RETENTION_DAYS, 13 months by default; 0 = no
    index, events are kept). The Postgres twin is swept by
    ``FlowEventService`` (``delete_older_than``). Changing the period on a
    deployed database needs the old ``created_at_1`` index dropped (or
    ``collMod``), as MongoDB will not recreate an index with other options."""
    days = settings.api_settings.FLOW_EVENTS_RETENTION_DAYS
    if days <= 0:
        return []
    return [IndexModel([("created_at", 1)], expireAfterSeconds=days * 86400)]


class FlowEventDocument(MongoDocument):
    """
    A single anonymous navigation step inside a form fill.

    Deliberately privacy-first: no answers, no identity — only a random
    client-generated session id and which page led to which. This is enough to
    aggregate per-branch traffic and drop-off without ever persisting content
    a responder hasn't chosen to submit.
    """

    form_id: str
    session_id: str
    # page id, or the sentinels "__welcome__" / "__submit__"
    from_page: str
    to_page: str

    class Settings:
        name = "form_flow_events"
        indexes = [
            IndexModel("form_id"),
            IndexModel("session_id"),
            *_retention_indexes(),
        ]
