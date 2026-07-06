from pymongo import IndexModel

from common.configs.mongo_document import MongoDocument


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
        indexes = [IndexModel("form_id"), IndexModel("session_id")]
