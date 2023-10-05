import asyncio
import threading
from typing import Awaitable, TypeVar

T = TypeVar("T")


def _start_background_loop(loop: asyncio.AbstractEventLoop):
    """
    Runs the given event loop in a background thread. This function is intended to be used
    as the target of a thread, and the event loop will run indefinitely until it is stopped.

    Args:
        loop (asyncio.AbstractEventLoop): The event loop to run in the background.
    """
    asyncio.set_event_loop(loop)
    loop.run_forever()


_LOOP = asyncio.new_event_loop()
_LOOP_THREAD = threading.Thread(
    target=_start_background_loop, args=(_LOOP,), daemon=True
)
_LOOP_THREAD.start()


def asyncio_run(coro: Awaitable[T], timeout=30) -> T:
    """
    Runs the given coroutine in an event loop running on a background thread,
    and blocks the current thread until it returns a result. This function is useful for
    running asyncio code in a thread-based environment, such as gevent.

    Args:
        coro (Awaitable[T]): A coroutine, typically an async method.
        timeout (int, optional): How many seconds we should wait for a result before raising an error.
            Defaults to 30.

    Returns:
        T: The result of the coroutine.
    """
    return asyncio.run_coroutine_threadsafe(coro, _LOOP).result(timeout=timeout)
