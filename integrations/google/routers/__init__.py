from fastapi import FastAPI

from routers import scheduler


def include_routers(server: "FastAPI"):
    server.include_router(scheduler.router, tags=["Schedulers"])
