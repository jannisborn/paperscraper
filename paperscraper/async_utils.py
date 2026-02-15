import asyncio
import logging
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
) -> Callable[[F], F]:
    """
    Decorator factory that retries an `async def` on HTTP 429, with exponential backoff.

    Args:
        max_retries: how many times to retry before giving up.
        base_delay: initial delay in seconds; next delays will be multiplied by `factor`.
        factor: multiplier for delay after each retry.
        constant_delay: fixed delay before each attempt.

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
                    if status != 429:
                        raise
                    last_exception = e
                    sleep_for = delay
                    if e.response is not None:
                        ra = e.response.headers.get("Retry-After")
                        if ra is not None:
                            try:
                                sleep_for = float(ra)
                            except ValueError:
                                pass
                    delay *= factor

                except (httpx.ReadError, httpx.TimeoutException, httpx.TransportError) as e:
                    last_exception = e
                    sleep_for = delay
                    delay *= factor

                if attempt == max_retries:
                    msg = (
                        f"{func.__name__} failed after {attempt} attempts with "
                        f"last delay {sleep_for:.2f}s"
                    )
                    raise RuntimeError(msg) from last_exception

                await asyncio.sleep(sleep_for)

        return wrapper

    return decorator
