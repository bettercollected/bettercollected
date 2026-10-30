import logging
import os

import uvicorn
from auth.app import get_application


class AccessLogWithoutQuery(logging.Filter):
    """uvicorn's access line without the query string: the backend calls this
    service with emails and sign-in codes in it (``/auth/otp/validate``)."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], args[2].split("?", 1)[0], *args[3:])
        return True


def main():
    """Run the FastAPI application."""
    app = get_application()
    # Config sets up uvicorn's loggers; the filter goes on after that
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
    logging.getLogger("uvicorn.access").addFilter(AccessLogWithoutQuery())
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
