"""uvicorn's access log without query strings: the backend calls this service
with emails and sign-in codes in them (``/auth/otp/validate``,
``/auth/otp/send``). :func:`install` runs in ``get_application`` (every way the
app is served: ``python -m auth``, ``uvicorn auth.app:get_application``) and
again after ``python -m auth`` configures uvicorn's loggers; it adds the filter
once. ``logging.config.dictConfig`` (uvicorn's set-up) keeps a logger's
filters, so the order does not matter."""

import logging

ACCESS_LOGGER = "uvicorn.access"


class AccessLogWithoutQuery(logging.Filter):
    """The request line's path (the third argument of uvicorn's access record)
    without its query string."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], args[2].split("?", 1)[0], *args[3:])
        return True


def install() -> AccessLogWithoutQuery:
    """The filter on uvicorn's access logger, added once per process."""
    logger = logging.getLogger(ACCESS_LOGGER)
    for existing in logger.filters:
        if isinstance(existing, AccessLogWithoutQuery):
            return existing
    added = AccessLogWithoutQuery()
    logger.addFilter(added)
    return added
