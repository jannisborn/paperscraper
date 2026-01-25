"""Dump chemRxiv data in JSONL format."""

import logging
import os
import sys
from datetime import datetime
from typing import Optional

from ..utils import get_server_dumps_dir
from .utils.chemrxiv import ChemrxivAPI, download_full, parse_dump

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

today = datetime.today().strftime("%Y-%m-%d")
save_folder = get_server_dumps_dir()
save_path = os.path.join(save_folder, f"chemrxiv_{today}.jsonl")


def chemrxiv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_path: str = save_path,
) -> None:
    """Fetches papers from bichemrxiv based on time range, i.e., start_date and end_date.
    If the start_date and end_date are not provided, papers will be fetched from chemrxiv
    from the launch date of chemrxiv until the current date. The fetched papers will be
    stored in jsonl format in save_path.

    Args:
        start_date (str, optional): begin date expressed as YYYY-MM-DD.
            Defaults to None, i.e., earliest possible.
        end_date (str, optional): end date expressed as YYYY-MM-DD.
            Defaults to None, i.e., today.
        save_path (str, optional): Path where the dump is stored.
            Defaults to save_path.
    """

    # create API client
    api = ChemrxivAPI(start_date, end_date)
    # Download the data
    download_full(save_folder, api)
    # Convert to JSONL format.
    parse_dump(save_folder, save_path)
