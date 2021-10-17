"""Dump chemRxiv data in JSONL format."""
import logging
import os
import sys
from datetime import datetime

import pkg_resources

from .utils.chemrxiv import ChemrxivAPI, download_full, parse_dump

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)

today = datetime.today().strftime("%Y-%m-%d")
save_folder = pkg_resources.resource_filename("paperscraper", "server_dumps")
save_path = os.path.join(save_folder, f"chemrxiv_{today}.jsonl")


def chemrxiv(save_path: str = save_path) -> None:
    """Fetches all papers from biorxiv until current date, stores them in jsonl
    format in save_path.

    Args:
        save_path (str, optional): Path where the dump is stored.
            Defaults to save_path.
    """

    # create API client
    api = ChemrxivAPI()
    # Download the data
    download_full(save_folder, api)
    # Convert to JSONL format.
    parse_dump(save_folder, save_path)
