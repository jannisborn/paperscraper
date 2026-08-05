"""Dump chemRxiv data in JSONL format."""

import logging
import os
import sys
from datetime import datetime
from typing import Optional

from ..utils import get_server_dumps_dir
from .utils.chemrxiv import download_full, parse_dump
from .utils.chemrxiv.chemrxiv_api import ChemrxivAPI
from .utils.chemrxiv.crossref_api import CrossrefChemrxivAPI
from .utils.chemrxiv.utils import download_full_crossref, parse_dump_crossref

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

today = datetime.today().strftime("%Y-%m-%d")
save_folder = get_server_dumps_dir()
SAVE_PATH = os.path.join(save_folder, f"chemrxiv_{today}.jsonl")


def chemrxiv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_path: str = SAVE_PATH,
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
            Defaults to SAVE_PATH.
    """

    if save_path == SAVE_PATH and (start_date is not None or end_date is not None):
        start_part = start_date or "2017-01-01"
        end_part = end_date or today
        save_path = os.path.join(save_folder, f"chemrxiv_{start_part}_{end_part}.jsonl")

    # create API client
    api = ChemrxivAPI(start_date, end_date)
    try:
        # Download the data
        download_full(save_folder, api)
        # Convert to JSONL format.
        parse_dump(save_folder, save_path)
    except PermissionError:
        logger.warning(
            "ChemRxiv OpenEngage API is blocked (403). Falling back to Crossref."
        )
        crossref_start = start_date or "2017-01-01"
        crossref_end = end_date or today
        crossref_api = CrossrefChemrxivAPI(crossref_start, crossref_end)
        download_full_crossref(save_folder, crossref_api)
        parse_dump_crossref(save_folder, save_path)
