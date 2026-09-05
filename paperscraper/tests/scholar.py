import functools
import logging
import multiprocessing
import traceback
from queue import Empty

import pytest
from scholarly._proxy_generator import MaxTriesExceededException

SCHOLARLY_TIMEOUT_SECONDS = 60


def _run_scholarly_test(func, args, kwargs):
    if "fork" not in multiprocessing.get_all_start_methods():
        return func(*args, **kwargs)

    ctx = multiprocessing.get_context("fork")
    queue = ctx.Queue()

    def target():
        try:
            func(*args, **kwargs)
        except MaxTriesExceededException as exc:
            queue.put(("skip", f"MaxTriesExceededException caught: {exc}"))
        except pytest.skip.Exception as exc:
            queue.put(("skip", str(exc)))
        except BaseException:
            queue.put(("fail", traceback.format_exc()))
        else:
            queue.put(("ok", ""))

    process = ctx.Process(target=target)
    process.start()
    process.join(SCHOLARLY_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join()
        raise TimeoutError(
            f"scholarly test exceeded {SCHOLARLY_TIMEOUT_SECONDS} seconds"
        )

    try:
        status, message = queue.get(timeout=1)
    except Empty:
        status, message = ("ok", "")
    if status == "ok" and process.exitcode:
        status = "fail"
        message = f"scholarly test process exited with code {process.exitcode}"

    queue.close()
    queue.join_thread()

    if status == "skip":
        logging.error(message)
        pytest.skip(message)
    if status == "fail":
        pytest.fail(message)


def handle_scholar_exception(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return _run_scholarly_test(func, args, kwargs)
        except MaxTriesExceededException as exc:
            logging.error(f"MaxTriesExceededException caught: {exc}")
            pytest.skip("Skipping test due to MaxTriesExceededException")
        except TimeoutError as exc:
            logging.error(f"TimeoutError caught: {exc}")
            pytest.skip(f"Skipping test due to scholarly timeout: {exc}")

    return wrapper
