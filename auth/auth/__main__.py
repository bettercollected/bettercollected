import os

import uvicorn
from auth.app import access_log, get_application


def main():
    """Run the FastAPI application."""
    app = get_application()  # installs the access-log filter (app/access_log.py)
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
    access_log.install()  # idempotent; after uvicorn configured its loggers
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
