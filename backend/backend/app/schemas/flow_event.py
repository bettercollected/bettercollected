from common.records import Record


class FlowEventDocument(Record):
    """
    A single anonymous navigation step inside a form fill.

    Deliberately privacy-first: no answers, no identity — only a random
    client-generated session id and which page led to which. This is enough to
    aggregate per-branch traffic and drop-off without ever persisting content
    a responder hasn't chosen to submit.
    """

    # kept for API_FLOW_EVENTS_RETENTION_DAYS (13 months by default; 0 = kept):
    # FlowEventService sweeps older events (delete_older_than)

    form_id: str
    session_id: str
    # page id, or the sentinels "__welcome__" / "__submit__"
    from_page: str
    to_page: str

    class Settings:
        name = "form_flow_events"
