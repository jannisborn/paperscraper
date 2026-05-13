import asyncio
import logging
import random
import sys
import threading
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar, Union

import httpx

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def _start_bg_loop(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


# Start one background loop in its own daemon thread
_background_loop = asyncio.new_event_loop()
threading.Thread(target=_start_bg_loop, args=(_background_loop,), daemon=True).start()


def optional_async(
    func: Callable[..., Awaitable[T]],
) -> Callable[..., Union[T, Awaitable[T]]]:
    """
    Allows an async function to be called from sync code (blocks until done)
    or from within an async context (returns a coroutine to await).
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> Union[T, Awaitable[T]]:
        coro = func(*args, **kwargs)
        try:
            # If we're already in an asyncio loop, hand back the coroutine:
            asyncio.get_running_loop()
            return coro  # caller must await it
        except RuntimeError:
            # Otherwise, schedule on the background loop and block
            future = asyncio.run_coroutine_threadsafe(coro, _background_loop)
            return future.result()

    return wrapper


def run_sync(coroutine: Awaitable[T]) -> T:
    """
    Run a coroutine on the background loop and block for the result.

    This is safe to call from sync or async contexts, but will block the caller.
    """
    future = asyncio.run_coroutine_threadsafe(coroutine, _background_loop)
    return future.result()


def retry_with_exponential_backoff(
    *,
    max_retries: int = 5,
    base_delay: float = 1.0,
    factor: float = 1.3,
    constant_delay: float = 0.2,
    max_delay: float = 60.0,
    jitter_ratio: float = 0.1,
) -> Callable[[F], F]:
    """
    Decorator factory that retries an `async def` on transient HTTP/network errors, with exponential backoff.

    Args:
        max_retries: how many times to retry before giving up.
        base_delay: initial delay in seconds; next delays will be multiplied by `factor`.
        factor: multiplier for delay after each retry.
        constant_delay: fixed delay before each attempt.
        max_delay: maximum backoff delay between attempts.
        jitter_ratio: add +/- jitter_ratio * delay seconds of jitter.

    Usage:

        @retry_with_exponential_backoff(max_retries=3, base_delay=0.5)
        async def fetch_data(...):
            ...

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            delay = base_delay
            last_exception: BaseException | None = None
            for attempt in range(1, max_retries + 1):
                await asyncio.sleep(constant_delay)
                try:
                    return await func(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    status = e.response.status_code if e.response is not None else None
                    retryable = status == 429 or (
                        status is not None and (status == 408 or 500 <= status <= 599)
                    )
                    if not retryable:
                        raise
                    last_exception = e
                    sleep_for = min(delay, max_delay)
                    if e.response is not None:
                        ra = e.response.headers.get("Retry-After")
                        if ra is not None:
                            try:
                                sleep_for = min(float(ra), max_delay)
                            except ValueError:
                                pass
                    delay = min(delay * factor, max_delay)

                except (
                    httpx.ReadError,
                    httpx.TimeoutException,
                    httpx.TransportError,
                ) as e:
                    last_exception = e
                    sleep_for = min(delay, max_delay)
                    delay = min(delay * factor, max_delay)

                if attempt == max_retries:
                    msg = (
                        f"{func.__name__} failed after {attempt} attempts with "
                        f"last delay {sleep_for:.2f}s"
                    )
                    raise RuntimeError(msg) from last_exception

                if jitter_ratio > 0:
                    jitter = sleep_for * jitter_ratio
                    sleep_for = max(0.0, sleep_for + random.uniform(-jitter, jitter))

                await asyncio.sleep(sleep_for)

        return wrapper

    return decorator
