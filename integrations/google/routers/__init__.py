from fastapi import FastAPI

from routers import scheduler


def include_routers(server: "FastAPI"):
    """
    Includes all the routers in the given FastAPI server instance.

    Parameters:
        server (FastAPI): FastAPI server instance to include routers in.
    """
    server.include_router(scheduler.router, tags=["Schedulers"])
