from concurrent.futures.thread import ThreadPoolExecutor

from settings.application import settings

thread_pool_executor = ThreadPoolExecutor(max_workers=settings.max_thread_pool_executors)