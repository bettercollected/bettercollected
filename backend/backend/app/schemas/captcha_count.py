from common.records import Record


class CaptchaDailyCountDocument(Record):
    """How many times one outcome of the automatic spam check happened on one
    UTC day for one form and purpose (``services/captcha/stats.py``).

    Counts only: no address, no client, no tag, no challenge, no person. The
    workspace and form are ids of the instance's own objects (empty for the
    creator's sign-in code, which belongs to no workspace). The id is a hash of
    the five key fields, so a day's count of one outcome is one row. Kept
    ``API_FLOW_EVENTS_RETENTION_DAYS`` (13 months by default) and swept with
    them."""

    # the UTC day, ``YYYY-MM-DD``
    day: str
    workspace_id: str = ""
    form_id: str = ""
    # "submit" or "mail"
    purpose: str
    # issued, verified, missing, invalid, expired, replayed, rate_limited
    outcome: str
    count: int = 0

    class Settings:
        name = "captcha_daily_counts"
