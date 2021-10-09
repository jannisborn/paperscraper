"""Dump chemRxiv data in JSONL format."""
import logging
import os
import sys
from datetime import datetime

import pkg_resources

from .utils.chemrxiv import ChemrxivAPI, download_full, parse_dump

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)

today = datetime.today().strftime('%Y-%m-%d')
save_folder = pkg_resources.resource_filename('paperscraper', 'server_dumps')
save_path = os.path.join(save_folder, f'chemrxiv_{today}.jsonl')


def chemrxiv(save_path: str = save_path, token=None) -> None:
    """Fetches all papers from biorxiv until current date, stores them in jsonl
    format in save_path.

    Args:
        save_path (str, optional): Path where the dump is stored.
            Defaults to save_path.
    """

    # API remains down for the moment
    chemrxiv_unavailable()

    # create API client
    api = ChemrxivAPI(token=token)
    # Download the data
    download_full(save_folder, api)
    # Convert to JSONL format.
    parse_dump(save_folder, save_path)


def chemrxiv_unavailable():
    raise ConnectionRefusedError(
        'From Sept. 2021 onwards, ChemRxiv API is no accessible (details in README).'
    )
