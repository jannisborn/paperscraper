"""Dump medrxiv data in JSONL format."""

import os
from datetime import datetime
from typing import Optional, Tuple

from ..utils import get_server_dumps_dir
from ..xrxiv.xrxiv_api import MedRxivApi

today = datetime.today().strftime("%Y-%m-%d")
save_folder = get_server_dumps_dir()
save_path = os.path.join(save_folder, f"medrxiv_{today}.jsonl")


def medrxiv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_path: str = save_path,
    max_retries: int = 10,
    request_timeout: Tuple[float, float] = (5.0, 30.0),
    retry_backoff_seconds: float = 1.0,
    window_days: int = 30,
    max_workers: int = 8,
):
    """Fetches papers from medrxiv based on time range, i.e., start_date and end_date.
    If the start_date and end_date are not provided, then papers will be fetched from
    medrxiv starting from the launch date of medrxiv until current date. The fetched
    papers will be stored in jsonl format in save_path.

    Args:
        start_date (str, optional): begin date expressed as YYYY-MM-DD.
            Defaults to None, i.e., earliest possible.
        end_date (str, optional): end date expressed as YYYY-MM-DD.
            Defaults to None, i.e., today.
        save_path (str, optional): Path where the dump is stored.
            Defaults to save_path.
        max_retries (int, optional): Number of retries when API shows connection issues.
            Defaults to 10.
        request_timeout (Tuple[float, float], optional): (connect timeout, read timeout).
            Defaults to (5.0, 30.0).
        retry_backoff_seconds (float, optional): Initial retry backoff.
            Defaults to 1.0.
        window_days (int, optional): Date-window size used for pagination.
            Defaults to 30.
        max_workers (int, optional): Number of parallel workers over date windows.
            Defaults to 8.
    """
    api = MedRxivApi(
        max_retries=max_retries,
        request_timeout=request_timeout,
        retry_backoff_seconds=retry_backoff_seconds,
        window_days=max(1, int(window_days)),
    )
    api.dump_papers(
        save_path=save_path,
        start_date=start_date,
        end_date=end_date,
        max_retries=max_retries,
        max_workers=max_workers,
        window_days=window_days,
        deduplicate_dois=False,
        show_progress=True,
    )
