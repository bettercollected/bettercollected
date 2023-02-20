"""Application implementation - utilities.

Resources:
    1. https://aioredis.readthedocs.io/en/latest/

"""
from backend.app.utils.aiohttp_client import AiohttpClient
from backend.app.utils.redis import RedisClient


__all__ = ("AiohttpClient", "RedisClient")
